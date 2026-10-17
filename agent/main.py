"""Agent Orchestrator with A2A Handoffs and Cross-Run Feedback Learning."""
import json
import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

from agent.state import AgentState
from agent.tools import (
    validate_order,
    get_available_couriers,
    assign_courier,
    get_shipment_status,
    reassign_courier,
    notify_customer,
    write_audit_log,
    read_audit_log,
    get_historical_failed_couriers,
)
from simulator.failure_simulator import reset_simulation_data, inject_courier_breakdown

load_dotenv()

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

MAX_RETRIES = 2

TOOL_REGISTRY = {
    "validate_order": validate_order,
    "get_available_couriers": get_available_couriers,
    "assign_courier": assign_courier,
    "get_shipment_status": get_shipment_status,
    "reassign_courier": reassign_courier,
    "notify_customer": notify_customer,
    "write_audit_log": write_audit_log,
}


def execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if tool_name not in TOOL_REGISTRY:
        return {"error": f"Unknown tool name: {tool_name}"}
    try:
        return TOOL_REGISTRY[tool_name](**arguments)
    except TypeError as exc:
        return {"error": f"Missing or invalid tool argument for {tool_name}: {exc}"}
    except Exception as exc:
        return {"error": f"Tool execution error in {tool_name}: {exc}"}


def inspect_multimodal_package(
    order: Dict[str, Any],
    image_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg"
) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if image_bytes and GENAI_AVAILABLE and api_key and api_key != "your_gemini_api_key_here":
        lite_candidates = [
            os.environ.get("GEMINI_LITE_MODEL", "gemini-flash-lite-latest"),
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
        ]
        client = genai.Client(api_key=api_key)
        for model_name in lite_candidates:
            try:
                resp = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        f"Inspect this same-day parcel image for order {order.get('order_id')} "
                        f"({order.get('package_type')}). Confirm packaging integrity and priority handling in 1 short sentence."
                    ]
                )
                return f"Gemini Vision ({model_name}): {resp.text.strip()}"
            except Exception:
                continue
    if image_bytes:
        return f"Simulated Vision Scan ({len(image_bytes)}B): Cold-chain seal intact for {order.get('package_type', 'parcel')}."
    return f"Manifest verified: {order.get('package_type', 'general')} ({order.get('priority', 'normal')} priority)."


