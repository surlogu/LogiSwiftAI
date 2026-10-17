"""Automated test suite for LLD Section 9 Testing Plan."""
from agent.main import run_agent


SAMPLE_ORDER = {
    "order_id": "ORDER-101",
    "pickup": "T. Nagar, Chennai",
    "drop": "Adyar, Chennai",
    "deadline": "18:00",
    "package_type": "medical_supplies",
    "priority": "high"
}


def test_valid_order_reaches_delivery():
    res = run_agent(SAMPLE_ORDER, simulate_failures=0, verbose=False)
    assert res["final_status"] == "delivered"
    assert res["customer_notified"] is True
    assert res["requires_human"] is False
    assert len(res["attempts"]) == 1


def test_courier_failure_triggers_reassignment():
    res = run_agent(SAMPLE_ORDER, simulate_failures=1, verbose=False)
    assert res["final_status"] == "delivered"
    assert res["customer_notified"] is True
    assert res["requires_human"] is False
    assert len(res["attempts"]) == 2
    assert res["attempts"][0]["courier_id"] == "COURIER_A"
    assert res["attempts"][1]["courier_id"] == "COURIER_B"
    assert any("COURIER_A -> COURIER_B" in act for act in res["recovery_actions"])


def test_agent_escalates_after_max_retries():
    res = run_agent(SAMPLE_ORDER, simulate_failures=3, verbose=False)
    assert res["final_status"] == "escalated"
    assert res["requires_human"] is True
    assert res["customer_notified"] is False


def test_audit_log_contains_recovery_event():
    res = run_agent(SAMPLE_ORDER, simulate_failures=1, verbose=False)
    events = [entry["event"] for entry in res["audit_log"]]
    assert "courier_assigned" in events
    assert "courier_reassigned" in events
    assert "shipment_delivered" in events

    reassigned_entry = next(e for e in res["audit_log"] if e["event"] == "courier_reassigned")
    assert reassigned_entry["from_courier"] == "COURIER_A"
    assert reassigned_entry["to_courier"] == "COURIER_B"
    assert reassigned_entry["reason"] == "courier_unavailable"


def test_invalid_order_rejected():
    bad_order = {"order_id": "ORDER-999", "pickup": "T. Nagar"}
    res = run_agent(bad_order, simulate_failures=0, verbose=False)
    assert res["final_status"] == "escalated"
    assert res["reason"] == "invalid_order"


def test_cross_run_feedback_loop_and_a2a_handoffs():
    # Run 1: Courier A fails -> A2A hands off to Recovery_Specialist_Agent -> Reassigns to Courier B
    run1 = run_agent(SAMPLE_ORDER, simulate_failures=1, clear_audit_history=True, verbose=False)
    assert run1["final_status"] == "delivered"
    assert any(h["to"] == "Recovery_Specialist_Agent" for h in run1["a2a_handoffs"])
    assert run1["attempts"][0]["courier_id"] == "COURIER_A"
    assert run1["attempts"][1]["courier_id"] == "COURIER_B"

    # Run 2 (with clear_audit_history=False): Agent remembers Courier A failed in Run 1
    # and automatically assigns Courier B on Attempt #1!
    run2 = run_agent(SAMPLE_ORDER, simulate_failures=0, clear_audit_history=False, verbose=False)
    assert run2["final_status"] == "delivered"
    assert len(run2["attempts"]) == 1
    assert run2["attempts"][0]["courier_id"] == "COURIER_B"


def test_human_can_revoke_courier_penalty():
    from agent.tools import revoke_courier_penalty, get_historical_failed_couriers
    # Run 1: Courier A fails and is recorded in audit_log.json
    run_agent(SAMPLE_ORDER, simulate_failures=1, clear_audit_history=True, verbose=False)
    assert "COURIER_A" in get_historical_failed_couriers()

    # Human auditor revokes the penalty
    revoke_res = revoke_courier_penalty("COURIER_A", "Pardoned by dispatcher")
    assert revoke_res["revoked_records"] >= 1
    assert "COURIER_A" not in get_historical_failed_couriers()

    # Run 2: With audit memory kept, Courier A is pardoned and chosen again on Attempt #1
    run2 = run_agent(SAMPLE_ORDER, simulate_failures=0, clear_audit_history=False, verbose=False)
    assert run2["final_status"] == "delivered"
    assert run2["attempts"][0]["courier_id"] == "COURIER_A"


