# F1 Throttle/Brake Fingerprint — Build Framework

**Project:** Interactive telemetry visualization tool using the OpenF1 API  
**Goal:** Compare throttle, brake, RPM, gear, and speed traces for all drivers at a user-selected circuit  
**Stack (recommended):** Python · Streamlit · Plotly · Pandas · Requests

---

## Overview of the Data Flow

```
User selects Year → Circuit → Session → Lap
        ↓
API: /meetings → /sessions → /laps (to pick lap)
        ↓
API: /car_data (throttle, brake, RPM, gear, speed) per driver
        ↓
Align traces by lap distance (via /location x/y coords)
        ↓
Plot synchronized multi-driver telemetry charts
```

---

## Phase 1 — Project Setup

**Goal:** Get a working environment with API access confirmed.

1. Create a Python virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies
   ```bash
   pip install streamlit plotly pandas requests python-dotenv
   ```

3. Create project structure
   ```
   f1_fingerprint/
   ├── app/
   │   ├── api.py            # All OpenF1 API calls
   │   ├── processor.py      # Data alignment and cleaning
   │   └── charts.py         # Plotly chart builders
   ├── main.py               # Streamlit UI
   ├── .env                  # BASE_API_URL=https://api.openf1.org/v1/
   └── requirements.txt
   ```

4. Verify API access — paste this in your browser to confirm it works:
   ```
   https://api.openf1.org/v1/meetings?year=2024&country_name=Italy
   ```

---

## Phase 2 — Build the API Layer (`api.py`)

**Goal:** Reliable, cached functions for every endpoint you need.

Write one function per endpoint. Use `@st.cache_data` on each to avoid hammering the API on every UI interaction.

### Functions to build:

| Function | Endpoint | Key params | Returns |
|---|---|---|---|
| `get_meetings(year)` | `/meetings` | `year` | List of races that year |
| `get_sessions(meeting_key)` | `/sessions` | `meeting_key` | FP1/FP2/FP3/Quali/Race for that GP |
| `get_drivers(session_key)` | `/drivers` | `session_key` | Driver numbers, names, team colors |
| `get_laps(session_key, driver_number)` | `/laps` | `session_key`, `driver_number` | All lap times for a driver |
| `get_car_data(session_key, driver_number, date_start, date_end)` | `/car_data` | session + time window | Throttle, brake, RPM, gear, speed at 3.7 Hz |
| `get_location(session_key, driver_number, date_start, date_end)` | `/location` | session + time window | X/Y car position at 3.7 Hz |

### Key implementation notes:

- The `car_data` and `location` endpoints return **time-series data, not lap-indexed data.** To get data for a specific lap, you need to know the lap's start and end timestamps — get these from `/laps` (`date_start` + `lap_duration`).
- `car_data` and `location` share the same 3.7 Hz sampling rate and can be merged on `date` after rounding timestamps.
- Rate limit on free tier: **3 requests/sec, 30 requests/min.** With 20 drivers you'll burn through this fast — add `time.sleep(0.4)` between calls or batch requests carefully.

---

## Phase 3 — Build the Data Processor (`processor.py`)

**Goal:** Turn raw time-series into comparable, chart-ready traces.

This is the hardest part. Raw telemetry is indexed by **timestamp**, but to compare drivers you need to align everything to a **common x-axis** (distance along the lap).

### Steps:

**3a. Compute lap distance from location data**

The `/location` endpoint gives X/Y coordinates at 3.7 Hz. Compute cumulative distance:
```python
import numpy as np

def compute_distance(df_location):
    dx = df_location['x'].diff().fillna(0)
    dy = df_location['y'].diff().fillna(0)
    df_location['delta_dist'] = np.sqrt(dx**2 + dy**2)
    df_location['distance'] = df_location['delta_dist'].cumsum()
    return df_location
```

**3b. Merge car_data onto location by timestamp**

Both share the same sampling rate. Merge on `date` (round to nearest 100ms if needed):
```python
df_merged = pd.merge_asof(
    df_car.sort_values('date'),
    df_location[['date','distance']].sort_values('date'),
    on='date', direction='nearest', tolerance=pd.Timedelta('150ms')
)
```

**3c. Normalize distance to 0–100%**

So every driver's lap maps to the same 0–100 x-axis regardless of lap time:
```python
df_merged['dist_pct'] = df_merged['distance'] / df_merged['distance'].max() * 100
```

**3d. Interpolate to a common grid**

Resample all drivers to the same 500-point distance grid for clean chart overlay:
```python
from scipy.interpolate import interp1d

grid = np.linspace(0, 100, 500)

def interpolate_channel(df, channel):
    f = interp1d(df['dist_pct'], df[channel], bounds_error=False, fill_value='extrapolate')
    return f(grid)
```

**3e. Build a per-driver data dict**

```python
{
  'VER': { 'throttle': [...500 values], 'brake': [...], 'rpm': [...], 'speed': [...], 'gear': [...], 'color': '#3671C6' },
  'PER': { ... },
  ...
}
```

---

## Phase 4 — Build the Charts (`charts.py`)

**Goal:** Stacked Plotly subplots, one panel per telemetry channel.

