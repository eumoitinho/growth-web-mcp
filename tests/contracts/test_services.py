from types import SimpleNamespace
import pytest
from growth_qa.services import assert_result, check_service, expand


def test_mcp_errors_and_bad_payloads_fail():
    with pytest.raises(AssertionError):
        assert_result(SimpleNamespace(isError=True))
    valid = SimpleNamespace(isError=False, content=[SimpleNamespace(type='text', text='{"data": []}')])
    assert_result(valid, {'type': 'object', 'required': ['data']})
    with pytest.raises(Exception):
        assert_result(valid, {'type': 'array'})


async def test_missing_credentials_are_blocked(monkeypatch):
    monkeypatch.delenv('QA_MISSING', raising=False)
    assert (await check_service({'name': 'ga4', 'url': '${QA_MISSING}'}))['status'] == 'BLOCKED'


def test_expansion_is_explicit(monkeypatch):
    monkeypatch.setenv('QA_VALUE', 'safe')
    assert expand({'a': ['${QA_VALUE}'], 'literal': '$QA_VALUE'}) == {'a': ['safe'], 'literal': '$QA_VALUE'}
