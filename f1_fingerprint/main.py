from datetime import datetime

import pandas as pd
import streamlit as st

from app.api import get_car_data, get_drivers, get_laps, get_location, get_meetings, get_sessions
from app.charts import build_telemetry_figure
from app.processor import build_driver_trace

st.set_page_config(page_title="F1 Throttle/Brake Fingerprint", layout="wide")
st.title("F1 Throttle/Brake Fingerprint")
st.caption("Compare speed, throttle, brake, RPM, and gear traces by lap distance.")


def _meeting_label(row: pd.Series) -> str:
    country = row.get("country_name", "Unknown Country")
    name = row.get("meeting_name", "Unknown Meeting")
    return f"{country} - {name}"


def _session_label(row: pd.Series) -> str:
    session_name = row.get("session_name", "Session")
    session_type = row.get("session_type", "")
    return f"{session_name} ({session_type})" if session_type else str(session_name)


def _driver_code(row: pd.Series) -> str:
    return str(
        row.get("name_acronym")
        or row.get("broadcast_name")
        or row.get("last_name")
        or row.get("full_name")
        or row.get("driver_number")
    )


def _driver_color(row: pd.Series) -> str:
    color = str(row.get("team_colour", "#999999")).strip()
    if not color.startswith("#"):
        color = f"#{color}"
    if len(color) != 7:
        color = "#999999"
    return color


current_year = datetime.utcnow().year
year_options = [y for y in range(2023, current_year + 1)]

with st.sidebar:
    st.header("Telemetry Selection")

    year = st.selectbox("Year", options=year_options, index=len(year_options) - 1, key="year")

    meetings = get_meetings(year)
    if meetings.empty:
        st.warning("No meetings found for this year.")
        st.stop()

    meeting_options = {int(row["meeting_key"]): _meeting_label(row) for _, row in meetings.iterrows()}
    meeting_key = st.selectbox(
        "Circuit",
        options=list(meeting_options.keys()),
        format_func=lambda k: meeting_options[k],
        key="meeting_key",
    )

    sessions = get_sessions(int(meeting_key))
    if sessions.empty:
        st.warning("No sessions found for the selected meeting.")
        st.stop()

    session_options = {int(row["session_key"]): _session_label(row) for _, row in sessions.iterrows()}
    session_key = st.selectbox(
        "Session",
        options=list(session_options.keys()),
        format_func=lambda k: session_options[k],
        key="session_key",
    )

    lap_number = st.number_input("Lap Number", min_value=1, max_value=90, value=1, step=1, key="lap_number")

    drivers = get_drivers(int(session_key))
    if drivers.empty:
        st.warning("No drivers found for this session.")
        st.stop()

    st.markdown("### Drivers")
    selected_driver_numbers = []

    for _, row in drivers.iterrows():
        driver_no = int(row["driver_number"])
        code = _driver_code(row)
        color = _driver_color(row)

        left, right = st.columns([1, 3])
        with left:
            st.markdown(
                f"<div style='width:16px;height:16px;border-radius:3px;background:{color};'></div>",
                unsafe_allow_html=True,
            )
        with right:
            checked = st.checkbox(f"{code}  #{driver_no}", key=f"driver_{driver_no}")
        if checked:
            selected_driver_numbers.append(driver_no)

    load_clicked = st.button(
        "Load Telemetry",
        type="primary",
        disabled=not (year and meeting_key and session_key and len(selected_driver_numbers) >= 2),
    )

if not load_clicked:
    st.info("Pick a year, circuit, session, lap, and at least two drivers, then click Load Telemetry.")
    st.stop()

driver_lookup = {
    int(row["driver_number"]): {
        "code": _driver_code(row),
        "color": _driver_color(row),
    }
    for _, row in drivers.iterrows()
}

telemetry_by_driver = {}
skipped = []
pit_laps = []

with st.spinner("Fetching and aligning telemetry..."):
    for driver_no in selected_driver_numbers:
        laps = get_laps(int(session_key), int(driver_no))
        if laps.empty or "lap_number" not in laps.columns:
            skipped.append(f"{driver_lookup[driver_no]['code']} (no lap data)")
            continue

        lap_row = laps[laps["lap_number"] == int(lap_number)]
        if lap_row.empty:
            skipped.append(f"{driver_lookup[driver_no]['code']} (lap {lap_number} unavailable)")
            continue

        lap = lap_row.iloc[0]
        date_start = lap.get("date_start")
        date_end = lap.get("date_end")
        if pd.isna(date_start) or pd.isna(date_end):
            skipped.append(f"{driver_lookup[driver_no]['code']} (invalid lap timestamps)")
            continue

        if bool(lap.get("is_pit_out_lap", False)):
            pit_laps.append(driver_lookup[driver_no]["code"])

        car = get_car_data(int(session_key), int(driver_no), date_start, date_end)
        loc = get_location(int(session_key), int(driver_no), date_start, date_end)

        trace = build_driver_trace(car, loc)
        if not trace:
            skipped.append(f"{driver_lookup[driver_no]['code']} (no telemetry for selected lap)")
            continue

        telemetry_by_driver[driver_lookup[driver_no]["code"]] = {
            **trace,
            "color": driver_lookup[driver_no]["color"],
        }

if skipped:
    st.warning("Skipped drivers: " + ", ".join(skipped))

if pit_laps:
    st.info("Pit-out laps detected: " + ", ".join(sorted(set(pit_laps))))

if len(telemetry_by_driver) < 2:
    st.error("Not enough valid driver data to compare. Try another lap or session.")
    st.stop()

fig = build_telemetry_figure(telemetry_by_driver)
st.plotly_chart(fig, use_container_width=True)
