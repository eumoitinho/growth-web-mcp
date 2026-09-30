import importlib.util
import os
from pathlib import Path
from unittest.mock import Mock

import pytest

os.environ['GOOGLE_ADS_MCP_TOOLS_CONFIG'] = str(Path('servers/google-ads/tools_config.yaml').resolve())
spec = importlib.util.spec_from_file_location('growth_ads', 'servers/google-ads/serve.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


def test_iam_transport_and_oauth_mode(monkeypatch):
    run = Mock()
    monkeypatch.setattr(server.mcp, 'run', run)
    monkeypatch.delenv('ADS_MCP_MODE', raising=False)
    server.main()
    assert run.call_args.kwargs['stateless_http'] is True
    assert run.call_args.kwargs['path'] == '/mcp'
    oauth = Mock()
    monkeypatch.setattr(server.upstream_server, 'run_server', oauth)
    monkeypatch.setenv('ADS_MCP_MODE', 'oauth')
    server.main()
    oauth.assert_called_once()


async def test_pinned_upstream_tools_and_argument_contract():
    from fastmcp import Client
    async with Client(server.mcp) as client:
        tools = {t.name: t for t in await client.list_tools()}
        assert {'search','list_accessible_customers'}.issubset(tools)
        schema = tools['search'].input_schema
        assert {'customer_id','fields','resource'}.issubset(schema['required'])
        with pytest.raises(Exception):
            await client.call_tool('search', {})


async def test_health():
    assert (await server.healthz(None)).status_code == 200
