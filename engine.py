"""Deterministic, auditable logistics recovery agent (simulation only)."""
import json
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).with_name('logiswift.db')
SCENARIOS = {
    'Traffic delay': {'failure': 'TRAFFIC', 'eta': 95, 'deadline': 65},
    'Vehicle breakdown': {'failure': 'BREAKDOWN', 'eta': 120, 'deadline': 85},
    'Driver unavailable': {'failure': 'DRIVER', 'eta': 90, 'deadline': 80},
    'AI API outage': {'failure': 'AI_TIMEOUT', 'eta': 75, 'deadline': 90},
    'Capacity overload': {'failure': 'CAPACITY', 'eta': 100, 'deadline': 90},
    'Unrecoverable incident': {'failure': 'NO_CAPACITY', 'eta': 160, 'deadline': 60},
}
ACTIONS = {
    'TRAFFIC': [('alternate_route_A', -10), ('alternate_route_B', -38)],
    'BREAKDOWN': [('replacement_vehicle', -48)],
    'DRIVER': [('backup_driver', -20)],
    'AI_TIMEOUT': [('rule_based_fallback', -1)],
    'CAPACITY': [('split_load', -25)],
    'NO_CAPACITY': [('escalate_to_dispatch', 0)],
}

def connect(path=DB_PATH):
    conn = sqlite3.connect(str(path))
    conn.execute('CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, shipment_id TEXT, scenario TEXT, status TEXT, attempts INTEGER, latency_ms REAL, timeline TEXT)')
    conn.commit()
    return conn

def sample_shipments():
    cities = [('Chennai','Bengaluru'),('Mumbai','Pune'),('Hyderabad','Vijayawada'),('Delhi','Jaipur'),('Coimbatore','Kochi')]
    result=[]
    for i in range(1,21):
        src,dst=cities[(i-1)%len(cities)]
        scenario=list(SCENARIOS)[(i-1)%len(SCENARIOS)]
        result.append({'Shipment':f'LS{1000+i}', 'Origin':src,'Destination':dst,'Priority':'High' if i%4==0 else 'Normal','Status':'At Risk' if i%3==0 else 'In Transit','Scenario':scenario})
    return result

def strategy_order(failure, conn):
    candidates=ACTIONS[failure][:]
    # Historical verified successes are favored, while untried strategies retain original order.
    history=conn.execute("SELECT timeline FROM incidents WHERE status='RECOVERED'").fetchall()
    counts={name:0 for name,_ in candidates}
    for (raw,) in history:
        for event in json.loads(raw):
            if event.get('verified') is True and event.get('action') in counts:
                counts[event['action']]+=1
    return sorted(candidates,key=lambda a:-counts[a[0]])

def recover(shipment_id, scenario, conn=None, max_attempts=3):
    if scenario not in SCENARIOS: raise ValueError('Unknown scenario')
    if max_attempts < 1: raise ValueError('max_attempts must be positive')
    own=conn is None
    conn=conn or connect()
    start=time.perf_counter()
    cfg=SCENARIOS[scenario]
    eta=cfg['eta']; deadline=cfg['deadline']; failure=cfg['failure']
    timeline=[{'stage':'OBSERVE','detail':f'{failure} detected; ETA {eta}m, deadline {deadline}m'}, {'stage':'REASON','detail':'Choose feasible strategy and verify against deadline'}]
    status='ESCALATED'; attempts=0
    for name, improvement in strategy_order(failure,conn)[:max_attempts]:
        attempts+=1
        if name=='rule_based_fallback':
            # AI failure does not mean logistics failure: deterministic fallback is healthy.
            verified=True
            detail='AI unavailable; validated deterministic engine activated'
        elif name=='escalate_to_dispatch':
            verified=False
            detail='No safe capacity available; human escalation required'
        else:
            eta+=improvement
            verified=eta<=deadline
            detail=f'New ETA {eta}m vs deadline {deadline}m'
        timeline.append({'stage':'ACT + VERIFY','action':name,'attempt':attempts,'verified':verified,'detail':detail})
        if verified:
            status='RECOVERED'; break
    timeline.append({'stage':'LEARN','detail':'Verified strategy recorded for future ranking' if status=='RECOVERED' else 'No verified recovery; human review required'})
    latency=round((time.perf_counter()-start)*1000,3)
    conn.execute('INSERT INTO incidents (created_at,shipment_id,scenario,status,attempts,latency_ms,timeline) VALUES (?,?,?,?,?,?,?)', (datetime.now(timezone.utc).isoformat(),shipment_id,scenario,status,attempts,latency,json.dumps(timeline)))
    conn.commit()
    result={'shipment_id':shipment_id,'scenario':scenario,'status':status,'attempts':attempts,'latency_ms':latency,'timeline':timeline,'final_eta':eta,'deadline':deadline}
    if own: conn.close()
    return result

def history(conn=None):
    own=conn is None
    conn=conn or connect()
    rows=conn.execute('SELECT id,created_at,shipment_id,scenario,status,attempts,latency_ms,timeline FROM incidents ORDER BY id DESC').fetchall()
    result=[dict(zip(('id','created_at','shipment_id','scenario','status','attempts','latency_ms','timeline'),row)) for row in rows]
    if own:conn.close()
    return result
