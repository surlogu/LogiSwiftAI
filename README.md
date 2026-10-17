# LogiSwift AI — Autonomous Logistics Handling Agent

A working hackathon prototype that demonstrates **Observe → Reason → Act → Verify → Learn** with auditable self-healing logistics scenarios.

## Run

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open the local Streamlit URL (usually http://localhost:8501).

## Gemini incident analysis (optional)

The recovery engine remains deterministic. To add an AI-generated explanation after an incident, set a Gemini API key in your shell before starting Streamlit:

```bash
export GEMINI_API_KEY="your-new-restricted-key"
streamlit run app.py
```

In PowerShell, use `$env:GEMINI_API_KEY="your-new-restricted-key"` before `streamlit run app.py`. For Streamlit Community Cloud, add `GEMINI_API_KEY` under the app's **Secrets** settings. Never commit the Gemini key or expose it in frontend code. The default model is `gemini-3.8-flash`; set `GEMINI_MODEL` to override it. If the key is missing or Gemini is unavailable, the app continues with deterministic recovery and shows no AI analysis.

## Google Maps route view (optional)

The **Route Map** tab displays approximate straight-line connections between the synthetic origin and destination cities. It does not calculate road routes or track shipments. Set a Google Maps JavaScript API key as `GOOGLE_MAPS_API_KEY` in your shell or Streamlit **Secrets**. Enable the Maps JavaScript API and restrict the key to that API and your app's HTTP referrers (for local use, `http://localhost:8501/*`). The browser can see a Maps JavaScript key, so HTTP referrer restrictions are essential. Maps requires billing to be enabled for the Google Cloud project.

## Demo (2 minutes)

1. Select **Traffic delay**, click **Execute autonomous recovery**. First alternate route fails verification, second passes.
2. Select **Vehicle breakdown**. Agent assigns simulated replacement vehicle and verifies ETA.
3. Select **AI API outage**. Deterministic fallback restores agent operation without API credentials.
4. Select **Unrecoverable incident**. Agent escalates instead of claiming an unsafe recovery.
5. Open **Feedback & Audit** to show persistent SQLite history and strategy ranking based on previously verified outcomes.
6. Use **Run all six demo scenarios** for metrics and charts.

## Architecture

- `app.py`: Streamlit UI, demo controls, charts, audit download.
- `engine.py`: deterministic incident diagnosis, action selection, verification, feedback ranking, SQLite persistence.
- `gemini_analysis.py`: optional AI-generated incident explanation; it does not select or execute recovery actions.
- `maps_view.py`: Google Maps display for the synthetic shipment city pairs.
- `tests/test_engine.py`: pytest regression tests.

## Tests

```bash
pytest -q
```

## Performance & truthfulness

Agent runtime measures the **local simulated decision engine only**, not network latency or real-world delivery time. Shipments, routes, deadlines, vehicle assignments and outcomes are synthetic. The self-healing feedback loop changes the **ranking of known strategies** using verified successes; it does **not** retrain an AI model. Optional Gemini analysis provides an advisory explanation, and Google Maps displays the synthetic city pairs; neither controls recovery or provides live logistics data. There are no real notifications or actual rerouting. The base deterministic demo still runs without API keys after dependency installation.

## Submission pitch

> LogiSwift AI is a self-healing logistics operations agent. Instead of stopping at alert generation, it diagnoses disruptions, selects corrective actions, verifies outcomes, learns which strategies have worked before, and safely escalates when automated recovery is impossible. The demo provides a reproducible, auditable execution trace and runtime metrics without external dependencies.
