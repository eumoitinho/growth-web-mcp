import httpx
import pytest
from growth_qa.collect import collect, collect_hubspot, bigquery_sql, safe_fields


def evidence():
    return {'version':1, 'run_id':'run-1', 'journey_id':'demo', 'started_at':'2026-01-01T00:00:00Z', 'sources':{}, 'observations':[]}


async def test_crm_correlation_and_pii_removal(monkeypatch):
    monkeypatch.setenv('QA_HUBSPOT_TOKEN', 'test')
    def handler(request):
        assert request.headers['Authorization'] == 'Bearer test'
        if 'search' in str(request.url):
            return httpx.Response(200, json={'results':[{'id':'123','updatedAt':'2026-01-01T00:00:01Z','properties':{'test_run_id':'run-1','email':'private@example.com','submission_id':'sub-1'}}]})
        return httpx.Response(200, json={'results':[{'submittedAt':1767225601000,'values':[{'name':'test_run_id','value':'run-1'},{'name':'email','value':'private@example.com'}]}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rows = await collect_hubspot(evidence(), {'form_ids':['form-1']}, client)
    assert len(rows) == 2
    assert all('email' not in row['fields'] for row in rows)


async def test_failed_or_truncated_query_never_becomes_complete(monkeypatch):
    monkeypatch.setenv('QA_HUBSPOT_TOKEN', 'test')
    for response in [httpx.Response(403), httpx.Response(200,json={'results':[],'paging':{'next':{'after':'1'}}})]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: response)) as client:
            result = await collect(evidence(), {'hubspot':{'max_pages':1}}, client)
            assert result['sources']['hubspot']['status'] == 'error'


def test_bigquery_identifier_and_field_allowlist():
    with pytest.raises(ValueError): bigquery_sql('p.d.t`; DROP TABLE foo')
    assert '@run_id' in bigquery_sql('project.dataset.view')
    assert safe_fields({'email':'x', 'utm_source':'google', 'cookies':{}, 'has_gclid':True}) == {'utm_source':'google','has_gclid':True}
