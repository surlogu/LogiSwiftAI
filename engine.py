"""Framework-driven Multimodal & Auditable Logistics Recovery Agent (End-to-End Simulation)."""
import json
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv

load_dotenv()

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

DB_PATH = Path(__file__).with_name('logiswift.db')

SCENARIOS = {
    'Traffic delay': {
        'failure': 'TRAFFIC', 'eta': 95, 'deadline': 65,
        'weight_tons': 18.0, 'max_weight_tons': 20.0, 'temp_c': 4.0, 'max_temp_c': 8.0
    },
    'Vehicle breakdown': {
        'failure': 'BREAKDOWN', 'eta': 120, 'deadline': 85,
        'weight_tons': 15.0, 'max_weight_tons': 20.0, 'temp_c': 6.5, 'max_temp_c': 8.0
    },
    'Driver unavailable': {
        'failure': 'DRIVER', 'eta': 90, 'deadline': 80,
        'weight_tons': 14.0, 'max_weight_tons': 20.0, 'temp_c': 3.5, 'max_temp_c': 8.0
    },
    'AI API outage': {
        'failure': 'AI_TIMEOUT', 'eta': 75, 'deadline': 90,
        'weight_tons': 12.0, 'max_weight_tons': 20.0, 'temp_c': 3.0, 'max_temp_c': 8.0
    },
    'Capacity overload': {
        'failure': 'CAPACITY', 'eta': 100, 'deadline': 90,
        'weight_tons': 24.5, 'max_weight_tons': 20.0, 'temp_c': 4.5, 'max_temp_c': 8.0
    },
    'Unrecoverable incident': {
        'failure': 'NO_CAPACITY', 'eta': 160, 'deadline': 60,
        'weight_tons': 28.0, 'max_weight_tons': 20.0, 'temp_c': 11.0, 'max_temp_c': 8.0
    },
}

ACTIONS = {
    'TRAFFIC': [
        ('alternate_route_A', -10, 0.0, 0.5),
        ('alternate_route_B', -38, 0.0, -0.5)
    ],
    'BREAKDOWN': [
        ('replacement_vehicle', -48, 0.0, -2.0)
    ],
    'DRIVER': [
        ('backup_driver', -20, 0.0, 0.0)
    ],
    'AI_TIMEOUT': [
        ('rule_based_fallback', -1, 0.0, 0.0)
    ],
    'CAPACITY': [
        ('reroute_heavy_bridge_fail', -5, 0.0, 0.5),
        ('split_load', -25, -8.0, -0.5)
    ],
    'NO_CAPACITY': [
        ('escalate_to_dispatch', 0, 0.0, 0.0)
    ],
}


@dataclass
class SimulationState:
    shipment_id: str
    scenario: str
    failure: str
    eta: int
    deadline: int
    weight_tons: float
    max_weight_tons: float
    temp_c: float
    max_temp_c: float
    multimodal_findings: str = "Standard telemetry only (no media uploaded)"


def connect(path=DB_PATH):
    conn = sqlite3.connect(str(path))
    conn.execute(
        '''CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            shipment_id TEXT,
            scenario TEXT,
            status TEXT,
            attempts INTEGER,
            latency_ms REAL,
            timeline TEXT
        )'''
    )
    conn.execute(
        '''CREATE TABLE IF NOT EXISTS mistake_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            failure_type TEXT,
            action TEXT,
            reason TEXT,
            review_status TEXT DEFAULT 'AUTO_APPLIED',
            auditor_note TEXT DEFAULT '',
            created_at TEXT
        )'''
    )
    # Safe migration if table was created without review_status
    existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(mistake_memory)").fetchall()]
    if "review_status" not in existing_cols:
        conn.execute("ALTER TABLE mistake_memory ADD COLUMN review_status TEXT DEFAULT 'AUTO_APPLIED'")
    if "auditor_note" not in existing_cols:
        conn.execute("ALTER TABLE mistake_memory ADD COLUMN auditor_note TEXT DEFAULT ''")
    conn.commit()
    return conn


def sample_shipments():
    cities = [
        ('Chennai', 'Bengaluru'),
        ('Mumbai', 'Pune'),
        ('Hyderabad', 'Vijayawada'),
        ('Delhi', 'Jaipur'),
        ('Coimbatore', 'Kochi')
    ]
    result = []
    for i in range(1, 21):
        src, dst = cities[(i - 1) % len(cities)]
        scenario = list(SCENARIOS)[(i - 1) % len(SCENARIOS)]
        result.append({
            'Shipment': f'LS{1000 + i}',
            'Origin': src,
            'Destination': dst,
            'Priority': 'High' if i % 4 == 0 else 'Normal',
            'Status': 'At Risk' if i % 3 == 0 else 'In Transit',
            'Scenario': scenario
        })
    return result


