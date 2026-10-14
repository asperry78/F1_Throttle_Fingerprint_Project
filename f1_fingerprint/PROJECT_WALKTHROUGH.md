# F1 Throttle/Brake Fingerprint: build and code walkthrough

This is a reconstruction of how the **current code** could have been built, not a record of the exact order in which the original work happened. Use it to understand and explain the project in your own words. [Project_outline.md](Project_outline.md) is an earlier plan; some of its proposed features are not present in the application.

## What problem the project solves

Raw F1 telemetry is a set of timestamped measurements. If two drivers take different amounts of time to complete a lap, plotting both against elapsed time makes the same corner appear at different horizontal positions. This dashboard turns those samples into traces against approximate **progress around the lap**, then overlays drivers' speed, throttle, brake, engine RPM, and gear. It is useful for exploring where drivers appear to brake, accelerate, or shift differently.

The product scope is specific: one meeting, one session, one lap **number**, and two or more selected drivers. It compares each selected driver's lap with that number. It does not automatically choose their fastest laps or compare different sessions.

## A plausible build sequence

### 1. Define the data and interface

Start from the question, “Where on a lap do drivers use the controls differently?” The minimum inputs are season, meeting, session, lap number, and drivers. The outputs are five charts sharing a lap-progress axis. Python is a practical choice because Pandas and NumPy handle time-series operations, Streamlit provides selectors without a separate frontend, and Plotly provides interactive linked charts.

The files split those jobs:

| File | Responsibility |
| --- | --- |
| `main.py` | Sidebar selections, load action, messages, and orchestration |
| `app/api.py` | OpenF1 requests, response conversion, date handling, and caching |
| `app/processor.py` | Approximate distance, time alignment, and resampling |
| `app/charts.py` | Five-panel Plotly figure |
| `requirements.txt` | Python dependencies |

### 2. Explore and connect the OpenF1 endpoints

The selectors form a chain of keys: `/meetings?year=...` supplies a `meeting_key`; `/sessions?meeting_key=...` supplies a `session_key`; `/drivers?session_key=...` supplies driver numbers and team colors. For each driver, `/laps?session_key=...&driver_number=...` supplies lap numbers, approximate start times, durations, and pit-out markers. The app requests `/car_data` and `/location` for the selected lap's time window. OpenF1 documents the channels and filters in its [API reference](https://openf1.org/docs/).

The car feed contains `date`, `speed` (km/h), `throttle` (%), `brake` (0 or 100), `rpm`, and `n_gear`. The location feed contains `date`, `x`, and `y`. Both are time series; neither feed directly gives a clean “distance along lap” field. The app deliberately does not plot other available fields, such as DRS, sector times, or race-control events.

In `app/api.py`, `_get_df` constructs the URL, sends a `requests.get` call with a 30-second timeout, expects a JSON list, and returns a Pandas DataFrame. HTTP 400/404 responses become empty data; a 429 response gets one retry after a one-second pause. Other HTTP errors and network exceptions propagate. Endpoint functions sort data and normalize what the UI needs: driver colors become `#RRGGBB`, lap timestamps become UTC datetimes, and lap duration becomes a computed end time:

```text
lap end = date_start + lap_duration (seconds)
```

The telemetry requests first send server-side `date>=` and `date<=` filters. If a filtered response is empty, they request that driver's full session and slice it locally to the lap window. The full-session fallback can be slow or large, especially for multiple drivers.

Streamlit's `@st.cache_data` keeps repeated API calls from firing on every widget rerun. Meetings, sessions, and drivers have a one-hour cache lifetime; laps and telemetry have a ten-minute lifetime. The full-session fallback calls also pause 0.4 seconds before a request. This is basic request pacing, not a guarantee against all rate limits.

### 3. Build the cascading sidebar

Streamlit reruns `main.py` after widget interaction. The year selector covers 2023 through the current UTC year and defaults to the latest year. Meetings are shown as “country - meeting”; sessions show name and type. The “Circuit” control actually selects a **meeting**, which matters because a meeting may have multiple sessions.

After choosing a session, the app lists its drivers with a team-color swatch and a checkbox. The user enters a lap number from 1 to 90. “Load Telemetry” is enabled only when at least two drivers are checked. Widget keys let Streamlit preserve selections across reruns. The button triggers a fresh processing pass; changing a widget afterward requires clicking it again to redraw the chart.

For each selected driver, `main.py` finds the matching `lap_number`, checks that the start and computed end timestamps exist, records a pit-out warning if indicated, obtains car and location data, and calls `build_driver_trace`. Missing laps or unusable telemetry are listed in a warning. If fewer than two valid traces remain, the app shows an error instead of drawing a one-driver comparison. A spinner covers the fetch and transform work.

### 4. Turn timestamps into lap progress

This is the central engineering step, implemented in `app/processor.py`.

