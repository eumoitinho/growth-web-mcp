import copy
from pathlib import Path
import yaml
import pytest
from growth_qa.browser import run_browser, validate_target
from growth_qa.collect import utc_now
from growth_qa.reconcile import reconcile
from .fixture_server import Fixture

SUITE = yaml.safe_load(Path('config/journeys.example.yaml').read_text())


@pytest.mark.parametrize('journey_id,fault,expected', [
    ('organic-demo',None,'PASS'), ('google-ads-demo',None,'PASS'), ('meta-ads-demo',None,'PASS'),
    ('consent-denied',None,'PASS'), ('form-error',None,'PASS'),
    ('duplicate-submit',None,'PASS'), ('cross-subdomain',None,'PASS'), ('return-direct',None,'PASS'), ('existing-contact',None,'PASS'), ('google-ads-demo','campaign-loss','FAIL'),
    ('duplicate-submit','duplicate','FAIL'),
])
async def test_browser_through_crm_reference_app(monkeypatch,journey_id,fault,expected):
    monkeypatch.setenv('QA_TEST_EMAIL','synthetic@example.invalid')
    monkeypatch.setenv('QA_EXISTING_CONTACT_EMAIL','existing@example.invalid')
    suite = copy.deepcopy(SUITE)
    journey = next(j for j in suite['journeys'] if j['id']==journey_id)
    if fault: journey['browser']['query']['fault']=fault
    if journey_id in ('consent-denied','form-error'): journey['browser']['settle_ms']=2200
    with Fixture() as fixture:
        settings={'environment':'test','base_url':fixture.url,'allowed_origins':[fixture.url,fixture.url.replace('127.0.0.1','localhost')],'network_rules':[{'origin':fixture.url,'path':'/g/collect'},{'origin':fixture.url.replace('127.0.0.1','localhost'),'path':'/g/collect'}]}
        evidence=await run_browser(suite,journey_id,settings,allow_submissions=True)
        evidence['observations'].extend(fixture.rows)
        for source in ('hubspot','ga4'):evidence['sources'][source]={'status':'complete','checked_at':utc_now()}
        if journey_id=='existing-contact':
            assert next(r for r in fixture.rows if r['event']=='contact')['record_id']=='existing-contact-id'
        result = reconcile(suite,evidence)
        assert result['status']==expected, result
        if fault=='campaign-loss':
            assert any(c['source']=='hubspot' and c['status']=='FAIL' for c in result['checks'])


def test_production_and_unapproved_targets_rejected():
    settings={'environment':'production','base_url':'https://example.com','allowed_origins':['https://example.com']}
    with pytest.raises(ValueError):validate_target(settings,True)
    settings['environment']='test'
    with pytest.raises(ValueError):validate_target(settings,False)
    settings['allowed_origins']=['https://other.example.com']
    with pytest.raises(ValueError):validate_target(settings,True)