def run_agent(
    order: Dict[str, Any],
    simulate_failures: int = 1,
    initial_courier_override: Optional[str] = "COURIER_A",
    reset_store: bool = True,
    clear_audit_history: bool = True,
    penalized_couriers: Optional[List[str]] = None,
    image_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg",
    verbose: bool = True
) -> Dict[str, Any]:
    """
    Executes the end-to-end flow with A2A Handoffs:
    - Agent 1: Intake_Monitor_Agent (Validates, assigns, monitors)
    - Agent 2: Recovery_Specialist_Agent (A2A handoff on failure: diagnoses, scores, reassigns)
    - Agent 3: Customer_Audit_Agent (A2A handoff on completion/escalation: notifies & logs)
    """
    if reset_store:
        reset_simulation_data(clear_audit_history=clear_audit_history)

    # Load cross-run learned penalties from audit_log.json
    historical_bad_couriers = get_historical_failed_couriers() if not clear_audit_history else []
    penalized = list(set((penalized_couriers or []) + historical_bad_couriers))

    steps_trace: List[Dict[str, Any]] = []
    a2a_handoffs: List[Dict[str, str]] = []
    recovery_actions: List[str] = []
    attempts_log: List[Dict[str, Any]] = []
    order_id = order.get("order_id", "UNKNOWN")
    shipment_id = f"SHP-{order_id}"
    state = AgentState.ORDER_VALIDATION
    active_agent = "Intake_Monitor_Agent"

    def log_step(step_num: int, tool_name: str, summary: str, payload: Dict[str, Any]):
        steps_trace.append({
            "step": step_num,
            "agent": active_agent,
            "state": state.value,
            "tool": tool_name,
            "summary": f"[{active_agent}] {summary}",
            "result": payload
        })
        if verbose:
            print(f"Step {step_num} [{active_agent}]: {tool_name}\nResult: {summary}\n")

    def log_a2a(from_agent: str, to_agent: str, reason: str):
        nonlocal active_agent
        active_agent = to_agent
        a2a_handoffs.append({"from": from_agent, "to": to_agent, "reason": reason})
        if verbose:
            print(f"🔄 [A2A HANDOFF] {from_agent} -> {to_agent} ({reason})\n")

    # Step 1: Validate Order + Multimodal Check
    mm_note = inspect_multimodal_package(order, image_bytes=image_bytes, mime_type=mime_type)
    val_res = execute_tool("validate_order", {"order": order})
    log_step(1, "validate_order", f"{'valid' if val_res.get('valid') else 'invalid'} | {mm_note}", val_res)

    if not val_res.get("valid"):
        log_a2a("Intake_Monitor_Agent", "Customer_Audit_Agent", "Order validation failed")
        state = AgentState.ESCALATED
        execute_tool("write_audit_log", {
            "entry": {
                "order_id": order_id,
                "shipment_id": None,
                "event": "order_rejected",
                "reason": "invalid_order",
                "missing_fields": val_res.get("missing_fields", []),
                "agent_decision": val_res.get("message")
            }
        })
        return {
            "engine": "a2a_state_machine",
            "order_id": order_id,
            "final_status": "escalated",
            "reason": "invalid_order",
            "summary": val_res.get("message"),
            "attempts": attempts_log,
            "recovery_actions": recovery_actions,
            "a2a_handoffs": a2a_handoffs,
            "customer_notified": False,
            "requires_human": True,
            "steps_trace": steps_trace,
            "audit_log": read_audit_log()
        }

    # Step 2: Fetch Available Couriers
    state = AgentState.COURIER_SELECTION
    req_cap = 4 if order.get("priority") == "high" else 2
    couriers_res = execute_tool("get_available_couriers", {
        "required_capacity": req_cap,
        "penalized_couriers": penalized
    })
    available = couriers_res.get("available_couriers", [])
    log_step(2, "get_available_couriers", f"{len(available)} couriers available (Penalized: {penalized})", couriers_res)

    if not available:
        log_a2a("Intake_Monitor_Agent", "Customer_Audit_Agent", "Zero courier capacity available")
        state = AgentState.ESCALATED
        execute_tool("write_audit_log", {
            "entry": {
                "order_id": order_id,
                "shipment_id": None,
                "event": "escalation",
                "reason": "no_courier_available",
                "agent_decision": "No available couriers in inventory; escalating to human dispatch"
            }
        })
        return {
            "engine": "a2a_state_machine",
            "order_id": order_id,
            "final_status": "escalated",
            "reason": "no_courier_available",
            "summary": "No couriers available for assignment.",
            "attempts": attempts_log,
            "recovery_actions": recovery_actions,
            "a2a_handoffs": a2a_handoffs,
            "customer_notified": False,
            "requires_human": True,
            "steps_trace": steps_trace,
            "audit_log": read_audit_log()
        }

    # Step 3: Assign Initial Courier
    # If COURIER_A is NOT penalized by past runs, pick COURIER_A for the demo;
    # If COURIER_A WAS penalized by a past run, the Feedback Loop automatically skips COURIER_A and picks COURIER_B!
    chosen_initial = available[0]
    if initial_courier_override and initial_courier_override not in penalized:
        override_match = next((c for c in available if c["id"] == initial_courier_override), None)
        if override_match:
            chosen_initial = override_match

    assign_res = execute_tool("assign_courier", {
        "order_id": order_id,
        "courier_id": chosen_initial["id"]
    })
    state = AgentState.SHIPMENT_ASSIGNED
    attempts_log.append({"attempt": 1, "courier_id": chosen_initial["id"], "action": "assign_courier"})
    log_step(3, "assign_courier", f"Selected: {chosen_initial['id']} (ETA {chosen_initial['base_eta_minutes']}m)", assign_res)

    execute_tool("write_audit_log", {
        "entry": {
            "order_id": order_id,
            "shipment_id": shipment_id,
            "event": "courier_assigned",
            "from_courier": None,
            "to_courier": chosen_initial["id"],
            "reason": "learned_optimal_assignment" if penalized else "initial_assignment",
            "agent_decision": f"Assigned {chosen_initial['id']} ({chosen_initial['name']}) with ETA {chosen_initial['base_eta_minutes']}m"
        }
    })

    # Step 4+: Self-Healing Monitoring & A2A Recovery Loop (MAX_RETRIES = 2)
    failures_remaining = simulate_failures
    step_counter = 4

    for retry_idx in range(MAX_RETRIES + 1):
        state = AgentState.MONITORING
        active_courier_id = attempts_log[-1]["courier_id"]

        if failures_remaining > 0:
            inject_courier_breakdown(shipment_id, courier_id=active_courier_id, event_time="16:10")
            failures_remaining -= 1

        status_res = execute_tool("get_shipment_status", {"shipment_id": shipment_id})
        current_status = status_res.get("status")
        log_step(step_counter, "get_shipment_status", f"Status: {current_status}", status_res)
        step_counter += 1

        if current_status == "delivered":
            log_a2a(active_agent, "Customer_Audit_Agent", f"Shipment verified delivered by {active_courier_id}")
            state = AgentState.CUSTOMER_NOTIFIED
            notif_msg = (
                f"Order {order_id} ({order.get('package_type', 'parcel')}) delivered from "
                f"{order.get('pickup')} to {order.get('drop')} by {active_courier_id} before {order.get('deadline')}."
            )
            notif_res = execute_tool("notify_customer", {"order_id": order_id, "message": notif_msg})
            log_step(step_counter, "notify_customer", "Customer notified", notif_res)

            state = AgentState.COMPLETED
            execute_tool("write_audit_log", {
                "entry": {
                    "order_id": order_id,
                    "shipment_id": shipment_id,
                    "event": "shipment_delivered",
                    "from_courier": None,
                    "to_courier": active_courier_id,
                    "reason": "verified_delivery",
                    "agent_decision": f"Verified delivery by {active_courier_id} and notified customer"
                }
            })
            return {
                "engine": "a2a_state_machine",
                "order_id": order_id,
                "shipment_id": shipment_id,
                "final_status": "delivered",
                "summary": f"Delivered by {active_courier_id}. Recovery actions: {len(recovery_actions)}.",
                "attempts": attempts_log,
                "recovery_actions": recovery_actions,
                "a2a_handoffs": a2a_handoffs,
                "customer_notified": True,
                "requires_human": False,
                "steps_trace": steps_trace,
                "audit_log": read_audit_log()
            }

        # Failure detected -> Trigger A2A Handoff to Recovery_Specialist_Agent
        log_a2a(active_agent, "Recovery_Specialist_Agent", f"Detected {current_status} on {active_courier_id}")
        state = AgentState.RECOVERY_PLANNING
        penalized.append(active_courier_id)

        if retry_idx >= MAX_RETRIES:
            break

        cand_res = execute_tool("get_available_couriers", {
            "required_capacity": req_cap,
            "penalized_couriers": penalized
        })
        candidates = cand_res.get("available_couriers", [])
        cand_ids = ", ".join(c["id"] for c in candidates) if candidates else "None"
        log_step(step_counter, "get_available_couriers", f"Recovery candidates: {cand_ids}", cand_res)
        step_counter += 1

        if not candidates:
            break

        best_replacement = candidates[0]
        reassign_res = execute_tool("reassign_courier", {
            "shipment_id": shipment_id,
            "new_courier_id": best_replacement["id"]
        })
        state = AgentState.COURIER_REASSIGNED
        action_desc = f"Reassigned {active_courier_id} -> {best_replacement['id']} (score={best_replacement['score']}, ETA={best_replacement['base_eta_minutes']}m)"
        recovery_actions.append(action_desc)
        attempts_log.append({
            "attempt": len(attempts_log) + 1,
            "courier_id": best_replacement["id"],
            "action": "reassign_courier"
        })
        log_step(step_counter, "reassign_courier", f"Reassigned: {active_courier_id} -> {best_replacement['id']}", reassign_res)
        step_counter += 1

        execute_tool("write_audit_log", {
            "entry": {
                "order_id": order_id,
                "shipment_id": shipment_id,
                "event": "courier_reassigned",
                "from_courier": active_courier_id,
                "to_courier": best_replacement["id"],
                "reason": current_status,
                "agent_decision": (
                    f"Deadline buffer 110m; selected highest-scored courier {best_replacement['id']} "
                    f"(reliability {best_replacement['reliability']}, ETA {best_replacement['base_eta_minutes']}m)"
                )
            }
        })
        # Hand back to Intake_Monitor_Agent to verify the new courier's delivery status
        log_a2a("Recovery_Specialist_Agent", "Intake_Monitor_Agent", f"Verify reassigned courier {best_replacement['id']}")

    # If loop exits without delivery -> A2A Handoff to Customer_Audit_Agent for Human Escalation
    log_a2a(active_agent, "Customer_Audit_Agent", "Max retries exhausted; escalating to human dispatch")
    state = AgentState.ESCALATED
    execute_tool("write_audit_log", {
        "entry": {
            "order_id": order_id,
            "shipment_id": shipment_id,
            "event": "escalated_to_human",
            "from_courier": attempts_log[-1]["courier_id"] if attempts_log else None,
            "to_courier": None,
            "reason": "max_retries_or_no_capacity",
            "agent_decision": "Automated recovery exhausted; marked requires_human_intervention"
        }
    })
    return {
        "engine": "a2a_state_machine",
        "order_id": order_id,
        "shipment_id": shipment_id,
        "final_status": "escalated",
        "reason": "max_retries_exceeded",
        "summary": "Automated recovery failed after maximum retries; escalated to human operations.",
        "attempts": attempts_log,
        "recovery_actions": recovery_actions,
        "a2a_handoffs": a2a_handoffs,
        "customer_notified": False,
        "requires_human": True,
        "steps_trace": steps_trace,
        "audit_log": read_audit_log()
    }


if __name__ == "__main__":
    sample_order = {
        "order_id": "ORDER-101",
        "pickup": "T. Nagar, Chennai",
        "drop": "Adyar, Chennai",
        "deadline": "18:00",
        "package_type": "medical_supplies",
        "priority": "high"
    }
    output = run_agent(sample_order, simulate_failures=1, verbose=True)
    print("FINAL STATUS:", output["final_status"].upper())
    print(json.dumps({
        "order_id": output["order_id"],
        "final_status": output["final_status"],
        "attempts": output["attempts"],
        "recovery_actions": output["recovery_actions"],
        "a2a_handoffs": output["a2a_handoffs"],
        "customer_notified": output["customer_notified"],
        "requires_human": output["requires_human"]
    }, indent=2))