1. **Approximate distance from positions.** Sort location samples by time, coerce `x` and `y` to numbers, and fill missing coordinate values by interpolation. For adjacent samples, calculate `sqrt((x_i-x_(i-1))² + (y_i-y_(i-1))²)`, then cumulatively sum those steps. The first step is zero. This gives a monotonically increasing *relative* distance for that selected time window. It is based on approximate coordinates, ignores `z`, and is not a calibrated track length in meters.
2. **Attach distance to car data.** Convert dates to UTC, round timestamps to 100 ms, then use Pandas `merge_asof` to find the nearest location distance for each car sample within 150 ms. Samples without a nearby location point are dropped. If no usable distance remains, the trace is rejected.
3. **Normalize the axis.** Divide each matched sample's cumulative distance by the maximum matched distance and multiply by 100. Now the two drivers' horizontal axes both run from roughly 0 to 100%, despite different lap durations or raw coordinate scales.
4. **Resample to the same grid.** Create 500 evenly spaced positions from 0 to 100. For each channel, remove missing values, sort by progress, keep one value for duplicate progress positions, then use NumPy linear interpolation. A missing channel or fewer than two usable points yields NaNs for that channel. `np.interp` fills outside the observed positions with endpoint values.

The returned dictionary has one 500-value array per channel plus the shared `dist_pct` array. The UI adds the driver's display code and color before plotting. “Aligned by distance” means comparing similar **estimated progress**, not proving that samples came from exactly the same physical point.

### 5. Make comparison readable

`app/charts.py` builds five vertically stacked Plotly subplots with a shared x-axis. Each driver gets a consistent color and legend group across panels. Speed, throttle, and RPM use lines; brake has a translucent fill to zero; gear uses a step-shaped line. Hover text shows driver code, channel value, and progress. The chart uses a dark theme, one visible legend entry per driver, and a 0–100% x-axis.

This presentation makes related events easier to inspect: a speed drop can be read alongside brake application, throttle release, RPM change, and a downshift. It does **not** establish why a driver was faster at a point; tire condition, traffic, fuel, weather, and flags are outside the plotted data.

## End-to-end example

Suppose you select a completed Grand Prix's qualifying session, lap 5, and two drivers. The sidebar fetches that year's meetings, the meeting's sessions, and the session's driver list. When you click Load, the app asks for each driver's lap 5 record. If a record starts at `T` and lasts `D` seconds, it requests car and location samples between `T` and `T+D`. It estimates each driver's path length from position samples, attaches those distances to car samples, maps each lap to 0–100%, and produces 500 values for each channel. Plotly draws ten traces: one per driver in each of five panels.

If a driver's lap 5 has no timestamp, no location data, or no usable time match, that driver is skipped. The remaining data is charted only if at least two drivers survive. A pit-out lap is reported, but its trace is still shown if usable.

## What to say about the engineering choices

- **Why align by progress?** Time alignment answers what happened at the same *moment*. This app asks what happened at approximately the same *place on the lap*, so normalizing cumulative location distance makes the overlay more meaningful.
- **Why join by nearest timestamp?** Car measurements and location measurements arrive as separate time series, so exact timestamp equality would discard many samples. A bounded nearest match is a simple way to associate them without accepting arbitrarily distant points.
- **Why interpolate?** Each driver has a different number and spacing of raw samples. A common 500-point grid gives Plotly matched x positions and makes overlays easy to inspect. It adds no new measured information.
- **Why cache?** Streamlit reruns the script when controls change. Caching reduces repeat API traffic and makes repeated exploration faster.
- **What was hardest?** The source feeds do not arrive as lap-distance traces. The hardest step is combining lap metadata, two time-series endpoints, timestamp matching, and progress normalization while handling missing data.

For an application essay, a truthful project arc is: you wanted to inspect driving technique through data; discovered that raw samples are time-indexed; built a pipeline to approximate lap position and align separate feeds; wrapped it in a selector-driven dashboard; and learned to treat the visualization as an exploratory tool with sampling and context limits. Describe what *you actually remember doing* in first person rather than presenting this reconstruction as a verified work log.

## Current limits and sensible next steps

OpenF1's published car/location data is roughly 3.7 Hz, and its location is approximate. Short braking or shift events can be missed. Linear interpolation is especially imperfect for discrete brake and gear values: it may display in-between values that were never measured. A future refinement could hold the last observed discrete state between samples. Pit-out laps are flagged but still plotted; safety car, tire, weather, and traffic context are not merged. Lap numbers are only meaningful within the selected session, and the app has no cross-session comparison, fastest-lap picker, lap-time delta, export, or track map.

The project has no automated test suite in this folder. A focused next test would feed synthetic car/location samples into `build_driver_trace` and check timestamp matching, normalization, missing data, and discrete-channel behavior. A separate live check should use a completed historical session, because the app depends on OpenF1 availability and data completeness.
