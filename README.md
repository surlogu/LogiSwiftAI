# 🚚 LogiSwift AI — Autonomous Same-Day Parcel Exception Handler & Control Tower

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Google ADK](https://img.shields.io/badge/Google%20ADK-2.12+-orange.svg)](https://google.github.io/adk-docs/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-red.svg)](https://streamlit.io/)
[![Tests](https://img.shields.io/badge/tests-11%20passed-brightgreen.svg)](https://docs.pytest.org/)

An autonomous logistics dispatch and self-healing delivery control tower built with **Google ADK (`google-adk`)**, **Gemini Flash** multimodal perception, and a **zero-key offline deterministic simulator**.

When a delivery courier encounters a mid-transit breakdown (e.g. traffic gridlock or bike engine failure in Chennai), LogiSwift AI automatically detects the exception, scores available backup couriers using live reliability and vehicle capacity, reassigns the parcel, updates the customer, and logs an immutable audit trail—**all in under 2 seconds without human bottlenecking**.

---

## 📋 Table of Contents
1. [Quick Overview: What Does It Do?](#-quick-overview-what-does-it-do)
2. [Prerequisites](#-prerequisites)
3. [Step-by-Step Setup Guide](#-step-by-step-setup-guide)
4. [How to Run and Check It (Choose Your Mode)](#-how-to-run-and-check-it)
   - [Mode 1: Instant Terminal Demo (CLI)](#mode-1-instant-terminal-demo-fastest)
   - [Mode 2: Interactive Web Control Tower UI (Streamlit)](#mode-2-interactive-web-control-tower-ui-recommended)
   - [Mode 3: Official Google ADK Web UI Playground](#mode-3-official-google-adk-web-ui-playground)
   - [Mode 4: Automated Verification Test Suite](#mode-4-automated-verification-test-suite)
5. [Key Features & Architecture](#-key-features--architecture)
6. [Troubleshooting & FAQ](#-troubleshooting--faq)

---

## 💡 Quick Overview: What Does It Do?

Imagine you run an express delivery company in Chennai. A customer orders urgent medical supplies to be delivered from **T. Nagar** to **Adyar** by 18:00.

1. **Intake & Validation**: LogiSwift validates the address, cargo priority, and parcel manifest.
2. **Optimal Dispatch**: It dispatches **Courier A** (fast bike, 55-min ETA).
3. **Mid-Route Failure**: At 16:10, Courier A reports a breakdown.
4. **Autonomous Self-Healing (A2A Handoff)**:
   - The Root Coordinator hands off the incident to the **Recovery Specialist Agent**.
   - The specialist filters available couriers, calculates composite multi-factor scores, and reassigns the shipment to **Courier B** (van, 94% reliability).
5. **Customer Update & Immutable Audit**:
   - The **Customer & Audit Agent** sends an automated ETA notification to the recipient and commits the complete incident timeline to `audit_log.json`.
6. **Cross-Run Learning & HITL Audit**:
   - On future orders, LogiSwift remembers past failures to avoid unreliable couriers.
   - Dispatchers can inspect or revoke false-positive penalties through a Human-in-the-Loop (HITL) audit dashboard.

---

## 📦 Prerequisites

Before starting, make sure you have:
- **Python 3.10, 3.11, 3.12, 3.13, or 3.14** installed on your system.
  ```bash
  python3 --version
  ```
- **Git** installed on your computer.
- *(Optional)* A **Google Gemini API Key**:
  - You can get one for free at [Google AI Studio](https://aistudio.google.com/apikey).
  - **No API key? No problem!** LogiSwift includes a built-in deterministic offline engine that runs all simulations and tests with 100% functionality even without an internet connection or API key.

---

## 🛠️ Step-by-Step Setup Guide

Follow these 4 simple steps to set up the project on your machine:

### Step 1: Open Terminal and Navigate to the Project
```bash
cd LogiSwiftAI
```

### Step 2: Create and Activate a Python Virtual Environment

- **macOS / Linux**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- **Windows (Command Prompt)**:
  ```cmd
  python -m venv .venv
  .venv\Scripts\activate.bat
  ```

- **Windows (PowerShell)**:
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  ```
*(You will see `(.venv)` appear at the beginning of your terminal prompt.)*

### Step 3: Install Required Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure Your Environment File (Optional)
Copy the example environment file:
```bash
cp .env.example .env
```
Open `.env` in any text editor:
```env
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GEMINI_API_KEY=your_gemini_api_key_here

# Model Right-Sizing (Independent Free-Tier Quota Pools)
GEMINI_ROOT_MODEL=gemini-3.8-flash
GEMINI_LITE_MODEL=gemini-flash-lite-latest
```
- Paste your Gemini API key in `GEMINI_API_KEY`.
- If you don't have an API key, leave it as is; the system will automatically run in offline simulation mode.

---

## 🎮 How to Run and Check It

Choose any of the following modes to see LogiSwift in action:

### Mode 1: Instant Terminal Demo (Fastest)
Run the end-to-end self-healing simulation directly in your terminal:
```bash
python -m agent.main
```
**What will happen?**
You will see a formatted step-by-step trace:
1. `Intake_Monitor_Agent` validates `ORDER-101` and assigns `COURIER_A`.
2. A simulated courier breakdown is injected at 16:10.
3. An Agent-to-Agent (A2A) handoff transfers control to `Recovery_Specialist_Agent`.
4. `Recovery_Specialist_Agent` scores alternatives and reassigns the order to `COURIER_B`.
5. An A2A handoff transfers control to `Customer_Audit_Agent`, which sends the customer confirmation and records the audit log.

---

### Mode 2: Interactive Web Control Tower UI (Recommended)
Launch the interactive web application in your browser:
```bash
streamlit run app.py
```
Open your browser to: **`http://localhost:8501`**

#### What to test on the Web UI:
- **💡 Quick Sample Presets**:
  Click any preset button at the top:
  - `📦 ORDER-101 (Medical / High Priority)`
  - `💻 ORDER-102 (Electronics / Normal)`
  - `🥛 ORDER-103 (Perishables / Express)`
  *(The form will instantly populate with valid pickup, drop, and deadline details!)*
- **🚨 Failure Simulator Mode**:
  Select between:
  - `0 Failures: Normal dispatch & direct delivery`
  - `1 Failure: Courier A breakdown at 4:10 PM -> Reassign Courier B (Self-Healing)`
  - `2 Failures: Cascading breakdown -> Reassign Courier C`
  - `3 Failures: Fleet exhausted -> Safe human escalation`
- **▶️ Click "Run Dispatch Simulation"**:
  Watch the real-time execution trace, view the interactive Plotly timeline chart, and inspect the self-healing recovery actions.
- **🛡️ Tab 3: Human-in-the-Loop (HITL) Memory Audit**:
  View past courier penalties recorded by the feedback loop. Click **"Revoke / Pardon"** to clear a false positive and see the courier immediately restored to top priority on the next run!

---

### Mode 3: Official Google ADK Web UI Playground
Test the multi-agent hierarchy using Google ADK's built-in developer interface:
```bash
adk web .
```
Open your browser to the URL printed in the terminal (default: **`http://localhost:8000`**).
- Select the `LogiSwift_Coordinator_Agent`.
- Send a conversational dispatch command:
  > *"Please dispatch order ORDER-101 from T. Nagar to Adyar with medical supplies by 18:00. Self-heal if the courier breaks down."*
- Watch the live Google ADK agent thought trace, tool invocations, and sub-agent transfers in real time.

---

### Mode 4: Automated Verification Test Suite
Run the test suite to verify all 11 unit, integration, and flow tests:
```bash
pytest -q
```
**Expected Output:**
```text
...........                                                              [100%]
11 passed in 0.28s
```
This tests:
- Order validation and schema integrity
- Single failure self-healing and recovery reassignments
- Maximum retry escalation boundaries
- A2A handoffs (`Intake` $\rightarrow$ `Recovery` $\rightarrow$ `Audit`)
- Cross-run feedback loop persistence
- Human-in-the-loop (HITL) penalty revocation

---

## 🏗️ Key Features & Architecture

```text
LogiSwiftAI/
├── agent/
│   ├── adk_agent.py          # Google ADK A2A Multi-Agent hierarchy + Waterfall Cascade
│   ├── agent.py              # Entrypoint exposing root_agent for `adk web .`
│   ├── main.py               # Deterministic orchestrator & CLI execution engine
│   ├── prompts.py            # System prompts & operational instructions
│   ├── state.py              # State machine & multi-factor scoring algorithms
│   └── tools.py              # Autonomous tools (validation, scoring, assignment, audit)
├── simulator/
│   ├── couriers.json         # Active courier fleet (vehicle, capacity, reliability)
│   └── failure_simulator.py  # Mid-route breakdown & anomaly injection
├── data/
│   ├── shipments.json        # Live shipment tracking states
│   └── audit_log.json        # Append-only immutable incident audit trail
├── app.py                    # Streamlit Control Tower & HITL Audit Dashboard
├── engine.py                 # Core SQLite incident database & multimodal telemetry
└── tests/
    ├── test_engine.py        # Engine & database unit tests
    └── test_flow.py          # End-to-end A2A & feedback learning tests
```

### 🧠 Model Right-Sizing & Multi-Model Waterfall Cascade
To prevent rate-limit interruptions (`429 RESOURCE_EXHAUSTED`) on free-tier Gemini accounts:
1. **Model Right-Sizing**: High-level coordination runs on `gemini-3.8-flash`, while sub-agents and image perception run on `gemini-flash-lite-latest` (separate quota pools).
2. **Waterfall Cascade**: If the primary model encounters a quota limit, the orchestrator automatically cascades down:
   $$\text{gemini-3.8-flash} \longrightarrow \text{gemini-flash-lite-latest} \longrightarrow \text{gemini-3.5-flash-lite} \longrightarrow \text{gemini-3.1-flash-lite} \longrightarrow \text{Offline Simulator}$$

---

## ❓ Troubleshooting & FAQ

### Q: Do I need a paid Google Cloud or Gemini account?
**No.** You can run LogiSwift with a free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey). If you have no key at all, LogiSwift will automatically run in offline mode using the deterministic simulation engine.

### Q: What should I do if I see a `429 RESOURCE_EXHAUSTED` error?
LogiSwift's built-in waterfall cascade automatically detects 429 quota exhaustion and retries with lightweight fallback models. You can also customize your default models in `.env`:
```env
GEMINI_ROOT_MODEL=gemini-flash-lite-latest
GEMINI_LITE_MODEL=gemini-flash-lite-latest
```

### Q: How do I reset all courier and shipment data to fresh defaults?
Run this one-liner in Python to reset couriers and clear active shipments:
```bash
python -c "from simulator.failure_simulator import reset_simulation_data; reset_simulation_data(clear_audit_history=True)"
```

### Q: Can I run this on Windows?
**Yes.** All file paths use `pathlib.Path` cross-platform handling, and virtual environment activation instructions for PowerShell and Command Prompt are provided above.
