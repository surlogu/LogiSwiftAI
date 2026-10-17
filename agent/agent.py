"""Google ADK entrypoint exposing root_agent for the official ADK Dev UI (`adk web`)."""
import os
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
)

load_dotenv()

try:
    from google.adk.agents import LlmAgent
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False

root_model = os.environ.get("GEMINI_ROOT_MODEL", os.environ.get("GEMINI_MODEL", "gemini-3.8-flash"))
lite_model = os.environ.get("GEMINI_LITE_MODEL", "gemini-flash-lite-latest")

if ADK_AVAILABLE:
    recovery_specialist = LlmAgent(
        name="Recovery_Specialist_Agent",
        model=lite_model,
        description="Handles courier_unavailable exceptions by scoring alternatives and reassigning shipments.",
        instruction="You are the Recovery Specialist Agent. Find available couriers, reassign the failed shipment, and log the recovery in the audit log.",
        tools=[get_available_couriers, reassign_courier, get_shipment_status, write_audit_log],
    )

    customer_audit_agent = LlmAgent(
        name="Customer_Audit_Agent",
        model=lite_model,
        description="Notifies the customer upon verified delivery and writes final audit log entries.",
        instruction="You are the Customer & Audit Agent. Notify the customer of delivery and record the final audit entry.",
        tools=[notify_customer, write_audit_log],
    )

    root_agent = LlmAgent(
        name="LogiSwift_Coordinator_Agent",
        model=root_model,
        instruction=SYSTEM_PROMPT,
        sub_agents=[recovery_specialist, customer_audit_agent],
        tools=[
            validate_order,
            get_available_couriers,
            assign_courier,
            get_shipment_status,
            reassign_courier,
            notify_customer,
            write_audit_log,
        ],
    )
else:
    root_agent = None
