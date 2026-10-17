"""Optional Gemini incident analysis; recovery decisions stay in engine.py."""

import os


def analyze_incident(scenario, result, api_key):
    """Return a short advisory explanation, or None when Gemini is unavailable."""
    if not api_key:
        return None

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
        return response.text.strip() if response.text else None
    except Exception:
        # Keep external API failures from blocking the deterministic demo.
        return None