### Chart layout:

Use `plotly.subplots.make_subplots` with shared x-axis (distance %).

```
┌─────────────────────────────────────────┐
│  SPEED (km/h)                           │  ← shared x
├─────────────────────────────────────────┤
│  THROTTLE (%)                           │
├─────────────────────────────────────────┤
│  BRAKE (on/off)                         │
├─────────────────────────────────────────┤
│  RPM                                    │
├─────────────────────────────────────────┤
│  GEAR                                   │
└─────────────────────────────────────────┘
         0%          50%          100%
              Lap Distance
```

### Key Plotly tips:

- Use `shared_xaxes=True` in `make_subplots` — clicking/zooming one panel syncs all.
- Color each driver's line using `team_colour` from the `/drivers` endpoint (it's a hex value).
- Set `opacity=0.75` on all lines so overlapping traces are still readable.
- For brake: it's binary (0 or 100). Use `fill='tozeroy'` for a shaded area rather than a line — much easier to read.
- For gear: use a step plot (`line_shape='hvh'`).
- Add a hover tooltip that shows the driver code, channel value, and lap distance.

---

## Phase 5 — Build the UI (`main.py`)

**Goal:** Streamlit sidebar with cascading selectors that feed the chart.

### UI flow (cascading — each selector unlocks the next):

```
Year          [2023 / 2024 / 2025]
    ↓
Circuit       [Bahrain / Saudi Arabia / ...]   ← populated from get_meetings(year)
    ↓
Session       [Practice 1 / Qualifying / Race]  ← populated from get_sessions(meeting_key)
    ↓
Lap Number    [1–70]                            ← user types or sliders
    ↓
Drivers       [Checkboxes, all 20, colored]     ← populated from get_drivers(session_key)
    ↓
[LOAD TELEMETRY] button
```

### Sidebar implementation notes:

- Store selections in `st.session_state` so re-runs don't wipe the user's choices.
- Disable the "Load Telemetry" button until Year + Circuit + Session + at least 2 drivers are selected.
- Show a spinner (`with st.spinner(...)`) while fetching — car_data for 20 drivers is ~20 API calls.
- Display driver checkboxes with a colored square (using HTML/markdown) matching their team color.

---

## Phase 6 — Polish & Edge Cases

Once the core works, handle these:

| Issue | How to handle |
|---|---|
| Driver has no data for selected lap | Skip silently, show warning badge next to driver name |
| Location data gaps (GPS dropout) | Fill with linear interpolation before computing distance |
| Pit out / in laps (messy traces) | Flag with `is_pit_out_lap` from `/laps`, warn user |
| Safety car laps (unrepresentative) | Cross-reference `/race_control` for yellow/SC flags, optionally grey out |
| Comparing across sessions (quali vs race) | Separate session selector; label each trace with session type |
| Free tier rate limits | Add `time.sleep(0.4)` between `car_data` calls; cache aggressively |

---

## Phase 7 — Optional Enhancements

After the baseline is working:

- **Fastest lap auto-select** — default lap selector to each driver's fastest lap (from `/laps`, sorted by `lap_duration`)
- **Delta trace** — add a 6th panel showing time delta between Driver A and Driver B, computed from speed integration
- **Mini-sector color map** — add a track map panel colored by throttle % (requires mapping distance → X/Y back onto circuit shape)
- **Session comparison** — allow overlaying the same driver's qualifying lap vs. race lap
- **Export** — `st.download_button` to export the chart as PNG or the raw data as CSV

---

## API Endpoint Quick Reference

| What you need | Endpoint | Notes |
|---|---|---|
| List of races by year | `/meetings?year=YYYY` | Returns `meeting_key` |
| Sessions for a race | `/sessions?meeting_key=X` | Returns `session_key` |
| All drivers in session | `/drivers?session_key=X` | Returns `team_colour` (hex) |
| Lap timestamps | `/laps?session_key=X&driver_number=Y` | `date_start` + `lap_duration` = time window |
| Telemetry (3.7 Hz) | `/car_data?session_key=X&driver_number=Y&date>=A&date<=B` | Throttle, brake, RPM, gear, speed |
| Car position (3.7 Hz) | `/location?session_key=X&driver_number=Y&date>=A&date<=B` | X, Y, Z — use for lap distance |
| Race events/flags | `/race_control?session_key=X` | SC, yellow flags, incidents |

---

## Known Data Limitations

- **Segments (mini-sectors) are not available during races** — only in practice and qualifying
- **Location X/Y has no fixed origin** — it's relative, not GPS. Use it for relative distance, not absolute position
- **Car data is ~3.7 Hz** — that's one sample every ~270ms. At 300 km/h, that's ~22 meters between samples. Sufficient for trend analysis but not corner-level precision
- **Historical data starts from 2023 season only**
- **Team radio is a limited selection** — not every transmission is captured

---

## Reference Project

The tutorial project at `github.com/bordanattila/OpenF1_tutorial` uses the same API with Streamlit + Plotly for strategy data (lap times, tire stints, pit stops). Its `data_loader.py` and `data_processor.py` are good structural references even though this project uses different endpoints.