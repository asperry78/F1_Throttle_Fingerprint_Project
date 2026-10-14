# F1 Throttle/Brake Fingerprint

An interactive dashboard for comparing Formula 1 drivers' speed, throttle, brake, RPM, and gear traces on the same lap of a session. It uses [OpenF1](https://openf1.org/docs/) data, [Streamlit](https://streamlit.io/) for the interface, and [Plotly](https://plotly.com/python/) for the charts.

Select a season, Grand Prix meeting, session, lap number, and at least two drivers. The app aligns their telemetry by **approximate lap progress (0–100%)** so you can compare where they accelerate, brake, and shift, even when their lap times differ.

## Run locally

You need Python 3.11+ and an internet connection. OpenF1's historical data starts in 2023 and is available without an API key; live data has separate access requirements. Run these commands from the `f1_fingerprint` directory (enter it with `cd f1_fingerprint` if you cloned the enclosing repository).

On macOS or Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run main.py
```

On Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run main.py
```

Open the local address printed by Streamlit, usually `http://localhost:8501`. If PowerShell prevents activation, you can use `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.\.venv\Scripts\python.exe -m streamlit run main.py` instead.

No `.env` file is required. The app defaults to `https://api.openf1.org/v1/`. To use another compatible endpoint, set `BASE_API_URL` in your environment or in a local `.env` file:

```env
BASE_API_URL=https://api.openf1.org/v1/
```

## Use the dashboard

1. Choose a **Year**, **Circuit** (the Grand Prix meeting), and **Session** in the sidebar. For a first try, pick a completed historical session.
2. Enter a **Lap Number** and tick at least two drivers.
3. Click **Load Telemetry**. Hover or zoom on the stacked charts to inspect the traces; the horizontal axis is shared across all five channels.

The app reports drivers whose selected lap or telemetry is missing and flags pit-out laps. If fewer than two usable traces remain, choose another lap or session. Fetching several drivers can take time because each requires lap, car, and location requests.

## How it works

`main.py` handles the Streamlit controls and coordinates loading. `app/api.py` queries OpenF1 and caches results. `app/processor.py` computes cumulative distance from location samples, joins it to car telemetry by timestamp, and interpolates each channel onto a common 500-point lap-progress grid. `app/charts.py` draws five linked Plotly panels with driver/team colors.

The distance axis is inferred from approximate car positions; it is not an official measured track distance. The available telemetry is sampled at roughly 3.7 Hz, and interpolation can smooth brief events or show intermediate values for discrete channels such as brake and gear. The dashboard compares the same **lap number within one session**, not each driver's fastest lap. It does not account for traffic, tire condition, flags, or weather when interpreting differences.

For a detailed, code-grounded build walkthrough and interview notes, see [PROJECT_WALKTHROUGH.md](PROJECT_WALKTHROUGH.md). The older [Project_outline.md](Project_outline.md) is a planning document and includes ideas that were not implemented.

Data source: [OpenF1 API documentation](https://openf1.org/docs/). OpenF1 is an unofficial project and is not affiliated with Formula 1.
