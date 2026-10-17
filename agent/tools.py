"""Crash-safe tool implementations with automatic cross-run feedback learning."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from agent.state import score_courier

BASE_DIR = Path(__file__).resolve().parent.parent
COURIERS_PATH = BASE_DIR / "simulator" / "couriers.json"
SHIPMENTS_PATH = BASE_DIR / "data" / "shipments.json"
AUDIT_PATH = BASE_DIR / "data" / "audit_log.json"


def _read_json(path: Path, default):
    """Crash-proof JSON reader: recovers automatically if file is empty or corrupted."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(default, indent=2))
        return default
    try:
        content = path.read_text().strip()
        return json.loads(content) if content else default
    except (json.JSONDecodeError, OSError):
        path.write_text(json.dumps(default, indent=2))
        return default


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def get_historical_failed_couriers() -> List[str]:
    """
    Reads `audit_log.json` to find couriers that previously broke down,
    EXCLUDING any entry where a human auditor marked `memory_revoked: True`.
    """
    logs = _read_json(AUDIT_PATH, [])
    return [
        entry["from_courier"]
        for entry in logs
        if entry.get("event") == "courier_reassigned"
        and entry.get("from_courier")
        and not entry.get("memory_revoked", False)
    ]


def revoke_courier_penalty(courier_id: str, auditor_reason: str = "False positive / External weather delay") -> Dict[str, Any]:
    """
    Marks past breakdown penalties for `courier_id` as `memory_revoked=True`
    and appends an immutable human_memory_audit entry to `audit_log.json`.
    """
    logs = _read_json(AUDIT_PATH, [])
    revoked_count = 0
    for entry in logs:
        if entry.get("event") == "courier_reassigned" and entry.get("from_courier") == courier_id:
            if not entry.get("memory_revoked"):
                entry["memory_revoked"] = True
                entry["auditor_reason"] = auditor_reason
                revoked_count += 1

    logs.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "order_id": "SYSTEM_AUDIT",
        "shipment_id": None,
        "event": "human_memory_override",
        "from_courier": courier_id,
        "to_courier": None,
        "reason": "wrong_memory_revoked",
        "agent_decision": f"Human auditor pardoned {courier_id} ({revoked_count} record(s)): {auditor_reason}"
    })
    _write_json(AUDIT_PATH, logs)
    return {"courier_id": courier_id, "revoked_records": revoked_count, "auditor_reason": auditor_reason}



def validate_order(order: Dict[str, Any]) -> Dict[str, Any]:
    required = ["order_id", "pickup", "drop", "deadline"]
    missing = [f for f in required if not order.get(f)]
    valid = len(missing) == 0
    return {
        "valid": valid,
        "missing_fields": missing,
        "message": "Order valid" if valid else f"Missing mandatory fields: {', '.join(missing)}"
    }


def get_available_couriers(
    required_capacity: int = 2,
    penalized_couriers: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Scores couriers using LLD formula + historical failure penalties from audit_log.json."""
    couriers = _read_json(COURIERS_PATH, [])
    historical_penalties = get_historical_failed_couriers()
    combined_penalties = list(set((penalized_couriers or []) + historical_penalties))

    available = [c for c in couriers if c.get("available", False)]
    for c in available:
        c["score"] = score_courier(
            c,
            required_capacity=required_capacity,
            penalized_couriers=combined_penalties
        )
        c["penalized_by_feedback_loop"] = c["id"] in combined_penalties
    available.sort(key=lambda x: -x["score"])
    return {"available_couriers": available, "penalized_couriers": combined_penalties}


def assign_courier(order_id: str, courier_id: str) -> Dict[str, Any]:
    couriers = _read_json(COURIERS_PATH, [])
    courier = next((c for c in couriers if c["id"] == courier_id and c.get("available")), None)
    if not courier:
        return {"success": False, "error": f"Courier {courier_id} not found or unavailable"}

    shipments = _read_json(SHIPMENTS_PATH, {})
    shipment_id = f"SHP-{order_id}"
    shipment_record = {
        "shipment_id": shipment_id,
        "order_id": order_id,
        "courier_id": courier_id,
        "previous_courier_id": None,
        "status": "assigned",
        "assigned_at": int(time.time()),
        "recovery_attempts": 0,
        "eta_minutes": courier["base_eta_minutes"]
    }
    shipments[shipment_id] = shipment_record
    _write_json(SHIPMENTS_PATH, shipments)
    return {"success": True, "shipment": shipment_record}


def get_shipment_status(shipment_id: str) -> Dict[str, Any]:
    shipments = _read_json(SHIPMENTS_PATH, {})
    if shipment_id not in shipments:
        return {"status": "not_found", "error": f"Shipment {shipment_id} not found"}

    shp = shipments[shipment_id]
    if shp["status"] in ("assigned", "reassigned"):
        shp["status"] = "delivered"
        shipments[shipment_id] = shp
        _write_json(SHIPMENTS_PATH, shipments)

    return {"status": shp["status"], "shipment": shp}


def reassign_courier(shipment_id: str, new_courier_id: str) -> Dict[str, Any]:
    shipments = _read_json(SHIPMENTS_PATH, {})
    if shipment_id not in shipments:
        return {"success": False, "error": f"Shipment {shipment_id} not found"}

    couriers = _read_json(COURIERS_PATH, [])
    new_courier = next((c for c in couriers if c["id"] == new_courier_id and c.get("available")), None)
    if not new_courier:
        return {"success": False, "error": f"Replacement courier {new_courier_id} unavailable"}

    shp = shipments[shipment_id]
    shp["previous_courier_id"] = shp["courier_id"]
    shp["courier_id"] = new_courier_id
    shp["status"] = "reassigned"
    shp["recovery_attempts"] = int(shp.get("recovery_attempts", 0)) + 1
    shp["eta_minutes"] = new_courier["base_eta_minutes"]

    shipments[shipment_id] = shp
    _write_json(SHIPMENTS_PATH, shipments)
    return {"success": True, "shipment": shp}


def notify_customer(order_id: str, message: str) -> Dict[str, Any]:
    return {
        "notified": True,
        "order_id": order_id,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


def write_audit_log(entry: Dict[str, Any]) -> Dict[str, Any]:
    logs = _read_json(AUDIT_PATH, [])
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **entry
    }
    logs.append(record)
    _write_json(AUDIT_PATH, logs)
    return {"logged": True, "entry": record}


def read_audit_log() -> List[Dict[str, Any]]:
    return _read_json(AUDIT_PATH, [])
