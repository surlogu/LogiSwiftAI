"""Agent state machine and courier scoring policy from LLD Section 5.3 & 5.4."""
from enum import Enum
from typing import Dict, Any, List, Optional


class AgentState(str, Enum):
    INIT = "INIT"
    ORDER_VALIDATION = "ORDER_VALIDATION"
    COURIER_SELECTION = "COURIER_SELECTION"
    SHIPMENT_ASSIGNED = "SHIPMENT_ASSIGNED"
    MONITORING = "MONITORING"
    RECOVERY_PLANNING = "RECOVERY_PLANNING"
    COURIER_REASSIGNED = "COURIER_REASSIGNED"
    CUSTOMER_NOTIFIED = "CUSTOMER_NOTIFIED"
    COMPLETED = "COMPLETED"
    ESCALATED = "ESCALATED"


def score_courier(
    courier: Dict[str, Any],
    max_eta_minutes: int = 120,
    required_capacity: int = 2,
    penalized_couriers: Optional[List[str]] = None
) -> float:
    """
    LLD Section 5.4 Formula:
    courier_score = reliability * 0.6 + eta_score * 0.3 + capacity_score * 0.1
    Plus penalty for previously failed couriers (learning from mistakes).
    """
    penalized_couriers = penalized_couriers or []
    reliability = float(courier.get("reliability", 0.5))
    base_eta = float(courier.get("base_eta_minutes", 60))
    capacity = float(courier.get("capacity", 1))

    eta_score = max(0.0, 1.0 - (base_eta / max_eta_minutes))
    capacity_score = min(capacity / max(required_capacity, 1), 1.0)

    score = (reliability * 0.6) + (eta_score * 0.3) + (capacity_score * 0.1)
    if courier["id"] in penalized_couriers:
        score -= 0.25
    return round(score, 4)