def analyze_multimodal_input(
    image_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg",
    manifest_notes: str = "",
    scenario: str = "Traffic delay"
) -> Dict[str, Any]:
    cfg = SCENARIOS.get(scenario, SCENARIOS['Traffic delay'])
    if scenario == 'AI API outage' or not image_bytes:
        summary = (
            f"Deterministic Multimodal Sensor Scan: Scenario='{scenario}', "
            f"Manifest='{manifest_notes or 'Standard manifest'}' | "
            f"Weight={cfg['weight_tons']}t, Reefer={cfg['temp_c']}°C"
        )
        return {"mode": "deterministic", "findings": summary}

    api_key = os.environ.get("GEMINI_API_KEY")
    if GENAI_AVAILABLE and api_key and api_key != "your_gemini_api_key_here":
        lite_candidates = [
            os.environ.get("GEMINI_LITE_MODEL", "gemini-flash-lite-latest"),
            "gemini-3.5-flash-lite",
            "gemini-3.1-flash-lite",
        ]
        prompt = (
            "You are a Multimodal Logistics Diagnostic Agent. Inspect this image alongside "
            f"the manifest notes ('{manifest_notes}') and active scenario ('{scenario}'). "
            "Identify any physical cargo damage, axle overload risk, or cold-chain breach in 1 concise sentence."
        )
        client = genai.Client(api_key=api_key)
        last_error = None
        for model_name in lite_candidates:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[
                        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                        prompt
                    ]
                )
                return {"mode": model_name, "findings": response.text.strip()}
            except Exception as exc:
                last_error = exc
                continue

        return {
            "mode": "fallback_after_error",
            "findings": f"All Gemini Vision models unreachable ({last_error}); switched to deterministic visual telemetry."
        }

    return {
        "mode": "simulated_multimodal",
        "findings": f"Simulated Vision Scan ({len(image_bytes)} bytes, {mime_type}): Cargo seal verified; {manifest_notes or 'No anomalies beyond scenario constraints'}."
    }


def strategy_order(failure, conn):
    """
    Only applies penalties from `mistake_memory` where review_status != 'REVOKED_FALSE_POSITIVE'.
    If a human audits and revokes a wrong memory, the strategy immediately recovers its rank!
    """
    raw_candidates = ACTIONS[failure][:]
    history_rows = conn.execute("SELECT timeline FROM incidents WHERE status='RECOVERED'").fetchall()
    mistake_rows = conn.execute(
        """SELECT action, COUNT(*) FROM mistake_memory
           WHERE failure_type=? AND review_status != 'REVOKED_FALSE_POSITIVE'
           GROUP BY action""",
        (failure,)
    ).fetchall()

    scores = {item[0]: 0 for item in raw_candidates}
    for (raw,) in history_rows:
        for event in json.loads(raw):
            act = event.get('action')
            if event.get('verified') is True and act in scores:
                scores[act] += 2

    for act, penalty_count in mistake_rows:
        if act in scores:
            scores[act] -= penalty_count * 2

    ranked = sorted(raw_candidates, key=lambda a: -scores[a[0]])
    return [(item[0], item[1]) for item in ranked]


def get_action_spec(failure: str, action_name: str):
    for item in ACTIONS[failure]:
        if item[0] == action_name:
            if len(item) == 2:
                return item[0], item[1], 0.0, 0.0
            return item
    raise KeyError(f"Unknown action {action_name}")


def simulate_step(state: SimulationState, action_name: str) -> Dict[str, Any]:
    name, eta_delta, weight_delta, temp_delta = get_action_spec(state.failure, action_name)

    if name == 'rule_based_fallback':
        return {
            'verified': True,
            'eta': state.eta,
            'weight_tons': state.weight_tons,
            'temp_c': state.temp_c,
            'detail': 'AI unavailable; validated deterministic engine activated'
        }

    if name == 'escalate_to_dispatch':
        return {
            'verified': False,
            'eta': state.eta,
            'weight_tons': state.weight_tons,
            'temp_c': state.temp_c,
            'detail': 'No safe capacity available; human escalation required'
        }

    new_eta = state.eta + eta_delta
    new_weight = round(state.weight_tons + weight_delta, 2)
    new_temp = round(state.temp_c + temp_delta, 2)

    eta_ok = new_eta <= state.deadline
    weight_ok = new_weight <= state.max_weight_tons
    temp_ok = new_temp <= state.max_temp_c
    verified = eta_ok and weight_ok and temp_ok

    reasons = [f"New ETA {new_eta}m vs deadline {state.deadline}m"]
    if not weight_ok:
        reasons.append(f"Overweight {new_weight}t > {state.max_weight_tons}t limit")
    if not temp_ok:
        reasons.append(f"Temp excursion {new_temp}°C > {state.max_temp_c}°C limit")

    return {
        'verified': verified,
        'eta': new_eta,
        'weight_tons': new_weight,
        'temp_c': new_temp,
        'detail': " | ".join(reasons)
    }


