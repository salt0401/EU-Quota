# -*- coding: utf-8 -*-
"""
Forecasting Data Loader  [EXPERIMENTAL — beta/]
Loads the daily quota history, merges into time series, and prepares
Prophet-format DataFrames.

This module is fully independent of the main src/ pipeline.

Usage:
    from beta.forecasting import load_history, get_quota_time_series
    data = load_history()                       # published daily history
    ts = get_quota_time_series(data, order_number="099491")

Two sources exist, and only one of them is still fed:

    load_history()        <- USE THIS. data/published/quota_history_<YEAR>.csv,
                             358 rows/day, written by the daily unattended run
                             on the company server and committed to git.
    load_all_snapshots()  <- LEGACY. data/snapshots/*.xlsx, produced by the
                             login-triggered snapshot mechanism that was
                             removed in v2.10.0. Nothing writes these any more;
                             kept only to read an archive if one turns up.
"""

import os
import sys
import re
import glob
from datetime import datetime
from typing import Optional

import pandas as pd


def _get_snapshot_folder() -> str:
    """Get the snapshots folder path (self-contained, no dependency on src/)."""
    # beta/ is one level inside project root
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(project_root, "data", "snapshots")

# Module-level cache to avoid re-reading Excel files on repeated calls
_snapshot_cache: Optional[pd.DataFrame] = None

# Minimum days of data needed for Prophet to produce meaningful forecasts
MIN_PROPHET_DAYS = 30

# The EU/UK quota regimes changed on this date. The old safeguard (189 EU
# quotas) ended 30 June 2026; the replacement (283 EU quotas, different order
# numbers and volumes) started 1 July 2026. Pre- and post-boundary rows are
# DIFFERENT QUOTA POPULATIONS, so a model trained across the boundary is
# fitting a discontinuity, not a trend. load_history() filters to the current
# regime by default; pass regime_start=None only if you know why.
REGIME_START = "2026-07-01"

# Column mapping from the published history CSV onto the names the rest of this
# module already uses, so get_quota_time_series / get_all_quota_ids /
# get_snapshot_summary work unchanged against either source.
_HISTORY_COLUMN_MAP = {
    "date": "snapshot_date",
    "quota_category": "input_quota_category",
    "country": "origin",
    "balance_remaining_t": "balance",
}


