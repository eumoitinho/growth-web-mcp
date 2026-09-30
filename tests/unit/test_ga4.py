from unittest.mock import Mock

import pytest
from growth_ga4 import extra_tools


@pytest.mark.parametrize('tool,method,alpha', [
    ('list_data_streams', 'list_data_streams', False),
    ('list_key_events', 'list_key_events', False),
    ('list_channel_groups', 'list_channel_groups', True),
])
async def test_admin_pagers_are_fully_consumed(monkeypatch, tool, method, alpha):
    client = Mock()
    getattr(client, method).return_value = iter([{'id': 'a'}, {'id': 'b'}])
    monkeypatch.setattr(extra_tools, 'create_admin_alpha_api_client' if alpha else 'create_admin_api_client', lambda: client)
    monkeypatch.setattr(extra_tools, 'proto_to_dict', lambda value: value)
    assert await getattr(extra_tools, tool)('properties/123') == [{'id': 'a'}, {'id': 'b'}]
    getattr(client, method).assert_called_once_with(parent='properties/123')


async def test_enhanced_measurement_resource_and_failure(monkeypatch):
    client = Mock()
    client.get_enhanced_measurement_settings.return_value = {'formInteractionsEnabled': False}
    monkeypatch.setattr(extra_tools, 'create_admin_alpha_api_client', lambda: client)
    monkeypatch.setattr(extra_tools, 'proto_to_dict', lambda value: value)
    assert await extra_tools.get_enhanced_measurement_settings('123', '456') == {'formInteractionsEnabled': False}
    client.get_enhanced_measurement_settings.assert_called_once_with(name='properties/123/dataStreams/456/enhancedMeasurementSettings')
    client.get_enhanced_measurement_settings.side_effect = PermissionError('denied')
    with pytest.raises(PermissionError):
        await extra_tools.get_enhanced_measurement_settings('123', '456')


async def test_retention_uses_property_resource(monkeypatch):
    client = Mock()
    client.get_data_retention_settings.return_value = {'eventDataRetention': 'FOURTEEN_MONTHS'}
    monkeypatch.setattr(extra_tools, 'create_admin_api_client', lambda: client)
    monkeypatch.setattr(extra_tools, 'proto_to_dict', lambda value: value)
    assert (await extra_tools.get_data_retention_settings(123))['eventDataRetention'] == 'FOURTEEN_MONTHS'
    client.get_data_retention_settings.assert_called_once_with(name='properties/123/dataRetentionSettings')


async def test_asgi_health_and_unknown_route():
    import httpx
    from growth_ga4.server import app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        health=await client.get('/healthz')
        assert health.status_code==200
        assert health.json()['tools']>=5
        assert (await client.get('/unknown')).status_code==404
