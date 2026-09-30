import httpx
import pytest
from growth_meta import server


def client_factory(monkeypatch, handler):
    real = httpx.AsyncClient
    monkeypatch.setattr(server.httpx, 'AsyncClient', lambda **kwargs: real(transport=httpx.MockTransport(handler), **kwargs))
    monkeypatch.setenv('META_ACCESS_TOKEN', 'test-token')


async def test_pagination_keeps_auth_and_reports_truncation(monkeypatch):
    requests = []
    def handler(request):
        requests.append(request)
        assert request.headers['Authorization'] == 'Bearer test-token'
        return httpx.Response(200, json={'data': [{'id': str(len(requests))}], 'paging': {'next': server.GRAPH_URL + '/items?after=next'}})
    client_factory(monkeypatch, handler)
    result = await server._get('items', max_pages=2)
    assert len(result['data']) == 2
    assert result['truncated'] is True
    assert len(requests) == 2


@pytest.mark.parametrize('code', [401, 403, 429, 500])
async def test_api_errors_are_not_success(monkeypatch, code):
    client_factory(monkeypatch, lambda request: httpx.Response(code, json={'error': {'message': 'test failure', 'code': code}}))
    with pytest.raises(server.MetaError):
        await server._get('items')


async def test_missing_credentials(monkeypatch):
    monkeypatch.delenv('META_ACCESS_TOKEN', raising=False)
    with pytest.raises(server.MetaError, match='not set'):
        await server._get('items')


async def test_timeout_propagates(monkeypatch):
    def handler(request):
        raise httpx.ReadTimeout('timeout', request=request)
    client_factory(monkeypatch, handler)
    with pytest.raises(httpx.ReadTimeout):
        await server._get('items')


async def test_pagination_cannot_forward_credentials_to_another_host(monkeypatch):
    client_factory(monkeypatch,lambda r:httpx.Response(200,json={'data':[],'paging':{'next':'https://example.invalid/steal'}}))
    with pytest.raises(server.MetaError,match='Unsafe'):
        await server._get('items',max_pages=2)


async def test_destinations_and_campaign_attribution(monkeypatch):
    from unittest.mock import AsyncMock
    monkeypatch.setattr(server,'_get',AsyncMock(return_value={'data':[{'id':'ad','creative':{'link_url':'https://example.com/?utm_source=facebook','url_tags':'utm_medium=paid_social&utm_campaign=qa'}}], 'truncated':False}))
    result=await server.list_ad_destinations('123')
    destination=result['ads'][0]['destinations'][0]
    assert destination['missing_utm']==[]
    assert destination['utm']['utm_campaign']=='qa'
    assert destination['host']=='example.com'


async def test_lead_forms_never_return_page_token(monkeypatch):
    from unittest.mock import AsyncMock
    mock=AsyncMock(side_effect=[{'access_token':'private-token'},{'data':[{'id':'form','leads_count':2}],'truncated':False}])
    monkeypatch.setattr(server,'_get',mock)
    result=await server.list_leadgen_forms('page')
    assert 'private-token' not in str(result)
    assert mock.call_args.kwargs['token']=='private-token'
