import sqlite3
from engine import (SCENARIOS, add_shipment, assign_driver, complete_delivery,
                    approve_recommendation, connect, decision_history, driver_records,
                    has_decision_feedback, rank_options_from_feedback, recover,
                    reject_recommendation, report_driver_update, shipment_workflows,
                    start_trip, strategy_order)

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

def test_breakdown_waits_for_ops_approval_then_reassigns_and_delivers():
    c=connect(':memory:')
    shipment=add_shipment('Chennai','Bengaluru','High','Normal','Test Vendor',c)
    assign_driver(shipment,'DRIVER_A',c)
    start_trip(shipment,'DRIVER_A',c)
    report_driver_update(shipment,'Ravi Kumar','Vehicle breakdown',c,'Bike stopped near Adyar')
    row=next(item for item in shipment_workflows(c) if item['Shipment']==shipment)
    assert row['Lifecycle']=='AWAITING_APPROVAL'
    assert row['Driver ID']=='DRIVER_A'
    assert len(row['Recommendations']) >= 2
    approve_recommendation(shipment,'replace:DRIVER_B','DRIVER_B','Bike 02',c)
    row=next(item for item in shipment_workflows(c) if item['Shipment']==shipment)
    assert row['Lifecycle']=='DRIVER_REASSIGNED'
    assert row['Driver ID']=='DRIVER_B'
    assert row['Previous Driver ID']=='DRIVER_A'
    assert any(item['decision']=='APPROVED' for item in decision_history(conn=c))
    start_trip(shipment,'DRIVER_B',c)
    complete_delivery(shipment,'DRIVER_B',c)
    row=next(item for item in shipment_workflows(c) if item['Shipment']==shipment)
    assert row['Lifecycle']=='DELIVERED'
    assert next(d for d in driver_records(c) if d['driver_id']=='DRIVER_B')['available']==1

def test_ops_can_approve_a_different_recommended_driver():
    c=connect(':memory:')
    shipment=add_shipment('Chennai','Bengaluru','Normal','Normal','Test Vendor',c)
    assign_driver(shipment,'DRIVER_A',c)
    start_trip(shipment,'DRIVER_A',c)
    report_driver_update(shipment,'Ravi Kumar','Vehicle breakdown',c)
    row=next(item for item in shipment_workflows(c) if item['Shipment']==shipment)
    assert row['Lifecycle']=='AWAITING_APPROVAL'
    approve_recommendation(shipment,'replace:DRIVER_C','DRIVER_C','Van 02',c)
    row=next(item for item in shipment_workflows(c) if item['Shipment']==shipment)
    assert row['Driver ID']=='DRIVER_C'
    assert row['Vehicle']=='Van 02'
    assert row['Lifecycle']=='DRIVER_REASSIGNED'

def test_rejection_logs_and_uses_next_option_then_learns_without_gemini():
    c=connect(':memory:')
    first=add_shipment('Chennai','Bengaluru','Normal','Normal','Test Vendor',c)
    assign_driver(first,'DRIVER_A',c)
    start_trip(first,'DRIVER_A',c)
    report_driver_update(first,'Ravi Kumar','Traffic delay',c,'Congestion near pickup')
    row=next(item for item in shipment_workflows(c) if item['Shipment']==first)
    next_option=reject_recommendation(first,row['Current recommendation ID'],'ETA too slow',c)
    assert next_option['id']=='alternate_route_A'
    assert next(item for item in shipment_workflows(c) if item['Shipment']==first)['Lifecycle']=='AWAITING_APPROVAL'
    saved=next(item for item in shipment_workflows(c) if item['Shipment']==first)['Recommendations']
    assert saved[0]['review_status']=='REJECTED'
    assert decision_history(conn=c)[0]['reason']=='ETA too slow'

    second=add_shipment('Mumbai','Pune','Normal','Normal','Test Vendor',c)
    assign_driver(second,'DRIVER_B',c)
    start_trip(second,'DRIVER_B',c)
    report_driver_update(second,'Suresh','Traffic delay',c)
    assert has_decision_feedback('Traffic delay',c)
    options=next(item for item in shipment_workflows(c) if item['Shipment']==second)['Recommendations']
    ranked=rank_options_from_feedback('Traffic delay',options,c)
    assert ranked[0]['id']=='alternate_route_A'
    assert ranked[0]['source']=='Learned from Ops decisions (Gemini skipped)'

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
