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

1. Open **Ops Console**.
2. Click **Create and run breakdown demo**. It creates a shipment, assigns a driver, starts the trip, reports a simulated vehicle breakdown, and applies the highest-ranked eligible replacement-driver choice.
3. Open **Agent Control Tower**. Review the ranked recovery options. Choose a different eligible driver or vehicle if desired, then click **Apply selected recovery**. The shipment ID remains the same.
4. Open **Driver App** and select the replacement driver shown in the Control Tower.
5. Click **Start trip**, then **Mark delivered**.
6. Return to the home page or Control Tower to review the updated shipment and audit events.

The demo needs at least two available drivers. After a shipment is delivered, its driver becomes available again.

### Manual path

1. In **Ops Console**, create a shipment with pickup, destination, deadline, package type, and priority.
2. Assign an available driver.
3. In **Driver App**, select that driver and shipment, then click **Start trip**.
4. Report an issue and provide a short description. A vehicle breakdown automatically triggers replacement-driver recovery; other issue types show their safe recommendation or dispatcher escalation.
5. In **Agent Control Tower**, review the recommendations and apply a different eligible action, driver, or vehicle if needed.
6. The selected driver starts the trip and marks the same shipment delivered.

All roles and delivery actions are simulated. The app does not contact real drivers, customers, or shipment systems.

## 4. Optional Gemini recommendations

Gemini can rank the pre-approved recovery options. The deterministic app logic validates the available choices and performs the state change; Gemini cannot execute actions or invent driver IDs.

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
- `pages/3_Agent_Control_Tower.py`: review/change recovery options and inspect audit events.
- `pages/4_Route_Map.py`, `maps_view.py`: Google Maps road routes and selectable alternatives.
- `engine.py`: shipment lifecycle, recovery policy, driver availability, SQLite, and audit events.
- `gemini_analysis.py`: optional constrained Gemini ranking and incident analysis.
- `tests/test_engine.py`: recovery and shipment lifecycle tests.
