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
    'Accident': {'failure': 'SAFETY', 'eta': 90, 'deadline': 65},
    'Customer unavailable': {'failure': 'CUSTOMER', 'eta': 60, 'deadline': 90},
    'Package damage': {'failure': 'PACKAGE', 'eta': 40, 'deadline': 120},
    'Wrong pickup address': {'failure': 'ADDRESS', 'eta': 75, 'deadline': 90},
}
ACTIONS = {
    'TRAFFIC': [('alternate_route_A', -10), ('alternate_route_B', -38)],
    'BREAKDOWN': [('replacement_vehicle', -48)],
    'DRIVER': [('backup_driver', -20)],
    'AI_TIMEOUT': [('rule_based_fallback', -1)],
    'CAPACITY': [('split_load', -25)],
    'NO_CAPACITY': [('escalate_to_dispatch', 0)],
    'SAFETY': [('escalate_to_dispatch', 0)],
    'CUSTOMER': [('customer_contact', -5)],
    'PACKAGE': [('escalate_to_dispatch', 0)],
    'ADDRESS': [('address_confirmation', -10)],
}
CITIES = ('Chennai', 'Bengaluru', 'Mumbai', 'Pune', 'Hyderabad', 'Vijayawada', 'Delhi', 'Jaipur', 'Coimbatore', 'Kochi')
DRIVERS = ('Ravi Kumar', 'Suresh', 'Meena', 'Arun')
VEHICLES = ('Bike 01', 'Bike 02', 'Van 01', 'Van 02')
DRIVER_ISSUES = {
    'No issue': None,
    'Traffic delay': 'Traffic delay',
    'Vehicle breakdown': 'Vehicle breakdown',
    'Driver unavailable': 'Driver unavailable',
    'Capacity overload': 'Capacity overload',
    'No safe recovery capacity': 'Unrecoverable incident',
    'Accident': 'Accident',
    'Customer unavailable': 'Customer unavailable',
    'Package damage': 'Package damage',
    'Wrong pickup address': 'Wrong pickup address',
}

def connect(path=DB_PATH):
    conn = sqlite3.connect(str(path))
    conn.execute('CREATE TABLE IF NOT EXISTS incidents (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, shipment_id TEXT, scenario TEXT, status TEXT, attempts INTEGER, latency_ms REAL, timeline TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS custom_shipments (shipment_id TEXT PRIMARY KEY, origin TEXT NOT NULL, destination TEXT NOT NULL, priority TEXT NOT NULL, status TEXT NOT NULL, scenario TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS shipment_likes (shipment_id TEXT PRIMARY KEY, liked INTEGER NOT NULL DEFAULT 1)')
    conn.execute('CREATE TABLE IF NOT EXISTS shipment_workflow (shipment_id TEXT PRIMARY KEY, vendor_name TEXT NOT NULL, driver_name TEXT, issue TEXT, agent_status TEXT, agent_action TEXT, vendor_decision TEXT NOT NULL DEFAULT \'No issue\', updated_at TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS drivers (driver_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, vehicle TEXT NOT NULL, available INTEGER NOT NULL DEFAULT 1, reliability REAL NOT NULL, eta_minutes INTEGER NOT NULL, current_location TEXT NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS workflow_events (id INTEGER PRIMARY KEY AUTOINCREMENT, shipment_id TEXT NOT NULL, event_type TEXT NOT NULL, actor TEXT NOT NULL, details TEXT NOT NULL, created_at TEXT NOT NULL)')
    shipment_columns = {row[1] for row in conn.execute('PRAGMA table_info(custom_shipments)')}
    if 'deadline' not in shipment_columns:
        conn.execute("ALTER TABLE custom_shipments ADD COLUMN deadline TEXT NOT NULL DEFAULT '18:00'")
    if 'package_type' not in shipment_columns:
        conn.execute("ALTER TABLE custom_shipments ADD COLUMN package_type TEXT NOT NULL DEFAULT 'general'")
    driver_seed = [('DRIVER_A','Ravi Kumar','Bike 01',1,.86,12,'T. Nagar'),('DRIVER_B','Suresh','Bike 02',1,.96,18,'Adyar'),('DRIVER_C','Meena','Van 01',1,.91,24,'Guindy'),('DRIVER_D','Arun','Van 02',1,.88,15,'Velachery')]
    conn.executemany('INSERT OR IGNORE INTO drivers VALUES (?,?,?,?,?,?,?)', driver_seed)
    workflow_columns = {row[1] for row in conn.execute('PRAGMA table_info(shipment_workflow)')}
    migrations = {
        'driver_id': 'TEXT', 'vehicle_name': 'TEXT', 'lifecycle_status': "TEXT NOT NULL DEFAULT 'CREATED'",
        'issue_description': "TEXT NOT NULL DEFAULT ''", 'recommendations_json': "TEXT NOT NULL DEFAULT '[]'",
        'selected_action': 'TEXT', 'selected_driver_id': 'TEXT', 'previous_driver_id': 'TEXT',
    }
    for column, declaration in migrations.items():
        if column not in workflow_columns:
            conn.execute(f'ALTER TABLE shipment_workflow ADD COLUMN {column} {declaration}')
    conn.execute("INSERT OR IGNORE INTO shipment_workflow (shipment_id, vendor_name, vendor_decision, updated_at) SELECT shipment_id, 'Vendor', 'No issue', ? FROM custom_shipments", (datetime.now(timezone.utc).isoformat(),))
    conn.commit()
    return conn

