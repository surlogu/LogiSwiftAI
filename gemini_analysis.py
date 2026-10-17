"""Optional Gemini incident analysis; recovery decisions stay in engine.py."""

import os


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
