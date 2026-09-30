from growth_qa.monitor import summarize


def test_missing_and_pending_journeys_never_green():
    suite={'journeys':[{'id':'paid'},{'id':'organic'}]}
    report=summarize(suite,[{'journey_id':'paid','status':'PASS'}])
    assert report['coverage']==0.5
    assert report['pass_rate']==0.5
    assert not report['healthy']
    report=summarize(suite,[{'journey_id':'paid','status':'PASS'},{'journey_id':'organic','status':'PENDING'}])
    assert report['coverage']==1
    assert not report['healthy']
    report=summarize(suite,[{'journey_id':'paid','status':'PASS'},{'journey_id':'organic','status':'PASS'}])
    assert report['healthy']


def test_latest_report_wins_and_empty_suite_not_healthy():
    assert not summarize({'journeys':[]},[])['healthy']
    result=summarize({'journeys':[{'id':'paid'}]},[{'journey_id':'paid','status':'PASS'},{'journey_id':'paid','status':'FAIL'}])
    assert not result['healthy']
