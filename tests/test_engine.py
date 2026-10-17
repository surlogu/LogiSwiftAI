import sqlite3
from engine import SCENARIOS, connect, recover, strategy_order

def test_scenarios():
    c=connect(':memory:')
    results={s:recover('TEST',s,c) for s in SCENARIOS}
    assert results['Traffic delay']['status']=='RECOVERED'
    assert results['Traffic delay']['attempts']==2
    assert results['Vehicle breakdown']['status']=='RECOVERED'
    assert results['AI API outage']['status']=='RECOVERED'
    assert results['Unrecoverable incident']['status']=='ESCALATED'
    assert all(r['attempts']<=3 for r in results.values())

def test_retry_limit():
    c=connect(':memory:')
    result=recover('TEST','Traffic delay',c,max_attempts=1)
    assert result['status']=='ESCALATED'
    assert result['attempts']==1

def test_feedback_recorded():
    c=connect(':memory:')
    recover('TEST','Traffic delay',c)
    assert strategy_order('TRAFFIC',c)[0][0]=='alternate_route_B'
    assert c.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]==1