def sample_shipments(conn=None):
    own = conn is None
    conn = conn or connect()
    cities = [('Chennai','Bengaluru'),('Mumbai','Pune'),('Hyderabad','Vijayawada'),('Delhi','Jaipur'),('Coimbatore','Kochi')]
    result=[]
    for i in range(1,21):
        src,dst=cities[(i-1)%len(cities)]
        scenario=list(SCENARIOS)[(i-1)%len(SCENARIOS)]
        result.append({'Shipment':f'LS{1000+i}', 'Origin':src,'Destination':dst,'Priority':'High' if i%4==0 else 'Normal','Status':'At Risk' if i%3==0 else 'In Transit','Scenario':scenario})
    rows = conn.execute('SELECT shipment_id, origin, destination, priority, status, scenario FROM custom_shipments ORDER BY shipment_id').fetchall()
    result.extend(dict(zip(('Shipment','Origin','Destination','Priority','Status','Scenario'), row)) for row in rows)
    liked_ids = {row[0] for row in conn.execute('SELECT shipment_id FROM shipment_likes WHERE liked=1').fetchall()}
    for shipment in result:
        shipment['Liked'] = shipment['Shipment'] in liked_ids
    if own:
        conn.close()
    return result

def add_shipment(origin, destination, priority='Normal', status='Normal', vendor_name='Vendor', conn=None, deadline='18:00', package_type='general'):
    if origin not in CITIES or destination not in CITIES:
        raise ValueError('Choose an origin and destination from the supported cities')
    if origin == destination:
        raise ValueError('Origin and destination must be different')
    if priority not in ('Normal', 'High'):
        raise ValueError('Priority must be Normal or High')
    if status not in ('Normal', 'At Risk'):
        raise ValueError('Status must be Normal or At Risk')
    vendor_name = vendor_name.strip()
    if not vendor_name:
        raise ValueError('Enter a vendor name')
    try:
        datetime.strptime(deadline,'%H:%M')
    except (TypeError,ValueError):
        raise ValueError('Enter a deadline using 24-hour HH:MM time')
    package_type=package_type.strip()
    if not package_type:
        raise ValueError('Enter a package type')
    own = conn is None
    conn = conn or connect()
    existing = conn.execute('SELECT shipment_id FROM custom_shipments').fetchall()
    numbers = [int(row[0][2:]) for row in existing if row[0].startswith('LS') and row[0][2:].isdigit()]
    shipment_id = f'LS{max([1020, *numbers]) + 1}'
    conn.execute('INSERT INTO custom_shipments (shipment_id, origin, destination, priority, status, scenario, deadline, package_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (shipment_id, origin, destination, priority, status, 'Custom route',deadline,package_type))
    conn.execute('INSERT INTO shipment_workflow (shipment_id, vendor_name, vendor_decision, updated_at) VALUES (?, ?, ?, ?)', (shipment_id, vendor_name, 'No issue', datetime.now(timezone.utc).isoformat()))
    conn.execute("UPDATE shipment_workflow SET lifecycle_status='CREATED' WHERE shipment_id=?", (shipment_id,))
    record_workflow_event(conn,shipment_id,'CREATED',vendor_name,f'{origin} → {destination}')
    conn.commit()
    if own:
        conn.close()
    return shipment_id

def shipment_workflows(conn=None):
    own = conn is None
    conn = conn or connect()
    rows = conn.execute('''SELECT s.shipment_id, w.vendor_name, s.origin, s.destination, s.priority, s.status, s.deadline, s.package_type,
        w.driver_name, w.issue, w.agent_status, w.agent_action, w.vendor_decision, w.updated_at,
        w.driver_id, w.vehicle_name, w.lifecycle_status, w.issue_description, w.recommendations_json,
        w.selected_action, w.selected_driver_id, w.previous_driver_id
        FROM custom_shipments s JOIN shipment_workflow w ON w.shipment_id=s.shipment_id
        ORDER BY s.shipment_id DESC''').fetchall()
    columns = ('Shipment','Vendor','Origin','Destination','Priority','Status','Deadline','Package','Driver','Issue','Agent status','Agent decision','Vendor decision','Updated','Driver ID','Vehicle','Lifecycle','Issue description','Recommendations JSON','Selected action','Selected driver ID','Previous Driver ID')
    result = [dict(zip(columns, row)) for row in rows]
    for item in result:
        try: item['Recommendations'] = json.loads(item.pop('Recommendations JSON') or '[]')
        except json.JSONDecodeError: item['Recommendations'] = []
    if own:
        conn.close()
    return result

def driver_records(conn=None, available_only=False):
    own = conn is None
    conn = conn or connect()
    query = 'SELECT driver_id, name, vehicle, available, reliability, eta_minutes, current_location FROM drivers'
    if available_only: query += ' WHERE available=1'
    query += ' ORDER BY reliability DESC, eta_minutes ASC'
    result = [dict(zip(('driver_id','name','vehicle','available','reliability','eta_minutes','current_location'), row)) for row in conn.execute(query).fetchall()]
    if own: conn.close()
    return result

def record_workflow_event(conn, shipment_id, event_type, actor, details):
    conn.execute('INSERT INTO workflow_events(shipment_id,event_type,actor,details,created_at) VALUES (?,?,?,?,?)',
                 (shipment_id,event_type,actor,details,datetime.now(timezone.utc).isoformat()))

def workflow_events(conn=None, shipment_id=None):
    own=conn is None
    conn=conn or connect()
    if shipment_id:
        rows=conn.execute('SELECT id,shipment_id,event_type,actor,details,created_at FROM workflow_events WHERE shipment_id=? ORDER BY id DESC',(shipment_id,)).fetchall()
    else:
        rows=conn.execute('SELECT id,shipment_id,event_type,actor,details,created_at FROM workflow_events ORDER BY id DESC').fetchall()
    result=[dict(zip(('id','shipment_id','event','actor','details','created_at'),row)) for row in rows]
    if own: conn.close()
    return result

def assign_driver(shipment_id, driver_id, conn=None):
    own = conn is None
    conn = conn or connect()
    shipment = conn.execute('SELECT 1 FROM custom_shipments WHERE shipment_id=?', (shipment_id,)).fetchone()
    driver = conn.execute('SELECT driver_id,name,vehicle,available FROM drivers WHERE driver_id=?', (driver_id,)).fetchone()
    if not shipment or not driver:
        if own: conn.close()
        raise ValueError('Choose an existing shipment and driver')
    if not driver[3]:
        if own: conn.close()
        raise ValueError('That driver is already assigned to an active shipment')
    conn.execute('UPDATE drivers SET available=0 WHERE driver_id=?', (driver_id,))
    conn.execute('''UPDATE shipment_workflow SET driver_id=?, driver_name=?, vehicle_name=?, lifecycle_status='DRIVER_ASSIGNED', updated_at=? WHERE shipment_id=?''',
                 (driver[0],driver[1],driver[2],datetime.now(timezone.utc).isoformat(),shipment_id))
    conn.execute("UPDATE custom_shipments SET status='Driver assigned' WHERE shipment_id=?",(shipment_id,))
    record_workflow_event(conn,shipment_id,'DRIVER_ASSIGNED','Dispatcher',f"Assigned {driver[1]} with {driver[2]}")
    conn.commit()
    if own: conn.close()

def start_trip(shipment_id, driver_id, conn=None):
    return _set_trip_state(shipment_id, driver_id, 'IN_TRANSIT', conn)

def complete_delivery(shipment_id, driver_id, conn=None):
    return _set_trip_state(shipment_id, driver_id, 'DELIVERED', conn)

def _set_trip_state(shipment_id, driver_id, status, conn=None):
    own = conn is None
    conn = conn or connect()
    row = conn.execute('SELECT driver_id,lifecycle_status FROM shipment_workflow WHERE shipment_id=?',(shipment_id,)).fetchone()
    allowed = ('DRIVER_ASSIGNED','DRIVER_REASSIGNED','RECOVERY_APPROVED') if status=='IN_TRANSIT' else ('IN_TRANSIT',)
    if not row or row[0] != driver_id or row[1] not in allowed:
        if own: conn.close()
        raise ValueError('The shipment is not assigned to this driver or cannot make that status change yet')
    conn.execute('UPDATE shipment_workflow SET lifecycle_status=?, updated_at=? WHERE shipment_id=?',(status,datetime.now(timezone.utc).isoformat(),shipment_id))
    conn.execute('UPDATE custom_shipments SET status=? WHERE shipment_id=?',(status,shipment_id))
    if status=='DELIVERED': conn.execute('UPDATE drivers SET available=1 WHERE driver_id=?',(driver_id,))
    record_workflow_event(conn,shipment_id,status,driver_id,'Driver updated trip status')
    conn.commit()
    if own: conn.close()

def recovery_options(shipment_id, issue, conn=None):
    own = conn is None
    conn = conn or connect()
    workflow = conn.execute('SELECT driver_id FROM shipment_workflow WHERE shipment_id=?',(shipment_id,)).fetchone()
    options=[]
    if issue in ('Vehicle breakdown','Driver unavailable'):
        current_id = workflow[0] if workflow else None
        rows=conn.execute('SELECT driver_id,name,vehicle,reliability,eta_minutes,current_location FROM drivers WHERE available=1 AND driver_id != ? ORDER BY reliability DESC,eta_minutes ASC',(current_id,)).fetchall()
        for rank,row in enumerate(rows[:3],1):
            options.append({'id':f"replace:{row[0]}",'action':'Reassign to '+row[1],'driver_id':row[0],'vehicle':row[2],
                'reason':f"Reliability {row[3]:.0%}; estimated arrival {row[4]} min from {row[5]}.",'rank':rank,'source':'Rules-based'})
    elif issue=='Traffic delay':
        options=[{'id':'alternate_route_B','action':'Google alternate route B','vehicle':None,'reason':'Shorter simulated ETA; confirm on the live road map.','rank':1,'source':'Rules-based'},
                 {'id':'alternate_route_A','action':'Google alternate route A','vehicle':None,'reason':'Backup road route if the preferred alternative is unsuitable.','rank':2,'source':'Rules-based'}]
    elif issue=='Capacity overload':
        options=[{'id':'split_load','action':'Split shipment across vehicles','vehicle':'Van 01','reason':'Distributes load and preserves full delivery.','rank':1,'source':'Rules-based'},
                 {'id':'add_capacity_vehicle','action':'Add capacity vehicle','vehicle':'Van 02','reason':'Keep the shipment together with additional capacity.','rank':2,'source':'Rules-based'}]
    elif issue=='Customer unavailable':
        options=[{'id':'contact_customer','action':'Record simulated customer contact','vehicle':None,'reason':'Confirm a safe delivery handoff before resuming the trip.','rank':1,'source':'Rules-based'}]
    elif issue=='No safe recovery capacity':
        options=[{'id':'escalate','action':'Escalate to dispatcher','vehicle':None,'reason':'No safe automated recovery is available.','rank':1,'source':'Rules-based'}]
    elif issue in ('Accident','Package damage','Wrong pickup address'):
        options=[{'id':'escalate','action':'Escalate to dispatcher for human review','vehicle':None,'reason':'This issue requires a human safety or shipment review before continuing.','rank':1,'source':'Rules-based'}]
    if own: conn.close()
    return options

def save_recommendations(shipment_id, options, conn=None):
    own=conn is None
    conn=conn or connect()
    conn.execute('UPDATE shipment_workflow SET recommendations_json=?,updated_at=? WHERE shipment_id=?',(json.dumps(options),datetime.now(timezone.utc).isoformat(),shipment_id))
    conn.commit()
    if own: conn.close()

def select_recovery(shipment_id, action_id, driver_id=None, vehicle_name=None, conn=None):
    own=conn is None
    conn=conn or connect()
    workflow=conn.execute('SELECT driver_id FROM shipment_workflow WHERE shipment_id=?',(shipment_id,)).fetchone()
    saved=conn.execute('SELECT recommendations_json FROM shipment_workflow WHERE shipment_id=?',(shipment_id,)).fetchone()
    options=json.loads(saved[0] or '[]') if saved else []
    option=next((o for o in options if o['id']==action_id),None)
    if not option:
        if own: conn.close()
        raise ValueError('Choose one of the listed recovery options')
    if action_id=='escalate':
        conn.execute("UPDATE shipment_workflow SET lifecycle_status='ESCALATED_TO_HUMAN',vendor_decision='Escalated to dispatcher',selected_action=?,updated_at=? WHERE shipment_id=?",
                     (option['action'],datetime.now(timezone.utc).isoformat(),shipment_id))
        conn.execute("UPDATE custom_shipments SET status='Escalated to dispatcher' WHERE shipment_id=?",(shipment_id,))
    elif action_id.startswith('replace:'):
        driver_id=driver_id or action_id.split(':',1)[1]
        target=conn.execute('SELECT name,vehicle,available FROM drivers WHERE driver_id=?',(driver_id,)).fetchone()
        if not target or (not target[2] and driver_id != workflow[0]):
            if own: conn.close()
            raise ValueError('Selected replacement driver is not available')
        if workflow and workflow[0] and workflow[0] != driver_id:
            conn.execute('UPDATE drivers SET available=1 WHERE driver_id=?',(workflow[0],))
        conn.execute('UPDATE drivers SET available=0 WHERE driver_id=?',(driver_id,))
        vehicle_name=vehicle_name or target[1]
        conn.execute("UPDATE shipment_workflow SET driver_id=?,driver_name=?,previous_driver_id=?,vehicle_name=?,lifecycle_status='DRIVER_REASSIGNED',updated_at=? WHERE shipment_id=?",
                     (driver_id,target[0],workflow[0] if workflow else None,vehicle_name,datetime.now(timezone.utc).isoformat(),shipment_id))
    else:
        conn.execute("UPDATE shipment_workflow SET lifecycle_status='RECOVERY_APPROVED',updated_at=? WHERE shipment_id=?",
                     (datetime.now(timezone.utc).isoformat(),shipment_id))
    if action_id!='escalate':
        conn.execute('UPDATE shipment_workflow SET selected_action=?, selected_driver_id=?, vehicle_name=?, vendor_decision=?, updated_at=? WHERE shipment_id=?',
                     (option['action'],driver_id,vehicle_name,'Approved',datetime.now(timezone.utc).isoformat(),shipment_id))
        conn.execute("UPDATE custom_shipments SET status=? WHERE shipment_id=?",('Driver reassigned' if action_id.startswith('replace:') else 'Recovery approved',shipment_id))
    record_workflow_event(conn,shipment_id,'RECOVERY_SELECTED','Dispatcher',f"{option['action']} · {driver_id or 'no driver'} · {vehicle_name or 'no vehicle'}")
    conn.commit()
    if own: conn.close()

def report_driver_update(shipment_id, driver_name, issue, conn=None, description=''):
    if driver_name not in DRIVERS:
        raise ValueError('Choose a driver from the list')
    if issue not in DRIVER_ISSUES:
        raise ValueError('Choose a supported issue')
    own = conn is None
    conn = conn or connect()
    exists = conn.execute('SELECT 1 FROM custom_shipments WHERE shipment_id=?', (shipment_id,)).fetchone()
    if not exists:
        if own:
            conn.close()
        raise ValueError('Choose a user-created shipment')

    scenario = DRIVER_ISSUES[issue]
    existing_workflow=conn.execute('SELECT lifecycle_status,driver_id FROM shipment_workflow WHERE shipment_id=?',(shipment_id,)).fetchone()
    driver_row=conn.execute('SELECT driver_id,vehicle FROM drivers WHERE name=?',(driver_name,)).fetchone()
    if existing_workflow and existing_workflow[1] and driver_row and existing_workflow[1] != driver_row[0]:
        if own: conn.close()
        raise ValueError('This driver is not assigned to the selected shipment')
    if scenario and existing_workflow and existing_workflow[0] != 'IN_TRANSIT':
        if own: conn.close()
        raise ValueError('Start the trip before reporting an issue')
    result = recover(shipment_id, scenario, conn) if scenario else None
    action = None
    agent_status = None
    vendor_decision = 'No issue'
    if result:
        agent_status = result['status']
        actions = [event['action'] for event in result['timeline'] if event.get('stage') == 'ACT + VERIFY']
        action = ', '.join(actions) if actions else 'Escalation required'
        vendor_decision = 'Pending vendor approval'
        conn.execute('UPDATE custom_shipments SET status=? WHERE shipment_id=?', ('At Risk', shipment_id))
        opts = recovery_options(shipment_id, issue, conn)
        conn.execute('UPDATE shipment_workflow SET recommendations_json=? WHERE shipment_id=?',(json.dumps(opts),shipment_id))
    else:
        conn.execute("UPDATE custom_shipments SET status='Normal' WHERE shipment_id=?", (shipment_id,))
    conn.execute('''UPDATE shipment_workflow SET driver_name=?, driver_id=COALESCE(?,driver_id), vehicle_name=COALESCE(?,vehicle_name), issue=?, issue_description=?, agent_status=?, agent_action=?, lifecycle_status=CASE WHEN ? IS NULL THEN 'DRIVER_ASSIGNED' ELSE 'ISSUE_REPORTED' END,
        vendor_decision=?, updated_at=? WHERE shipment_id=?''',
        (driver_name, driver_row[0] if driver_row else None, driver_row[1] if driver_row else None, issue, description, agent_status, action, scenario, vendor_decision, datetime.now(timezone.utc).isoformat(), shipment_id))
    if scenario:
        conn.execute('UPDATE drivers SET available=0 WHERE name=?',(driver_name,))
        record_workflow_event(conn,shipment_id,'ISSUE_REPORTED',driver_name,f'{issue}: {description or "No note provided"}')
        if issue=='Vehicle breakdown' and opts:
            # Breakdown recovery is automatic; a dispatcher can select another option later.
            top=opts[0]
            select_recovery(shipment_id,top['id'],top.get('driver_id'),top.get('vehicle'),conn)
        elif issue=='Vehicle breakdown':
            conn.execute("UPDATE shipment_workflow SET lifecycle_status='ESCALATED_TO_HUMAN', vendor_decision='Escalated to dispatcher' WHERE shipment_id=?",(shipment_id,))
            conn.execute("UPDATE custom_shipments SET status='Escalated to dispatcher' WHERE shipment_id=?",(shipment_id,))
    conn.commit()
    if own:
        conn.close()
    return result

def set_vendor_decision(shipment_id, decision, conn=None):
    if decision not in ('Approved', 'Rejected'):
        raise ValueError('Decision must be Approved or Rejected')
    own = conn is None
    conn = conn or connect()
    conn.execute('UPDATE shipment_workflow SET vendor_decision=?, updated_at=? WHERE shipment_id=? AND issue IS NOT NULL AND issue != \'No issue\'',
        (decision, datetime.now(timezone.utc).isoformat(), shipment_id))
    conn.commit()
    if own:
        conn.close()

def set_shipment_liked(shipment_id, liked, conn=None):
    own = conn is None
    conn = conn or connect()
    if liked:
        conn.execute('INSERT OR IGNORE INTO shipment_likes (shipment_id, liked) VALUES (?, 1)', (shipment_id,))
    else:
        conn.execute('DELETE FROM shipment_likes WHERE shipment_id=?', (shipment_id,))
    conn.commit()
    if own:
        conn.close()

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