def recover(
    shipment_id,
    scenario,
    conn=None,
    max_attempts=3,
    image_bytes: Optional[bytes] = None,
    mime_type: str = "image/jpeg",
    manifest_notes: str = ""
):
    if scenario not in SCENARIOS:
        raise ValueError('Unknown scenario')
    if max_attempts < 1:
        raise ValueError('max_attempts must be positive')

    own = conn is None
    conn = conn or connect()
    start = time.perf_counter()

    cfg = SCENARIOS[scenario]
    mm_result = analyze_multimodal_input(image_bytes, mime_type, manifest_notes, scenario)

    sim_state = SimulationState(
        shipment_id=shipment_id,
        scenario=scenario,
        failure=cfg['failure'],
        eta=cfg['eta'],
        deadline=cfg['deadline'],
        weight_tons=cfg.get('weight_tons', 15.0),
        max_weight_tons=cfg.get('max_weight_tons', 20.0),
        temp_c=cfg.get('temp_c', 4.0),
        max_temp_c=cfg.get('max_temp_c', 8.0),
        multimodal_findings=mm_result['findings']
    )

    timeline: List[Dict[str, Any]] = [
        {
            'stage': 'OBSERVE',
            'detail': (
                f"{sim_state.failure} detected; ETA {sim_state.eta}m, deadline {sim_state.deadline}m | "
                f"Load {sim_state.weight_tons}t/{sim_state.max_weight_tons}t | "
                f"Temp {sim_state.temp_c}°C | {sim_state.multimodal_findings}"
            )
        },
        {
            'stage': 'REASON',
            'detail': 'Rank candidate strategies using mistake memory & verify against ETA, weight, and thermal constraints'
        }
    ]

    status = 'ESCALATED'
    attempts = 0

    for name, _ in strategy_order(sim_state.failure, conn)[:max_attempts]:
        attempts += 1
        step_out = simulate_step(sim_state, name)

        sim_state.eta = step_out['eta']
        sim_state.weight_tons = step_out['weight_tons']
        sim_state.temp_c = step_out['temp_c']
        verified = step_out['verified']

        timeline.append({
            'stage': 'ACT + VERIFY',
            'action': name,
            'attempt': attempts,
            'verified': verified,
            'detail': step_out['detail']
        })

        if verified:
            status = 'RECOVERED'
            break
        else:
            conn.execute(
                'INSERT INTO mistake_memory (failure_type, action, reason, created_at) VALUES (?,?,?,?)',
                (sim_state.failure, name, step_out['detail'], datetime.now(timezone.utc).isoformat())
            )

    timeline.append({
        'stage': 'LEARN',
        'detail': (
            'Verified strategy promoted & failed attempts penalized in mistake memory'
            if status == 'RECOVERED'
            else 'No verified recovery; failure patterns logged & human review triggered'
        )
    })

    latency = round((time.perf_counter() - start) * 1000, 3)
    conn.execute(
        'INSERT INTO incidents (created_at,shipment_id,scenario,status,attempts,latency_ms,timeline) VALUES (?,?,?,?,?,?,?)',
        (datetime.now(timezone.utc).isoformat(), shipment_id, scenario, status, attempts, latency, json.dumps(timeline))
    )
    conn.commit()

    result = {
        'shipment_id': shipment_id,
        'scenario': scenario,
        'status': status,
        'attempts': attempts,
        'latency_ms': latency,
        'timeline': timeline,
        'final_eta': sim_state.eta,
        'deadline': sim_state.deadline,
        'final_weight_tons': sim_state.weight_tons,
        'final_temp_c': sim_state.temp_c,
        'multimodal_mode': mm_result['mode']
    }
    if own:
        conn.close()
    return result


def history(conn=None):
    own = conn is None
    conn = conn or connect()
    rows = conn.execute(
        'SELECT id,created_at,shipment_id,scenario,status,attempts,latency_ms,timeline FROM incidents ORDER BY id DESC'
    ).fetchall()
    result = [
        dict(zip(('id', 'created_at', 'shipment_id', 'scenario', 'status', 'attempts', 'latency_ms', 'timeline'), row))
        for row in rows
    ]
    if own:
        conn.close()
    return result


def audit_mistake_memory(mistake_id: int, new_status: str, auditor_note: str = "", conn=None) -> dict:
    """
    Human-in-the-Loop (HITL) control to approve or revoke a learned mistake.
    Valid statuses: 'APPROVED_BY_HUMAN', 'REVOKED_FALSE_POSITIVE', 'AUTO_APPLIED'
    """
    valid_statuses = {'APPROVED_BY_HUMAN', 'REVOKED_FALSE_POSITIVE', 'AUTO_APPLIED'}
    if new_status not in valid_statuses:
        raise ValueError(f"Invalid review_status: {new_status}")

    own = conn is None
    conn = conn or connect()
    conn.execute(
        "UPDATE mistake_memory SET review_status=?, auditor_note=? WHERE id=?",
        (new_status, auditor_note, mistake_id)
    )
    conn.commit()
    if own:
        conn.close()
    return {"mistake_id": mistake_id, "review_status": new_status, "auditor_note": auditor_note}


def mistake_log(conn=None):
    own = conn is None
    conn = conn or connect()
    rows = conn.execute(
        'SELECT id,failure_type,action,reason,review_status,auditor_note,created_at FROM mistake_memory ORDER BY id DESC'
    ).fetchall()
    result = [
        dict(zip(('id', 'failure_type', 'action', 'reason', 'review_status', 'auditor_note', 'created_at'), row))
        for row in rows
    ]
    if own:
        conn.close()
    return result