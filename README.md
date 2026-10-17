# LogiSwift AI — Shipment Recovery Demo

LogiSwift AI is a Streamlit multipage logistics simulation backed by SQLite. It has separate **Ops Console**, **Driver App**, **Agent Control Tower**, and **Road Routes** screens. Shipment state and audit events are shared between the screens.

## 1. Requirements

- Python 3.10 or newer
- Internet access to install packages
- Google API keys are optional. The shipment workflow runs without them.

## 2. Install and start

### Linux or macOS

From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

### Windows PowerShell

From the project folder:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Open the local URL printed in the terminal, usually `http://localhost:8501`. Keep the terminal running while using the app. Use the left sidebar to switch between screens. The first launch creates `logiswift.db`; it stores local demo data and is ignored by Git.

## 3. Run the full shipment demo

### Fast path: one-click breakdown simulation

1. Open **Ops Console → Create & assign**.
2. Click **Create and run breakdown demo**. It creates a shipment, assigns a driver, starts the trip, reports a simulated breakdown, and asks the agent for recovery options. The shipment is not reassigned yet.
3. Open **Ops Console → Recovery approvals**, inspect the current suggestion, then accept it or reject it with an optional reason. A rejection is logged and advances to the next option; if every option is rejected, the shipment is escalated.
4. Open **Agent Control Tower** to review the decision and audit log. The same shipment ID is kept.
5. Open **Driver App** and select the approved replacement driver.
6. Click **Start trip**, then **Mark delivered**.
7. Return to the home page or Control Tower to review the updated shipment and audit events.

The demo needs at least two available drivers. After a shipment is delivered, its driver becomes available again.

### Manual path

1. In **Ops Console → Create & assign**, create a shipment with pickup, destination, deadline, package type, and priority.
2. Assign an available driver.
3. In **Driver App**, select that driver and shipment, then click **Start trip**.
4. Report an issue and provide a short description. The agent prepares options but does not change the shipment yet.
5. In **Ops Console → Recovery approvals**, accept a suggestion to apply it, or reject it to log the decision and request the next available option.
6. Use **Agent Control Tower** to inspect the reasoning and history. The selected driver starts the trip and marks the same shipment delivered in **Driver App**.

All roles and delivery actions are simulated. The app does not contact real drivers, customers, or shipment systems.

## 4. Optional Gemini recommendations

Gemini can rank the pre-approved recovery options, but cannot execute them. Ops must accept an option in **Ops Console** before the driver or route assignment changes. Rejections and approvals, including the optional rejection reason, are written to SQLite and shown in the audit history.

After the first decision for an issue type, later incidents of that type are ranked locally from Ops approval/rejection history. The app skips the Gemini request for those repeat issues, saving tokens while favoring options Ops accepted and lowering options Ops rejected. This is deterministic feedback ranking; it does not train or modify the Gemini model.

Create `.streamlit/secrets.toml` in the project folder and add:

```toml
GEMINI_API_KEY = "your restricted Gemini API key"
```

The default model is `gemini-3.8-flash`. To select another supported model, set `GEMINI_MODEL` in your shell before starting Streamlit. If the key is missing or the Gemini request fails, the app uses rules-based recommendations and the shipment simulation still works.

## 5. Optional Google road routes

Add your restricted Maps JavaScript key to the same `.streamlit/secrets.toml` file:

```toml
GOOGLE_MAPS_API_KEY = "your restricted Maps JavaScript API key"
```

For route alternatives, the Google Cloud project must have billing enabled and both the **Maps JavaScript API** and **Routes API** enabled. Restrict the browser key to those APIs and your app’s HTTP referrers, such as `http://localhost:8501/*` and `http://127.0.0.1:8501/*` for local use. The browser can see this key, so keep its referrer and API restrictions enabled.

Open **Road Routes**, choose a shipment, and select among the route cards shown under the map. Google computes driving routes between the shipment’s city endpoints; these are route estimates, not live vehicle tracking. Google may return fewer alternatives than requested. See Google’s [Routes setup guide](https://developers.google.com/maps/documentation/javascript/routes/start) and [alternative routes guide](https://developers.google.com/maps/documentation/javascript/routes/get-alternative-routes).

If the map reports an API error, verify the key restrictions, enabled APIs, billing, and the referrer for the exact local URL you opened. The shipment and driver screens do not depend on Maps.

## 6. Run tests

Activate the virtual environment first, then run:

```bash
python -m pytest -q
```

The tests use in-memory SQLite. They do not send requests to Gemini or Google Maps.

## Project files

- `app.py`: shared home page and shipment overview.
- `pages/1_Ops_Console.py`: create shipments, assign drivers, run the quick demo.
- `pages/2_Driver_App.py`: start trips, report issues, mark delivery.
- `pages/3_Agent_Control_Tower.py`: read agent recommendations, Ops decisions, and audit events.
- `pages/4_Route_Map.py`, `maps_view.py`: Google Maps road routes and selectable alternatives.
- `engine.py`: shipment lifecycle, recovery policy, driver availability, SQLite, and audit events.
- `gemini_analysis.py`: optional constrained Gemini ranking and incident analysis.
- `tests/test_engine.py`: recovery and shipment lifecycle tests.
