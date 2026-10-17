"""Optional Gemini incident analysis; recovery decisions stay in engine.py."""

import os
import json
import re


DEFAULT_MODEL = 'gemini-3.8-flash'
DEFAULT_FALLBACK_MODELS = ('gemini-3.6-flash', 'gemini-3.5-flash-lite')


def _model_candidates():
    """Return the configured primary model followed by unique fallback models."""
    primary = os.getenv('GEMINI_MODEL', DEFAULT_MODEL).strip() or DEFAULT_MODEL
    configured = os.getenv('GEMINI_FALLBACK_MODELS')
    fallbacks = list(DEFAULT_FALLBACK_MODELS) if configured is None else [
        name.strip() for name in configured.split(',') if name.strip()
    ]
    return list(dict.fromkeys([primary, *fallbacks]))


def _error_code(exc):
    for attr in ('code', 'status_code', 'http_status'):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            match = re.search(r'\b(408|429|500|502|503|504)\b', value)
            if match:
                return int(match.group(1))
    match = re.search(r'\b(408|429|500|502|503|504)\b', str(exc))
    return int(match.group(1)) if match else None


def _is_retryable(exc):
    code = _error_code(exc)
    if code in (408, 429, 500, 502, 503, 504):
        return True
    message = f'{type(exc).__name__} {exc}'.lower()
    return any(term in message for term in (
        'resource_exhausted', 'rate_limit', 'quota_exceeded', 'too_many_requests',
        'deadline_exceeded', 'timed out', 'timeout', 'service_unavailable',
    ))


def _generate_with_fallback(client, contents):
    """Try another configured model only after a rate limit or transient failure."""
    models = _model_candidates()
    errors = []
    for index, model in enumerate(models):
        try:
            response = client.models.generate_content(model=model, contents=contents)
            return response, model, errors
        except Exception as exc:
            errors.append((model, exc))
            if not _is_retryable(exc) or index == len(models) - 1:
                break
    return None, None, errors


def _fallback_note(model, errors):
    if not errors or model == errors[0][0]:
        return None
    failed = ', '.join(name for name, _ in errors)
    return f'Gemini fallback succeeded with {model} after a rate limit or transient error on {failed}.'


def _failure_note(errors):
    if not errors:
        return 'Gemini returned no response.'
    attempted = ', '.join(name for name, _ in errors)
    last_model, last_error = errors[-1]
    code = _error_code(last_error)
    detail = f'HTTP {code}' if code else type(last_error).__name__
    if any(_is_retryable(error) for _, error in errors):
        return f'Gemini fallback models were exhausted ({attempted}; last error {detail}). Check model-specific and project quotas, then try again.'
    return f'Gemini request failed for {last_model} ({detail}). Check the model name, key, and API access.'


def analyze_incident(scenario, result, api_key):
    """Return an advisory explanation and a safe diagnostic, if one is needed."""
    if not api_key:
        return None, "GEMINI_API_KEY is not configured."

    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        prompt = f"""Analyze this simulated logistics incident for an operations dashboard.
Explain the likely issue, what the recorded recovery did, and one practical follow-up.
Use at most 100 words. Treat the recorded outcome as authoritative; do not invent live
traffic, route, vehicle, or driver data. Label any suggestion as advisory.

Scenario: {scenario}
Recovery status: {result['status']}
Attempts: {result['attempts']}
Recorded event timeline: {result['timeline']}
"""
        response, model, errors = _generate_with_fallback(client, prompt)
        if response is None:
            return None, _failure_note(errors)
        text = response.text
        if text and text.strip():
            note = _fallback_note(model, errors)
            return text.strip(), note
        return None, f'Gemini returned an empty response from {model}.'
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
        prompt = f"""You rank safe, pre-approved logistics recovery candidates. Do not invent candidates or claim live data.
Return JSON only with this shape: {{"ranked_ids":["candidate-id",...],"reasons":{{"candidate-id":"short reason"}}}}.
Include each provided id exactly once. Incident: {issue}. Shipment: {shipment_id}.
Candidates: {json.dumps(safe_options)}"""
        response, model, errors = _generate_with_fallback(client, prompt)
        if response is None:
            return safe_options, _failure_note(errors)
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
            option['source'] = f'Gemini-ranked, policy-validated ({model})'
            result.append(option)
        return result, _fallback_note(model, errors)
    except Exception as exc:
        return safe_options, f'Gemini ranking failed ({type(exc).__name__}); rules-based order is shown.'
