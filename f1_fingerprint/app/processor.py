import numpy as np
import pandas as pd
from typing import Optional

CHANNELS = ["speed", "throttle", "brake", "rpm", "n_gear"]


def compute_distance(df_location: pd.DataFrame) -> pd.DataFrame:
    if df_location.empty:
        return df_location

    df = df_location.copy()
    df = df.sort_values("date").reset_index(drop=True)

    for col in ["x", "y"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df[["x", "y"]] = df[["x", "y"]].interpolate(limit_direction="both")
    df[["x", "y"]] = df[["x", "y"]].ffill().bfill()

    dx = df["x"].diff().fillna(0.0)
    dy = df["y"].diff().fillna(0.0)

    df["delta_dist"] = np.sqrt(dx**2 + dy**2)
    df["distance"] = df["delta_dist"].cumsum()
    return df


def merge_telemetry_by_time(df_car: pd.DataFrame, df_location: pd.DataFrame) -> pd.DataFrame:
    if df_car.empty or df_location.empty:
        return pd.DataFrame()

    car = df_car.copy().sort_values("date")
    loc = df_location[["date", "distance"]].copy().sort_values("date")

    car["date"] = pd.to_datetime(car["date"], utc=True, errors="coerce").dt.round("100ms")
    loc["date"] = pd.to_datetime(loc["date"], utc=True, errors="coerce").dt.round("100ms")

    merged = pd.merge_asof(
        car,
        loc,
        on="date",
        direction="nearest",
        tolerance=pd.Timedelta("150ms"),
    )
    merged = merged.dropna(subset=["distance"]).reset_index(drop=True)
    if merged.empty:
        return merged

    max_distance = merged["distance"].max()
    if pd.isna(max_distance) or max_distance <= 0:
        return pd.DataFrame()

    merged["dist_pct"] = (merged["distance"] / max_distance) * 100.0
    return merged


def _interp_channel(df: pd.DataFrame, channel: str, grid: np.ndarray) -> np.ndarray:
    x = pd.to_numeric(df["dist_pct"], errors="coerce").to_numpy()
    y = pd.to_numeric(df[channel], errors="coerce").to_numpy()

    valid = np.isfinite(x) & np.isfinite(y)
    x = x[valid]
    y = y[valid]

    if len(x) < 2:
        return np.full_like(grid, np.nan, dtype=float)

    order = np.argsort(x)
    x = x[order]
    y = y[order]

    unique_x, unique_idx = np.unique(x, return_index=True)
    y = y[unique_idx]

    if len(unique_x) < 2:
        return np.full_like(grid, np.nan, dtype=float)

    return np.interp(grid, unique_x, y)


def build_driver_trace(
    df_car: pd.DataFrame,
    df_location: pd.DataFrame,
    grid_points: int = 500,
) -> Optional[dict]:
    if df_car.empty or df_location.empty:
        return None

    loc_dist = compute_distance(df_location)
    merged = merge_telemetry_by_time(df_car, loc_dist)
    if merged.empty:
        return None

    grid = np.linspace(0, 100, grid_points)
    trace = {"dist_pct": grid.tolist()}

    for channel in CHANNELS:
        if channel not in merged.columns:
            trace[channel] = np.full(grid_points, np.nan).tolist()
            continue
        trace[channel] = _interp_channel(merged, channel, grid).tolist()

    return trace
