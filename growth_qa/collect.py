"""Collect bounded, correlated evidence from test CRM and GA4 export accounts."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import quote

import httpx
import yaml
from growth_qa.reconcile import validate, timestamp

# Never retain email, phone, names, cookies, full URLs or access tokens.
SAFE_FIELDS = frozenset({'test_run_id', 'submission_id', 'event_id', 'utm_source', 'utm_medium',
    'utm_campaign', 'first_touch_source', 'last_touch_source', 'lifecyclestage',
    'hubspot_owner_id', 'pipeline', 'dealstage', 'form_id', 'hubspot_form_id',
    'lead_type', 'consent', 'has_gclid', 'has_fbclid'})


def safe_fields(fields):
    return {k: v for k, v in fields.items() if k in SAFE_FIELDS and isinstance(v, (str, int, float, bool, type(None)))}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


async def collect_hubspot(evidence, config, http):
    token = os.environ[config.get('token_env', 'QA_HUBSPOT_TOKEN')]
    headers = {'Authorization': f'Bearer {token}'}
    properties = list(SAFE_FIELDS - {'has_gclid', 'has_fbclid', 'consent'})
    # Operators must configure custom CRM properties on the test portal first.
    properties = config.get('properties', ['test_run_id', 'submission_id', 'utm_source', 'utm_medium', 'utm_campaign', 'lifecyclestage'])
    if not set(properties).issubset(SAFE_FIELDS):
        raise ValueError('Only allowlisted evidence properties may be collected')
    run_id = evidence['run_id']
    after = None
    observations = []
    max_pages = config.get('max_pages', 20)
    for _ in range(max_pages):
        payload = {'filterGroups': [{'filters': [{'propertyName': 'test_run_id', 'operator': 'EQ', 'value': run_id}]}], 'properties': properties, 'limit': 100}
        if after: payload['after'] = after
        response = await http.post('https://api.hubapi.com/crm/v3/objects/contacts/search', headers=headers, json=payload)
        response.raise_for_status()
        body = response.json()
        for contact in body['results']:
            fields = contact['properties']
            if fields.get('test_run_id') != run_id:
                raise ValueError('Uncorrelated CRM search result')
            observations.append({'run_id': run_id, 'source': 'hubspot', 'event': 'contact', 'record_id': str(contact['id']), 'occurred_at': contact['updatedAt'], 'fields': safe_fields(fields)})
        after = body.get('paging', {}).get('next', {}).get('after')
        if not after: break
    else:
        raise ValueError('CRM search truncated')
    # Form submissions prove receipt independently of contact creation/update.
    for form_id in config.get('form_ids', []):
        after = None
        for _ in range(max_pages):
            params = {'limit': 50}
            if after: params['after'] = after
            response = await http.get(f'https://api.hubapi.com/form-integrations/v1/submissions/forms/{quote(form_id, safe="")}', headers=headers, params=params)
            response.raise_for_status()
            body = response.json()
            for submission in body['results']:
                fields = {v['name']: v['value'] for v in submission['values']}
                if fields.get('test_run_id') != run_id: continue
                fields['hubspot_form_id'] = form_id
                observations.append({'run_id': run_id, 'source': 'hubspot', 'event': 'submission', 'record_id': str(submission.get('conversionId', submission['submittedAt'])), 'occurred_at': datetime.fromtimestamp(submission['submittedAt'] / 1000, timezone.utc).isoformat(), 'fields': safe_fields(fields)})
            after = body.get('paging', {}).get('next', {}).get('after')
            if not after: break
        else:
            raise ValueError('Form submissions truncated')
    return observations


def bigquery_sql(table):
    if not re.fullmatch(r'[a-zA-Z0-9_-]+\.[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+', table):
        raise ValueError('Expected project.dataset.table or view')
    return f'''SELECT event_ts, event_name, test_run_id, submission_id, event_id,
      utm_source, utm_medium, utm_campaign, form_id, hubspot_form_id, lead_type,
      gclid IS NOT NULL AS has_gclid
      FROM `{table}` WHERE test_run_id = @run_id AND event_ts >= @started_at
      ORDER BY event_ts'''


def collect_bigquery(evidence, config):
    from google.cloud import bigquery
    client = bigquery.Client(project=config['project'])
    job_config = bigquery.QueryJobConfig(
        maximum_bytes_billed=config.get('maximum_bytes_billed', 100_000_000),
        query_parameters=[bigquery.ScalarQueryParameter('run_id', 'STRING', evidence['run_id']),
                          bigquery.ScalarQueryParameter('started_at', 'TIMESTAMP', timestamp(evidence['started_at']))])
    job = client.query(bigquery_sql(config['table']), job_config=job_config, location=config.get('location', 'US'))
    rows = job.result(timeout=config.get('timeout_seconds', 60))
    observations = []
    for index, row in enumerate(rows):
        if index >= config.get('max_records', 10000):
            raise ValueError('BigQuery evidence exceeds record bound')
        data = dict(row)
        observations.append({'run_id': evidence['run_id'], 'source': 'ga4', 'event': data.pop('event_name'), 'record_id': str(index), 'occurred_at': data.pop('event_ts').isoformat(), 'fields': safe_fields(data)})
    return observations


async def collect(evidence, config, http=None):
    validate(evidence, 'evidence')
    async with httpx.AsyncClient(timeout=30) as default_http:
        for source, settings in config.items():
            if source not in ('hubspot', 'ga4'):
                raise ValueError(f'Unsupported collector: {source}')
            # Replace the source snapshot; never append the same query twice.
            evidence['observations'] = [o for o in evidence['observations'] if o['source'] != source]
            try:
                rows = await collect_hubspot(evidence, settings, http or default_http) if source == 'hubspot' else await asyncio.to_thread(collect_bigquery, evidence, settings)
                evidence['observations'].extend(rows)
                evidence['sources'][source] = {'status': 'complete', 'checked_at': utc_now()}
            except Exception as exc:
                evidence['sources'][source] = {'status': 'error', 'checked_at': utc_now(), 'error_code': type(exc).__name__}
    validate(evidence, 'evidence')
    return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()
    path = Path(args.evidence)
    evidence = asyncio.run(collect(json.loads(path.read_text()), yaml.safe_load(Path(args.config).read_text())))
    path.write_text(json.dumps(evidence, indent=2) + '\n')
    raise SystemExit(1 if any(s['status'] == 'error' for s in evidence['sources'].values()) else 0)


if __name__ == '__main__':
    main()
