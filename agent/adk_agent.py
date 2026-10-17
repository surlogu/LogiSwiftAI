"""Google ADK Multi-Agent (A2A) Orchestrator with Thread-Safe Streamlit Execution."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from agent.prompts import SYSTEM_PROMPT
from agent.tools import (
    validate_order,
    get_available_couriers,
    assign_courier,
    get_shipment_status,
    reassign_courier,
    notify_customer,
    write_audit_log,
    read_audit_log,
)
from agent.main import run_agent as run_deterministic_fallback
from simulator.failure_simulator import reset_simulation_data, inject_courier_breakdown

load_dotenv()

try:
    from google.adk.agents import LlmAgent
    from google.adk.runners import InMemoryRunner
    from google.genai import types
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False


async def _run_adk_async(
    order: Dict[str, Any],
    simulate_failures: int = 1,
    clear_audit_history: bool = True,
    image_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg",
    root_model_override: Optional[str] = None,
    lite_model_override: Optional[str] = None,
) -> Dict[str, Any]:
    reset_simulation_data(clear_audit_history=clear_audit_history)
    shipment_id = f"SHP-{order.get('order_id', 'ORDER-101')}"
    failures_left = {"count": simulate_failures}

    def assign_courier_with_sim(order_id: str, courier_id: str) -> Dict[str, Any]:
        res = assign_courier(order_id, courier_id)
        if res.get("success"):
            write_audit_log({
                "event": "courier_assigned",
                "order_id": order_id,
                "courier_id": courier_id,
                "shipment_id": f"SHP-{order_id}",
            })
            if failures_left["count"] > 0:
                inject_courier_breakdown(f"SHP-{order_id}", courier_id=courier_id, event_time="16:10")
                failures_left["count"] -= 1
        return res

    def reassign_courier_with_sim(shipment_id: str, new_courier_id: str) -> Dict[str, Any]:
        res = reassign_courier(shipment_id, new_courier_id)
        if res.get("success"):
            shp = res.get("shipment", {})
            write_audit_log({
                "event": "courier_reassigned",
                "order_id": shp.get("order_id"),
                "shipment_id": shipment_id,
                "from_courier": shp.get("previous_courier_id"),
                "to_courier": new_courier_id,
                "reason": "courier_unavailable",
            })
            if failures_left["count"] > 0:
                inject_courier_breakdown(shipment_id, courier_id=new_courier_id, event_time="16:25")
                failures_left["count"] -= 1
        return res

    def get_shipment_status_with_sim(shipment_id: str) -> Dict[str, Any]:
        res = get_shipment_status(shipment_id)
        if res.get("status") == "delivered":
            write_audit_log({
                "event": "shipment_delivered",
                "shipment_id": shipment_id,
                "order_id": order.get("order_id"),
                "status": "delivered"
            })
        return res

    root_model = root_model_override or os.environ.get("GEMINI_ROOT_MODEL", os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"))
    lite_model = lite_model_override or os.environ.get("GEMINI_LITE_MODEL", "gemini-flash-lite-latest")

    # Sub-Agent 1: Recovery Specialist (Uses lightweight Flash-Lite to preserve RPM)
    recovery_specialist = LlmAgent(
        name="Recovery_Specialist_Agent",
        model=lite_model,
        description="Handles courier_unavailable exceptions by scoring alternatives and reassigning shipments.",
        instruction="You are the Recovery Specialist Agent. Find available couriers, reassign the failed shipment, and log the recovery in the audit log.",
        tools=[get_available_couriers, reassign_courier_with_sim, get_shipment_status_with_sim, write_audit_log],
    )

    # Sub-Agent 2: Customer & Audit Closer (Uses lightweight Flash-Lite to preserve RPM)
    customer_audit_agent = LlmAgent(
        name="Customer_Audit_Agent",
        model=lite_model,
        description="Notifies the customer upon verified delivery and writes final audit log entries.",
        instruction="You are the Customer & Audit Agent. Notify the customer of delivery and record the final audit entry.",
        tools=[notify_customer, write_audit_log],
    )

    # Root Coordinator Agent with A2A Sub-Agents and full toolset
    root_coordinator = LlmAgent(
        name="LogiSwift_Coordinator_Agent",
        model=root_model,
        instruction=SYSTEM_PROMPT,
        sub_agents=[recovery_specialist, customer_audit_agent],
        tools=[
            validate_order,
            get_available_couriers,
            assign_courier_with_sim,
            get_shipment_status_with_sim,
            reassign_courier_with_sim,
            notify_customer,
            write_audit_log,
        ],
    )

    runner = InMemoryRunner(agent=root_coordinator, app_name="logiswift_app")
    session = await runner.session_service.create_session(
        app_name="logiswift_app", user_id="dispatcher_01"
    )

    parts = [
        types.Part.from_text(
            text=(
                f"Process this same-day delivery order end-to-end. "
                f"Initially assign COURIER_A if available and not penalized, verify shipment status, "
                f"and self-heal if a breakdown occurs:\n{json.dumps(order)}"
            )
        )
    ]
    if image_bytes:
        parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

    content = types.Content(role="user", parts=parts)
    steps_trace = []
    step_num = 1
    final_text = ""

    async for event in runner.run_async(
        user_id="dispatcher_01", session_id=session.id, new_message=content
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    steps_trace.append({
                        "step": step_num,
                        "state": f"ADK ({event.author})",
                        "tool": part.function_call.name,
                        "summary": f"[{event.author}] Args: {dict(part.function_call.args)}",
                    })
                    step_num += 1
                elif part.text:
                    final_text = part.text

    audit_entries = read_audit_log()
    delivered = (
        any(
            e.get("event") in ("shipment_delivered", "delivery_completed")
            or e.get("status") == "delivered"
            or e.get("action") == "delivery_completed"
            for e in audit_entries
        )
        or "delivered" in final_text.lower()
    )

    return {
        "engine": f"google-adk-a2a (root:{root_model}, sub:{lite_model})",
        "order_id": order.get("order_id"),
        "shipment_id": shipment_id,
        "final_status": "delivered" if delivered else "escalated",
        "summary": final_text,
        "attempts": [e for e in audit_entries if e.get("event") in ("courier_assigned", "courier_reassigned")],
        "recovery_actions": [
            f"{e.get('from_courier')} -> {e.get('to_courier')}"
            for e in audit_entries if e.get("event") == "courier_reassigned"
        ],
        "customer_notified": delivered,
        "requires_human": not delivered,
        "steps_trace": steps_trace,
        "audit_log": audit_entries,
    }


def _run_coroutine_safely(coro):
    """Prevents `RuntimeError: This event loop is already running` inside Streamlit."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def run_hybrid_agent(
    order: Dict[str, Any],
    simulate_failures: int = 1,
    clear_audit_history: bool = True,
    image_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg",
) -> Dict[str, Any]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if ADK_AVAILABLE and api_key and api_key != "your_gemini_api_key_here":
        cascade = [
            os.environ.get("GEMINI_ROOT_MODEL", "gemini-3.8-flash"),
            os.environ.get("GEMINI_LITE_MODEL", "gemini-flash-lite-latest"),
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
        ]
        seen = set()
        ordered_models = [m for m in cascade if not (m in seen or seen.add(m))]
        last_error = None

        for candidate_root in ordered_models:
            candidate_lite = candidate_root if "lite" in candidate_root else os.environ.get("GEMINI_LITE_MODEL", "gemini-flash-lite-latest")
            try:
                res = _run_coroutine_safely(
                    _run_adk_async(
                        order,
                        simulate_failures=simulate_failures,
                        clear_audit_history=clear_audit_history,
                        image_bytes=image_bytes,
                        mime_type=mime_type,
                        root_model_override=candidate_root,
                        lite_model_override=candidate_lite,
                    )
                )
                if candidate_root != ordered_models[0]:
                    res["cascade_fallback"] = f"Primary model rate-limited; automatically resolved with {candidate_root}."
                return res
            except Exception as exc:
                last_error = exc
                continue

        fallback = run_deterministic_fallback(
            order,
            simulate_failures=simulate_failures,
            clear_audit_history=clear_audit_history,
            image_bytes=image_bytes,
            mime_type=mime_type,
            verbose=False
        )
        fallback["engine"] = f"deterministic_a2a_fallback (All cascade models failed: {last_error})"
        return fallback

    fallback = run_deterministic_fallback(
        order,
        simulate_failures=simulate_failures,
        clear_audit_history=clear_audit_history,
        image_bytes=image_bytes,
        mime_type=mime_type,
        verbose=False
    )
    fallback["engine"] = "deterministic_a2a_simulator (No GEMINI_API_KEY in .env)"
    return fallback