def _get_published_folder() -> str:
    """Path to data/published/ (self-contained, no dependency on src/)."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(project_root, "data", "published")


def load_history(
    history_path: Optional[str] = None,
    year: Optional[int] = None,
    region: Optional[str] = None,
    regime_start: Optional[str] = REGIME_START,
) -> pd.DataFrame:
    """
    Load the published daily history — **the preferred forecasting source**.

    ``data/published/quota_history_<YEAR>.csv`` carries one row per quota per
    day (358/day: 283 EU + 75 UK), written by the daily unattended run and
    committed to git. It superseded the local snapshot workbooks that
    ``load_all_snapshots()`` reads, which are no longer produced by anything.

    The returned frame is deliberately shaped like ``load_all_snapshots()``
    output — ``snapshot_date``, ``order_number``, ``balance``,
    ``input_quota_category``, ``origin`` — so every other function in this
    module works against it without change. Native history columns
    (``pct_allocated``, ``quota_limit_t``, ``awaiting_allocation_t`` …) are kept
    alongside, since they are richer than the old snapshots.

    Rows whose ``scrape_status`` is not ``'ok'`` are dropped: a failed scrape is
    a missing observation, not a zero, and feeding it to a model would invent a
    cliff that never happened.

    Args:
        history_path: Explicit CSV path. Defaults to the current year's file,
            or ``year``'s file if given.
        year: Calendar year to load. Defaults to the newest file present.
        region: ``'EU'`` or ``'UK'`` to restrict; ``None`` for both. Order
            numbers do not collide (EU ``0994xx``-``0999xx``, UK ``0586xx``),
            so mixing regions is safe.
        regime_start: ISO date; rows before it are dropped. See ``REGIME_START``.

    Returns:
        pd.DataFrame: empty if the file does not exist.
    """
    if history_path is None:
        folder = _get_published_folder()
        if year is not None:
            history_path = os.path.join(folder, f"quota_history_{year}.csv")
        else:
            candidates = sorted(glob.glob(os.path.join(folder, "quota_history_[0-9][0-9][0-9][0-9].csv")))
            if not candidates:
                return pd.DataFrame()
            history_path = candidates[-1]

    if not os.path.exists(history_path):
        return pd.DataFrame()

    # utf-8-sig: publisher.py writes a BOM so Excel opens it cleanly.
    df = pd.read_csv(history_path, encoding="utf-8-sig", dtype={"order_number": str})
    if df.empty:
        return df

    if "scrape_status" in df.columns:
        df = df[df["scrape_status"] == "ok"]

    if region is not None and "region" in df.columns:
        df = df[df["region"].str.upper() == region.upper()]

    df = df.rename(columns=_HISTORY_COLUMN_MAP)
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"], errors="coerce")
    df = df.dropna(subset=["snapshot_date"])

    if regime_start is not None:
        df = df[df["snapshot_date"] >= pd.Timestamp(regime_start)]

    for col in ("balance", "quota_limit_t", "pct_allocated", "pct_remaining",
                "quota_allocated_t", "awaiting_allocation_t"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.reset_index(drop=True)


def load_all_snapshots(
    snapshot_folder: Optional[str] = None,
    use_cache: bool = True,
) -> pd.DataFrame:
    """
    Load all snapshot Excel files and merge into a single DataFrame.

    Globs ``snapshot_*.xlsx`` from the snapshot folder, parses the date from
    each filename, keeps only the latest file per day, and adds a
    ``snapshot_date`` column.

    Args:
        snapshot_folder: Path to folder containing snapshot files.
            Defaults to ``_get_snapshot_folder()``.
        use_cache: If True, return cached result on subsequent calls.

    Returns:
        pd.DataFrame: Combined data from all snapshots with ``snapshot_date``
        column (dtype ``datetime64[ns]``).
    """
    global _snapshot_cache

    if use_cache and _snapshot_cache is not None:
        return _snapshot_cache.copy()

    if snapshot_folder is None:
        snapshot_folder = _get_snapshot_folder()

    pattern = os.path.join(snapshot_folder, "snapshot_*.xlsx")
    files = glob.glob(pattern)

    if not files:
        return pd.DataFrame()

    # Parse filename → (date_str, timestamp_str, filepath)
    file_info = []
    fname_re = re.compile(r"snapshot_(\d{8})_(\d{6})\.xlsx$")
    for fpath in files:
        m = fname_re.search(os.path.basename(fpath))
        if m:
            date_str, time_str = m.group(1), m.group(2)
            file_info.append((date_str, time_str, fpath))

    if not file_info:
        return pd.DataFrame()

    # Keep only the latest snapshot per day
    by_date: dict[str, tuple[str, str]] = {}
    for date_str, time_str, fpath in file_info:
        if date_str not in by_date or time_str > by_date[date_str][0]:
            by_date[date_str] = (time_str, fpath)

    # Read each file and tag with snapshot_date
    frames = []
    for date_str, (_, fpath) in sorted(by_date.items()):
        try:
            df = pd.read_excel(fpath)
            df["snapshot_date"] = pd.to_datetime(date_str, format="%Y%m%d")
            frames.append(df)
        except Exception:
            # Skip corrupted / unreadable files
            continue

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)

    if use_cache:
        _snapshot_cache = combined.copy()

    return combined


def get_quota_time_series(
    all_snapshots: pd.DataFrame,
    order_number: object,
    metric: str = "balance",
) -> pd.DataFrame:
    """
    Extract a time series for one quota, formatted for Prophet.

    Args:
        all_snapshots: DataFrame returned by ``load_all_snapshots()``.
        order_number: The quota order number (int or str — converted
            automatically).
        metric: Column name to track over time (default ``"balance"``).

    Returns:
        pd.DataFrame: Two-column DataFrame ``{ds, y}`` sorted by date.
        Empty DataFrame if the order number or metric is not found.
    """
    if all_snapshots.empty:
        return pd.DataFrame(columns=["ds", "y"])

    if "order_number" not in all_snapshots.columns:
        return pd.DataFrame(columns=["ds", "y"])

    # Normalise order_number for comparison (handle int/str mismatch)
    target = str(order_number).strip().lstrip("0")
    col = all_snapshots["order_number"].astype(str).str.strip().str.lstrip("0")
    mask = col == target

    filtered = all_snapshots.loc[mask]

    if filtered.empty or metric not in filtered.columns:
        return pd.DataFrame(columns=["ds", "y"])

    ts = (
        filtered[["snapshot_date", metric]]
        .rename(columns={"snapshot_date": "ds", metric: "y"})
        .sort_values("ds")
        .reset_index(drop=True)
    )

    # Ensure numeric y values
    ts["y"] = pd.to_numeric(ts["y"], errors="coerce")
    ts = ts.dropna(subset=["y"])

    return ts


def get_all_quota_ids(all_snapshots: pd.DataFrame) -> list[dict]:
    """
    Return all unique quota identifiers across snapshots.

    Args:
        all_snapshots: DataFrame returned by ``load_all_snapshots()``.

    Returns:
        list[dict]: Each dict has keys ``order_number``, ``category``,
        ``origin``. Sorted by order_number.
    """
    if all_snapshots.empty:
        return []

    id_cols = {
        "order_number": "order_number",
        "input_quota_category": "category",
        "origin": "origin",
    }

    # Use only columns that exist
    available = {k: v for k, v in id_cols.items() if k in all_snapshots.columns}
    if not available:
        return []

    subset = all_snapshots[list(available.keys())].drop_duplicates()
    subset = subset.rename(columns=available)
    subset = subset.sort_values("order_number").reset_index(drop=True)

    return subset.to_dict("records")


def get_snapshot_summary(all_snapshots: pd.DataFrame) -> dict:
    """
    Return a summary of the loaded snapshot data.

    Args:
        all_snapshots: DataFrame returned by ``load_all_snapshots()``.

    Returns:
        dict: Keys include ``snapshot_count``, ``date_range``,
        ``quota_count``, ``prophet_ready`` (True when >= 30 days).
    """
    if all_snapshots.empty:
        return {
            "snapshot_count": 0,
            "date_range": None,
            "quota_count": 0,
            "prophet_ready": False,
        }

    dates = all_snapshots["snapshot_date"].dropna().unique()
    n_days = len(dates)

    date_min = pd.Timestamp(dates.min()).strftime("%Y-%m-%d") if n_days else None
    date_max = pd.Timestamp(dates.max()).strftime("%Y-%m-%d") if n_days else None

    quota_count = 0
    if "order_number" in all_snapshots.columns:
        quota_count = all_snapshots["order_number"].nunique()

    return {
        "snapshot_count": n_days,
        "date_range": {"start": date_min, "end": date_max} if n_days else None,
        "quota_count": quota_count,
        "prophet_ready": n_days >= MIN_PROPHET_DAYS,
    }


def prepare_prophet_df(
    ts_df: pd.DataFrame,
    cap: Optional[float] = None,
    floor: Optional[float] = None,
) -> pd.DataFrame:
    """
    Prepare a time series DataFrame for Prophet modelling.

    Adds optional ``cap`` / ``floor`` columns for logistic growth,
    removes NaN values, and ensures chronological order.

    Args:
        ts_df: DataFrame with ``ds`` and ``y`` columns (from
            ``get_quota_time_series``).
        cap: Upper saturation cap for logistic growth. If None, no cap
            column is added.
        floor: Lower floor for logistic growth. If None, no floor column
            is added.

    Returns:
        pd.DataFrame: Cleaned DataFrame ready for ``Prophet().fit()``.
    """
    if ts_df.empty:
        return ts_df.copy()

    df = ts_df[["ds", "y"]].copy()

    # Clean
    df["y"] = pd.to_numeric(df["y"], errors="coerce")
    df = df.dropna(subset=["y"])
    df = df.sort_values("ds").reset_index(drop=True)

    # Logistic growth bounds
    if cap is not None:
        df["cap"] = cap
    if floor is not None:
        df["floor"] = floor

    return df
