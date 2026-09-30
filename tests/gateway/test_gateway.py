import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from growth_gateway import server


@pytest.mark.parametrize('claims,allowed', [
    ({'email': 'qa@example.com', 'email_verified': True}, True),
    ({'email': 'QA@EXAMPLE.COM', 'email_verified': 'true'}, True),
    ({'email': 'qa@evil-example.com', 'email_verified': True}, False),
    ({'email': 'qa@example.com', 'email_verified': False}, False),
    ({}, False),
])
async def test_domain_verifier(claims, allowed):
    inner = SimpleNamespace(required_scopes=[], verify_token=AsyncMock(return_value=SimpleNamespace(claims=claims)))
    verifier = server.DomainVerifier(inner, {'example.com'})
    assert ((await verifier.verify_token('test')) is not None) == allowed
    inner.verify_token.return_value = None
    assert await verifier.verify_token('expired') is None


async def test_browser_sessions_isolated_and_expired(monkeypatch):
    user = ['one@example.com']
    now = [0]
    created = []
    class Client:
        def __init__(self, transport):
            self.connected = False
            self.closed = False
            created.append(self)
        async def __aenter__(self):
            self.connected = True
            return self
        def is_connected(self):
            return self.connected
        async def __aexit__(self, *args):
            self.connected = False
            self.closed = True
    monkeypatch.setattr(server, '_current_email', lambda: user[0])
    monkeypatch.setattr(server.time, 'time', lambda: now[0])
    monkeypatch.setattr(server, 'ProxyClient', Client)
    factory = server._per_user_factory('http://localhost/mcp', None)
    first = await factory()
    assert await factory() is first
    user[0] = 'two@example.com'
    assert await factory() is not first
    now[0] = server.STATEFUL_IDLE_SECONDS + 1
    await factory()
    assert first.closed
    assert len(created) == 3


async def test_audit_marks_mcp_error_as_failure(monkeypatch, capsys):
    monkeypatch.setattr(server, '_current_email', lambda: 'test')
    context = SimpleNamespace(message=SimpleNamespace(name='probe'))
    from fastmcp.tools.base import ToolResult
    result = ToolResult(content=[], is_error=True)
    assert await server.AuditLog().on_call_tool(context, AsyncMock(return_value=result)) is result
    assert json.loads(capsys.readouterr().out)['ok'] is False
