"""Optional Gemini incident analysis; recovery decisions stay in engine.py."""

import os
import json
import re


def analyze_incident(scenario, result, api_key):
    """Return an advisory explanation and a safe diagnostic, if one is needed."""
    if not api_key:
        return None, "GEMINI_API_KEY is not configured."

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        prompt = f"""Analyze this simulated logistics incident for an operations dashboard.
Explain the likely issue, what the recorded recovery did, and one practical follow-up.
Use at most 100 words. Treat the recorded outcome as authoritative; do not invent live
traffic, route, vehicle, or driver data. Label any suggestion as advisory.

Scenario: {scenario}
Recovery status: {result['status']}
Attempts: {result['attempts']}
Recorded event timeline: {result['timeline']}
"""
        response = client.models.generate_content(model=model, contents=prompt)
        text = response.text
        if text and text.strip():
            return text.strip(), None
        return None, "Gemini returned an empty response."
    except Exception as exc:
        # Keep external API failures from blocking the deterministic demo.
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        if code == 400:
            detail = "Gemini rejected the request (HTTP 400). Check the model and request configuration."
        elif code in (401, 403):
            detail = f"Gemini rejected authentication or API access (HTTP {code}). Check key validity and API restrictions."
        elif code == 404:
            detail = "Gemini could not find the requested model/API (HTTP 404). Check GEMINI_MODEL."
        elif code == 429:
            detail = "Gemini quota or rate limit was reached (HTTP 429). Check project quota and billing."
        elif code:
            detail = f"Gemini returned HTTP {code}."
        else:
            detail = f"Gemini request failed ({type(exc).__name__}). Check network access and the installed Gemini client."
        return None, detail


def recommend_options(issue, shipment_id, options, api_key):
    """Rank only pre-validated recovery choices; never lets Gemini execute or invent an action."""
    safe_options = [dict(option) for option in options]
    if not safe_options or not api_key:
        return safe_options, 'Rules-based recommendations (Gemini unavailable or not configured).'
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        model = os.getenv('GEMINI_MODEL', 'gemini-3.8-flash')
        prompt = f"""You rank safe, pre-approved logistics recovery candidates. Do not invent candidates or claim live data.
Return JSON only with this shape: {{"ranked_ids":["candidate-id",...],"reasons":{{"candidate-id":"short reason"}}}}.
Include each provided id exactly once. Incident: {issue}. Shipment: {shipment_id}.
Candidates: {json.dumps(safe_options)}"""
        response = client.models.generate_content(model=model, contents=prompt)
        raw = (response.text or '').strip()
        match = re.search(r'\{.*\}', raw, flags=re.DOTALL)
        payload = json.loads(match.group(0)) if match else None
        allowed = {item['id'] for item in safe_options}
        ranked = [item for item in (payload or {}).get('ranked_ids', []) if item in allowed]
        ranked.extend(item['id'] for item in safe_options if item['id'] not in ranked)
        reasons = (payload or {}).get('reasons', {})
        by_id = {item['id']: item for item in safe_options}
        result = []
        for rank, option_id in enumerate(ranked, 1):
            option = by_id[option_id]
            reason = reasons.get(option_id)
            if isinstance(reason, str) and reason.strip():
                option['reason'] = reason.strip()[:240]
            option['rank'] = rank
            option['source'] = 'Gemini-ranked, policy-validated'
            result.append(option)
        return result, None
    except Exception as exc:
        return safe_options, f'Gemini ranking failed ({type(exc).__name__}); rules-based order is shown.'
