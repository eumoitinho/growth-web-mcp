"""Validate journey contracts against correlated, timestamped evidence."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import jsonschema
import yaml

ROOT = Path(__file__).resolve().parent.parent


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Timestamps must have a timezone')
    return result


def validate(value, kind):
    schema = json.loads((ROOT / 'schemas' / f'{kind}.schema.json').read_text())
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(value)
    if kind == 'journeys':
        ids = [j['id'] for j in value['journeys']]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate journey id')
        for journey in value['journeys']:
            ids = [e['id'] for e in journey['expectations']]
            if len(ids) != len(set(ids)):
                raise ValueError('Duplicate expectation id')
            for e in journey['expectations']:
                if e['min_count'] > e['max_count']:
                    raise ValueError('min_count exceeds max_count')


def reconcile(suite, evidence, now=None):
    validate(suite, 'journeys')
    validate(evidence, 'evidence')
    now = now or datetime.now(timezone.utc)
    started = timestamp(evidence['started_at'])
    if now < started:
        raise ValueError('Run starts in the future')
    journey = next((j for j in suite['journeys'] if j['id'] == evidence['journey_id']), None)
    if journey is None:
        raise ValueError('Unknown journey')
    for observation in evidence['observations']:
        if observation['run_id'] != evidence['run_id']:
            raise ValueError('Mixed run ids in evidence')
        if not started <= timestamp(observation['occurred_at']) <= now:
            raise ValueError('Observation outside run time window')
    for source in evidence['sources'].values():
        if not started <= timestamp(source['checked_at']) <= now:
            raise ValueError('Source check outside run time window')
    results = []
    for rule in journey['expectations']:
        item = {'id': rule['id'], 'source': rule['source'], 'status': 'PENDING', 'reason': 'Awaiting evidence', 'count': 0}
        source = evidence['sources'].get(rule['source'])
        rows = [o for o in evidence['observations'] if o['source'] == rule['source'] and o['event'] == rule['event']]
        item['count'] = len(rows)
        deadline = rule['deadline_seconds']
        elapsed = (now - started).total_seconds()
        if not rule.get('applicable', True):
            item.update(status='NOT_APPLICABLE', reason='Excluded by journey contract')
        elif source and source['status'] == 'error':
            item.update(status='ERROR', reason='Evidence source unavailable')
        elif len(rows) > rule['max_count']:
            item.update(status='FAIL', reason='Too many matching records')
        elif any(any(row['fields'].get(k) != v for k, v in rule.get('fields', {}).items()) or
                 any(row['fields'].get(k) in (None, '') for k in rule.get('required_fields', [])) for row in rows):
            item.update(status='FAIL', reason='Required fields missing or different')
        elif any((timestamp(row['occurred_at']) - started).total_seconds() > deadline for row in rows):
            item.update(status='FAIL', reason='Record arrived after deadline')
        elif source and source['status'] == 'complete' and len(rows) >= rule['min_count'] and (
                rule['max_count'] > 0 or (timestamp(source['checked_at']) - started).total_seconds() >= deadline):
            item.update(status='PASS', reason='Count and fields match contract')
        elif elapsed >= deadline:
            # Require a fresh query before concluding that data is missing.
            fresh = source and (timestamp(source['checked_at']) - started).total_seconds() >= deadline
            item.update(status='FAIL' if fresh else 'ERROR', reason='Missing records after deadline' if fresh else 'Evidence source not checked after deadline')
        results.append(item)
    statuses = {r['status'] for r in results}
    status = next((s for s in ['FAIL', 'ERROR', 'PENDING'] if s in statuses), 'PASS')
    if statuses == {'NOT_APPLICABLE'}:
        status = 'NOT_APPLICABLE'
    return {'version': 1, 'run_id': evidence['run_id'], 'journey_id': journey['id'], 'status': status, 'checks': results}


def write_report(report, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    lines = ['# Journey validation', '', f"Status: **{report['status']}**", '', '| Check | Source | Status | Count | Reason |', '|---|---|---|---|---|']
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    for check in report['checks']:
        lines.append('| ' + ' | '.join(cell(check[k]) for k in ['id', 'source', 'status', 'count', 'reason']) + ' |')
    (directory / 'report.md').write_text('\n'.join(lines) + '\n')
    suite = ET.Element('testsuite', name=report['journey_id'], tests=str(len(report['checks'])))
    for check in report['checks']:
        case = ET.SubElement(suite, 'testcase', name=check['id'], classname=check['source'])
        if check['status'] in ('FAIL', 'ERROR'):
            ET.SubElement(case, 'failure' if check['status'] == 'FAIL' else 'error', message=check['reason'])
        elif check['status'] in ('PENDING', 'NOT_APPLICABLE'):
            ET.SubElement(case, 'skipped', message=check['reason'])
    ET.ElementTree(suite).write(directory / 'junit.xml', encoding='utf-8', xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', required=True)
    parser.add_argument('--evidence', required=True)
    parser.add_argument('--out', default='artifacts/reconciliation')
    args = parser.parse_args()
    report = reconcile(yaml.safe_load(Path(args.suite).read_text()), json.loads(Path(args.evidence).read_text()))
    write_report(report, args.out)
    print(report['status'])
    raise SystemExit({'PASS': 0, 'FAIL': 1, 'ERROR': 1, 'PENDING': 2, 'NOT_APPLICABLE': 3}[report['status']])


if __name__ == '__main__':
    main()
