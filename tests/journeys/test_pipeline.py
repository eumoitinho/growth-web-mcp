import json
from types import SimpleNamespace
import pytest
import yaml
from growth_qa.pipeline import execute


async def test_resume_reconciles_without_replaying_submission(tmp_path):
    suite={'version':1,'journeys':[{'id':'demo','channel':'test','expectations':[{'id':'lead','source':'hubspot','event':'contact','min_count':1,'max_count':1,'deadline_seconds':10}]}]}
    suite_path=tmp_path/'suite.yaml'
    suite_path.write_text(yaml.safe_dump(suite))
    evidence={'version':1,'run_id':'one','journey_id':'demo','started_at':'2026-01-01T00:00:00Z','sources':{'hubspot':{'status':'complete','checked_at':'2026-01-01T00:00:01Z'}},'observations':[{'run_id':'one','source':'hubspot','event':'contact','record_id':'1','occurred_at':'2026-01-01T00:00:01Z','fields':{}}]}
    (tmp_path/'evidence.json').write_text(json.dumps(evidence))
    args=SimpleNamespace(out=str(tmp_path),suite=str(suite_path),resume=True,collectors=None)
    assert await execute(args)==0
    assert (tmp_path/'junit.xml').exists()
    args.resume=False
    with pytest.raises(ValueError,match='already exists'):await execute(args)
