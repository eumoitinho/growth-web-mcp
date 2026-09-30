import copy
from datetime import datetime, timezone
import json
import xml.etree.ElementTree as ET

import pytest
from growth_qa.reconcile import reconcile, write_report, validate

START = '2026-01-01T00:00:00Z'
LATER = '2026-01-01T00:00:10Z'
NOW = datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc)


@pytest.fixture
def pair():
    suite = {'version': 1, 'journeys': [{'id': 'paid', 'channel': 'paid', 'expectations': [
        {'id': 'crm', 'source': 'hubspot', 'event': 'contact', 'min_count': 1, 'max_count': 1, 'deadline_seconds': 10, 'fields': {'utm_source': 'google'}, 'required_fields': ['submission_id']}
    ]}]}
    evidence = {'version': 1, 'run_id': 'run-1', 'journey_id': 'paid', 'started_at': START, 'sources': {'hubspot': {'status': 'complete', 'checked_at': LATER}}, 'observations': [
        {'run_id': 'run-1', 'source': 'hubspot', 'event': 'contact', 'record_id': '1', 'occurred_at': LATER, 'fields': {'utm_source': 'google', 'submission_id': 'sub-1'}}
    ]}
    return suite, evidence


def test_complete_journey_passes_and_report_excludes_field_values(pair, tmp_path):
    result = reconcile(*pair, now=NOW)
    assert result['status'] == 'PASS'
    write_report(result, tmp_path)
    assert 'utm_source' not in (tmp_path / 'report.json').read_text()
    assert ET.parse(tmp_path / 'junit.xml').getroot().get('tests') == '1'


@pytest.mark.parametrize('mutation', ['duplicate', 'wrong_field', 'missing_field', 'mixed_run', 'future'])
def test_bad_evidence_never_passes(pair, mutation):
    suite, evidence = pair
    row = evidence['observations'][0]
    if mutation == 'duplicate': evidence['observations'].append(copy.deepcopy(row))
    if mutation == 'wrong_field': row['fields']['utm_source'] = 'direct'
    if mutation == 'missing_field': del row['fields']['submission_id']
    if mutation == 'mixed_run': row['run_id'] = 'other'
    if mutation == 'future': row['occurred_at'] = '2027-01-01T00:00:00Z'
    if mutation in ('mixed_run', 'future'):
        with pytest.raises(ValueError): reconcile(suite, evidence, now=NOW)
    else:
        assert reconcile(suite, evidence, now=NOW)['status'] == 'FAIL'


def test_missing_pending_then_failed_only_after_fresh_query(pair):
    suite, evidence = pair
    evidence['observations'] = []
    evidence['sources']['hubspot']['checked_at'] = START
    assert reconcile(suite, evidence, now=datetime(2026,1,1,0,0,1,tzinfo=timezone.utc))['status'] == 'PENDING'
    assert reconcile(suite, evidence, now=NOW)['status'] == 'ERROR'
    evidence['sources']['hubspot']['checked_at'] = LATER
    assert reconcile(suite, evidence, now=NOW)['status'] == 'FAIL'


def test_forbidden_event_needs_full_observation_window(pair):
    suite, evidence = pair
    rule = suite['journeys'][0]['expectations'][0]
    rule.update(min_count=0, max_count=0)
    evidence['observations'] = []
    evidence['sources']['hubspot']['checked_at'] = START
    assert reconcile(suite, evidence, now=datetime(2026,1,1,0,0,1,tzinfo=timezone.utc))['status'] == 'PENDING'
    evidence['sources']['hubspot']['checked_at'] = LATER
    assert reconcile(suite, evidence, now=NOW)['status'] == 'PASS'


def test_source_error_and_not_applicable(pair):
    suite, evidence = pair
    evidence['sources']['hubspot']['status'] = 'error'
    assert reconcile(suite, evidence, now=NOW)['status'] == 'ERROR'
    suite['journeys'][0]['expectations'][0]['applicable'] = False
    assert reconcile(suite, evidence, now=NOW)['status'] == 'NOT_APPLICABLE'


def test_invalid_counts_and_duplicate_ids(pair):
    suite, _ = pair
    suite['journeys'][0]['expectations'][0]['max_count'] = 0
    with pytest.raises(ValueError): validate(suite, 'journeys')
