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
- `tests/test_engine.py`: pytest regression tests.

## Tests

```bash
pytest -q
```

## Performance & truthfulness

Agent runtime measures the **local simulated decision engine only**, not network latency or real-world delivery time. Shipments, routes, deadlines, vehicle assignments and outcomes are synthetic. The self-healing feedback loop changes the **ranking of known strategies** using verified successes; it does **not** retrain an AI model. No live logistics APIs, external AI model, real notifications, or actual rerouting are included. The deterministic implementation intentionally requires no API key and runs offline after dependency installation.

## Submission pitch

> LogiSwift AI is a self-healing logistics operations agent. Instead of stopping at alert generation, it diagnoses disruptions, selects corrective actions, verifies outcomes, learns which strategies have worked before, and safely escalates when automated recovery is impossible. The demo provides a reproducible, auditable execution trace and runtime metrics without external dependencies.
