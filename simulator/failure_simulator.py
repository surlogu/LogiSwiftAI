"""Deterministic failure simulator with persistent cross-run audit memory."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SHIPMENTS_FILE = DATA_DIR / "shipments.json"
AUDIT_FILE = DATA_DIR / "audit_log.json"
COURIERS_FILE = Path(__file__).resolve().parent / "couriers.json"


def reset_simulation_data(clear_audit_history: bool = False):
    """
    Resets active couriers and shipments for a new order run.
    Preserves `audit_log.json` by default so the Feedback Loop learns from past runs!
    """
    DATA_DIR.mkdir(exist_ok=True)
    default_couriers = [
        {
            "id": "COURIER_A",
            "name": "Chennai Quick",
            "vehicle": "bike",
            "capacity": 5,
            "available": True,
            "reliability": 0.72,
            "base_eta_minutes": 55
        },
        {
            "id": "COURIER_B",
            "name": "Adyar Express Med",
            "vehicle": "van",
            "capacity": 10,
            "available": True,
            "reliability": 0.94,
            "base_eta_minutes": 48
        },
        {
            "id": "COURIER_C",
            "name": "Marina Fast Track",
            "vehicle": "bike",
            "capacity": 4,
            "available": True,
            "reliability": 0.86,
            "base_eta_minutes": 62
        }
    ]
    COURIERS_FILE.write_text(json.dumps(default_couriers, indent=2))
    SHIPMENTS_FILE.write_text(json.dumps({}, indent=2))
    if clear_audit_history or not AUDIT_FILE.exists():
        AUDIT_FILE.write_text(json.dumps([], indent=2))


def inject_courier_breakdown(shipment_id: str, courier_id: str = "COURIER_A", event_time: str = "16:10"):
    """Marks a shipment's active courier as unavailable due to a simulated breakdown."""
    if not SHIPMENTS_FILE.exists():
        return {"injected": False, "reason": "shipments.json not found"}

    try:
        shipments = json.loads(SHIPMENTS_FILE.read_text())
    except json.JSONDecodeError:
        shipments = {}

    if shipment_id not in shipments:
        return {"injected": False, "reason": f"Shipment {shipment_id} not found"}

    shipments[shipment_id]["status"] = "courier_unavailable"
    shipments[shipment_id]["failure_reason"] = f"{courier_id} vehicle breakdown at {event_time}"

    if COURIERS_FILE.exists():
        try:
            couriers = json.loads(COURIERS_FILE.read_text())
        except json.JSONDecodeError:
            couriers = []
        for c in couriers:
            if c["id"] == courier_id:
                c["available"] = False
        COURIERS_FILE.write_text(json.dumps(couriers, indent=2))

    SHIPMENTS_FILE.write_text(json.dumps(shipments, indent=2))
    return {
        "injected": True,
        "shipment_id": shipment_id,
        "courier_id": courier_id,
        "status": "courier_unavailable",
        "detail": f"{courier_id} vehicle breakdown at {event_time}"
    }
