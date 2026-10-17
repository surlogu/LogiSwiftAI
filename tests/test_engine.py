import sqlite3
from engine import (SCENARIOS, add_shipment, assign_driver, complete_delivery,
                    connect, driver_records, recover, report_driver_update,
                    select_recovery, shipment_workflows, start_trip, strategy_order)

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

def test_breakdown_reassigns_same_shipment_and_allows_delivery():
    c=connect(':memory:')
    shipment=add_shipment('Chennai','Bengaluru','High','Normal','Test Vendor',c)
    assign_driver(shipment,'DRIVER_A',c)
    start_trip(shipment,'DRIVER_A',c)
    report_driver_update(shipment,'Ravi Kumar','Vehicle breakdown',c,'Bike stopped near Adyar')
    row=next(item for item in shipment_workflows(c) if item['Shipment']==shipment)
    assert row['Lifecycle']=='DRIVER_REASSIGNED'
    assert row['Driver ID']=='DRIVER_B'
    assert row.get('Previous Driver ID')=='DRIVER_A', list(row.keys())
    assert len(row['Recommendations']) >= 2
    start_trip(shipment,'DRIVER_B',c)
    complete_delivery(shipment,'DRIVER_B',c)
    row=next(item for item in shipment_workflows(c) if item['Shipment']==shipment)
    assert row['Lifecycle']=='DELIVERED'
    assert next(d for d in driver_records(c) if d['driver_id']=='DRIVER_B')['available']==1

def test_dispatcher_can_change_recommended_replacement_driver():
    c=connect(':memory:')
    shipment=add_shipment('Chennai','Bengaluru','Normal','Normal','Test Vendor',c)
    assign_driver(shipment,'DRIVER_A',c)
    start_trip(shipment,'DRIVER_A',c)
    report_driver_update(shipment,'Ravi Kumar','Vehicle breakdown',c)
    select_recovery(shipment,'replace:DRIVER_C','DRIVER_C','Van 02',c)
    row=next(item for item in shipment_workflows(c) if item['Shipment']==shipment)
    assert row['Driver ID']=='DRIVER_C'
    assert row['Vehicle']=='Van 02'
    assert row['Lifecycle']=='DRIVER_REASSIGNED'

def test_driver_cannot_report_before_trip_starts():
    c=connect(':memory:')
    shipment=add_shipment('Chennai','Bengaluru','Normal','Normal','Test Vendor',c)
    assign_driver(shipment,'DRIVER_A',c)
    try:
        report_driver_update(shipment,'Ravi Kumar','Vehicle breakdown',c)
    except ValueError as exc:
        assert 'Start the trip' in str(exc)
    else:
        raise AssertionError('An incident should require an active trip')
