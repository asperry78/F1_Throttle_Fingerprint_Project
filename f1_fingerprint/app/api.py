import os
import time
from datetime import timedelta
from typing import Optional

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

BASE_API_URL = os.getenv("BASE_API_URL", "https://api.openf1.org/v1/").rstrip("/")
DEFAULT_TIMEOUT = 30


def _build_url(endpoint: str) -> str:
    return f"{BASE_API_URL}/{endpoint.lstrip('/')}"


def _get_df(endpoint: str, params: dict) -> pd.DataFrame:
    response = requests.get(_build_url(endpoint), params=params, timeout=DEFAULT_TIMEOUT)

    # OpenF1 may return 400/404 for unavailable slices; treat as no data, not a hard crash.
    if response.status_code in (400, 404):
        return pd.DataFrame()

    # Back off once on rate limiting.
    if response.status_code == 429:
        time.sleep(1.0)
        response = requests.get(_build_url(endpoint), params=params, timeout=DEFAULT_TIMEOUT)
        if response.status_code in (400, 404, 429):
            return pd.DataFrame()

    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return pd.DataFrame()
    return pd.DataFrame(payload)


def _to_openf1_datetime(value: pd.Timestamp) -> str:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _normalize_hex_color(value: Optional[str]) -> str:
    if not value:
        return "#999999"
    value = str(value).strip().lstrip("#")
    if len(value) == 6:
        return f"#{value.upper()}"
    return "#999999"


@st.cache_data(show_spinner=False, ttl=3600)
def get_meetings(year: int) -> pd.DataFrame:
    df = _get_df("meetings", {"year": year})
    if "meeting_key" in df.columns:
        df = df.sort_values([c for c in ["date_start", "meeting_key"] if c in df.columns]).reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False, ttl=3600)
def get_sessions(meeting_key: int) -> pd.DataFrame:
    df = _get_df("sessions", {"meeting_key": meeting_key})
    if "session_key" in df.columns:
        df = df.sort_values([c for c in ["date_start", "session_key"] if c in df.columns]).reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False, ttl=3600)
def get_drivers(session_key: int) -> pd.DataFrame:
    df = _get_df("drivers", {"session_key": session_key})
    if df.empty:
        return df

    if "team_colour" in df.columns:
        df["team_colour"] = df["team_colour"].map(_normalize_hex_color)
    else:
        df["team_colour"] = "#999999"

    if "driver_number" in df.columns:
        df = df.sort_values("driver_number").reset_index(drop=True)
    return df


@st.cache_data(show_spinner=False, ttl=600)
def get_laps(session_key: int, driver_number: int) -> pd.DataFrame:
    df = _get_df("laps", {"session_key": session_key, "driver_number": driver_number})
    if df.empty:
        return df

    if "lap_number" in df.columns:
        df = df.sort_values("lap_number").reset_index(drop=True)

    if "date_start" in df.columns:
        df["date_start"] = pd.to_datetime(df["date_start"], utc=True, errors="coerce")

    if "lap_duration" in df.columns:
        df["lap_duration"] = pd.to_numeric(df["lap_duration"], errors="coerce")

    if "date_start" in df.columns and "lap_duration" in df.columns:
        df["date_end"] = df["date_start"] + df["lap_duration"].apply(
            lambda x: timedelta(seconds=float(x)) if pd.notna(x) else pd.NaT
        )

    return df


def _slice_time_window(df: pd.DataFrame, date_start: pd.Timestamp, date_end: pd.Timestamp) -> pd.DataFrame:
    if df.empty or "date" not in df.columns:
        return pd.DataFrame()

    ts_start = pd.Timestamp(date_start)
    ts_end = pd.Timestamp(date_end)
    if ts_start.tzinfo is None:
        ts_start = ts_start.tz_localize("UTC")
    else:
        ts_start = ts_start.tz_convert("UTC")
    if ts_end.tzinfo is None:
        ts_end = ts_end.tz_localize("UTC")
    else:
        ts_end = ts_end.tz_convert("UTC")

    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], utc=True, errors="coerce")
    out = out[(out["date"] >= ts_start) & (out["date"] <= ts_end)]
    return out.reset_index(drop=True)


@st.cache_data(show_spinner=False, ttl=600)
def get_car_data_full(session_key: int, driver_number: int) -> pd.DataFrame:
    time.sleep(0.4)
    df = _get_df("car_data", {"session_key": session_key, "driver_number": driver_number})
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    return df


@st.cache_data(show_spinner=False, ttl=600)
def get_location_full(session_key: int, driver_number: int) -> pd.DataFrame:
    time.sleep(0.4)
    df = _get_df("location", {"session_key": session_key, "driver_number": driver_number})
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    return df


@st.cache_data(show_spinner=False, ttl=600)
def get_car_data(
    session_key: int,
    driver_number: int,
    date_start: pd.Timestamp,
    date_end: pd.Timestamp,
) -> pd.DataFrame:
    # Try server-side date filters first; some sessions currently 404 on filtered calls.
    params = {
        "session_key": session_key,
        "driver_number": driver_number,
        "date>=": _to_openf1_datetime(date_start),
        "date<=": _to_openf1_datetime(date_end),
    }
    df = _get_df("car_data", params)
    if not df.empty:
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
        return df

    full_df = get_car_data_full(session_key, driver_number)
    return _slice_time_window(full_df, date_start, date_end)


@st.cache_data(show_spinner=False, ttl=600)
def get_location(
    session_key: int,
    driver_number: int,
    date_start: pd.Timestamp,
    date_end: pd.Timestamp,
) -> pd.DataFrame:
    params = {
        "session_key": session_key,
        "driver_number": driver_number,
        "date>=": _to_openf1_datetime(date_start),
        "date<=": _to_openf1_datetime(date_end),
    }
    df = _get_df("location", params)
    if not df.empty:
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
        return df

    full_df = get_location_full(session_key, driver_number)
    return _slice_time_window(full_df, date_start, date_end)
