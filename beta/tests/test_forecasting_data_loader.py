# -*- coding: utf-8 -*-
"""
Tests for beta/forecasting/data_loader.py — Snapshot loading and time-series prep
"""
import pytest
import pandas as pd
import numpy as np
from datetime import datetime
import sys
import os

# Add project root to path so beta/ is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from beta.forecasting.data_loader import (
    load_all_snapshots,
    get_quota_time_series,
    get_all_quota_ids,
    get_snapshot_summary,
    prepare_prophet_df,
    _snapshot_cache,
)
import beta.forecasting.data_loader as data_loader_module


def _make_snapshot_df(order_numbers, balance_values, origin="European Union"):
    """Helper: build a minimal DataFrame matching snapshot column structure."""
    return pd.DataFrame({
        "order_number": order_numbers,
        "input_quota_category": ["Category 1A"] * len(order_numbers),
        "origin": [origin] * len(order_numbers),
        "balance": balance_values,
        "quota_limit": [1000000] * len(order_numbers),
    })


def _write_snapshot(tmp_path, date_str, time_str, df):
    """Helper: write a DataFrame as a snapshot Excel file."""
    fname = f"snapshot_{date_str}_{time_str}.xlsx"
    fpath = tmp_path / fname
    df.to_excel(fpath, index=False)
    return fpath


class TestLoadAllSnapshots:
    """Tests for load_all_snapshots function"""

    def setup_method(self):
        """Reset module-level cache before each test."""
        data_loader_module._snapshot_cache = None

    def test_loads_single_snapshot(self, tmp_path):
        df = _make_snapshot_df(["098967"], [500000])
        _write_snapshot(tmp_path, "20260124", "133032", df)

        result = load_all_snapshots(snapshot_folder=str(tmp_path), use_cache=False)
        assert len(result) == 1
        assert "snapshot_date" in result.columns

    def test_loads_multiple_snapshots(self, tmp_path):
        df1 = _make_snapshot_df(["098967"], [500000])
        df2 = _make_snapshot_df(["098967"], [490000])
        _write_snapshot(tmp_path, "20260124", "133032", df1)
        _write_snapshot(tmp_path, "20260125", "032648", df2)

        result = load_all_snapshots(snapshot_folder=str(tmp_path), use_cache=False)
        assert len(result) == 2
        dates = result["snapshot_date"].unique()
        assert len(dates) == 2

    def test_keeps_latest_per_day(self, tmp_path):
        df_early = _make_snapshot_df(["098967"], [500000])
        df_late = _make_snapshot_df(["098967"], [499000])
        _write_snapshot(tmp_path, "20260124", "100000", df_early)
        _write_snapshot(tmp_path, "20260124", "150000", df_late)

        result = load_all_snapshots(snapshot_folder=str(tmp_path), use_cache=False)
        # Only 1 row because same day → latest wins
        assert len(result) == 1
        assert result["balance"].iloc[0] == 499000

    def test_returns_empty_for_no_files(self, tmp_path):
        result = load_all_snapshots(snapshot_folder=str(tmp_path), use_cache=False)
        assert result.empty

    def test_cache_returns_copy(self, tmp_path):
        df = _make_snapshot_df(["098967"], [500000])
        _write_snapshot(tmp_path, "20260124", "133032", df)

        r1 = load_all_snapshots(snapshot_folder=str(tmp_path), use_cache=True)
        r2 = load_all_snapshots(snapshot_folder=str(tmp_path), use_cache=True)
        # Modifying r1 should not affect r2
        r1.drop(r1.index, inplace=True)
        assert len(r2) == 1

    def test_snapshot_date_is_datetime(self, tmp_path):
        df = _make_snapshot_df(["098967"], [500000])
        _write_snapshot(tmp_path, "20260124", "133032", df)

        result = load_all_snapshots(snapshot_folder=str(tmp_path), use_cache=False)
        assert pd.api.types.is_datetime64_any_dtype(result["snapshot_date"])


class TestGetQuotaTimeSeries:
    """Tests for get_quota_time_series function"""

    def _make_multi_day(self):
        """Create a 3-day snapshot DataFrame."""
        rows = []
        for i, (d, bal) in enumerate([
            ("2026-01-24", 500000),
            ("2026-01-25", 490000),
            ("2026-01-26", 480000),
        ]):
            rows.append({
                "order_number": "098967",
                "balance": bal,
                "snapshot_date": pd.Timestamp(d),
            })
        return pd.DataFrame(rows)

    def test_returns_prophet_format(self):
        data = self._make_multi_day()
        ts = get_quota_time_series(data, "098967")
        assert list(ts.columns) == ["ds", "y"]
        assert len(ts) == 3

    def test_int_order_number(self):
        data = self._make_multi_day()
        ts = get_quota_time_series(data, 98967)
        assert len(ts) == 3

    def test_str_order_number_with_leading_zeros(self):
        data = self._make_multi_day()
        ts = get_quota_time_series(data, "098967")
        assert len(ts) == 3

    def test_custom_metric(self):
        data = self._make_multi_day()
        data["quota_limit"] = 1000000
        ts = get_quota_time_series(data, "098967", metric="quota_limit")
        assert all(ts["y"] == 1000000)

    def test_missing_order_number(self):
        data = self._make_multi_day()
        ts = get_quota_time_series(data, "999999")
        assert ts.empty
        assert list(ts.columns) == ["ds", "y"]

    def test_empty_input(self):
        ts = get_quota_time_series(pd.DataFrame(), "098967")
        assert ts.empty

    def test_sorted_by_date(self):
        data = self._make_multi_day()
        # Shuffle order
        data = data.sample(frac=1, random_state=42)
        ts = get_quota_time_series(data, "098967")
        assert ts["ds"].is_monotonic_increasing


class TestGetAllQuotaIds:
    """Tests for get_all_quota_ids function"""

    def test_returns_unique_ids(self):
        data = pd.DataFrame({
            "order_number": ["098967", "098967", "098968"],
            "input_quota_category": ["Cat 1A", "Cat 1A", "Cat 2"],
            "origin": ["EU", "EU", "Turkey"],
        })
        ids = get_all_quota_ids(data)
        assert len(ids) == 2

    def test_dict_keys(self):
        data = pd.DataFrame({
            "order_number": ["098967"],
            "input_quota_category": ["Cat 1A"],
            "origin": ["EU"],
        })
        ids = get_all_quota_ids(data)
        assert "order_number" in ids[0]
        assert "category" in ids[0]
        assert "origin" in ids[0]

    def test_sorted_by_order_number(self):
        data = pd.DataFrame({
            "order_number": ["098968", "098967"],
            "input_quota_category": ["Cat 2", "Cat 1A"],
            "origin": ["EU", "EU"],
        })
        ids = get_all_quota_ids(data)
        assert ids[0]["order_number"] == "098967"

    def test_empty_input(self):
        assert get_all_quota_ids(pd.DataFrame()) == []


class TestGetSnapshotSummary:
    """Tests for get_snapshot_summary function"""

    def test_basic_summary(self):
        data = pd.DataFrame({
            "order_number": ["098967", "098968"],
            "snapshot_date": [pd.Timestamp("2026-01-24")] * 2,
        })
        summary = get_snapshot_summary(data)
        assert summary["snapshot_count"] == 1
        assert summary["quota_count"] == 2
        assert summary["prophet_ready"] is False

    def test_prophet_ready_threshold(self):
        dates = pd.date_range("2026-01-01", periods=30, freq="D")
        data = pd.DataFrame({
            "order_number": ["098967"] * 30,
            "snapshot_date": dates,
        })
        summary = get_snapshot_summary(data)
        assert summary["prophet_ready"] is True

    def test_not_prophet_ready(self):
        dates = pd.date_range("2026-01-01", periods=29, freq="D")
        data = pd.DataFrame({
            "order_number": ["098967"] * 29,
            "snapshot_date": dates,
        })
        summary = get_snapshot_summary(data)
        assert summary["prophet_ready"] is False

    def test_date_range(self):
        data = pd.DataFrame({
            "order_number": ["098967", "098967"],
            "snapshot_date": [pd.Timestamp("2026-01-24"), pd.Timestamp("2026-02-18")],
        })
        summary = get_snapshot_summary(data)
        assert summary["date_range"]["start"] == "2026-01-24"
        assert summary["date_range"]["end"] == "2026-02-18"

    def test_empty_input(self):
        summary = get_snapshot_summary(pd.DataFrame())
        assert summary["snapshot_count"] == 0
        assert summary["prophet_ready"] is False
        assert summary["date_range"] is None


class TestPrepareProphetDf:
    """Tests for prepare_prophet_df function"""

    def _make_ts(self):
        return pd.DataFrame({
            "ds": pd.date_range("2026-01-01", periods=5, freq="D"),
            "y": [100, 200, 300, 400, 500],
        })

    def test_basic_passthrough(self):
        ts = self._make_ts()
        result = prepare_prophet_df(ts)
        assert list(result.columns) == ["ds", "y"]
        assert len(result) == 5

    def test_adds_cap(self):
        ts = self._make_ts()
        result = prepare_prophet_df(ts, cap=1000)
        assert "cap" in result.columns
        assert all(result["cap"] == 1000)

    def test_adds_floor(self):
        ts = self._make_ts()
        result = prepare_prophet_df(ts, floor=0)
        assert "floor" in result.columns
        assert all(result["floor"] == 0)

    def test_adds_cap_and_floor(self):
        ts = self._make_ts()
        result = prepare_prophet_df(ts, cap=1000, floor=0)
        assert "cap" in result.columns
        assert "floor" in result.columns

    def test_removes_nan(self):
        ts = self._make_ts()
        ts.loc[2, "y"] = np.nan
        result = prepare_prophet_df(ts)
        assert len(result) == 4
        assert not result["y"].isna().any()

    def test_sorts_by_date(self):
        ts = self._make_ts().sample(frac=1, random_state=42)
        result = prepare_prophet_df(ts)
        assert result["ds"].is_monotonic_increasing

    def test_empty_input(self):
        result = prepare_prophet_df(pd.DataFrame(columns=["ds", "y"]))
        assert result.empty

    def test_coerces_string_y(self):
        ts = pd.DataFrame({
            "ds": pd.date_range("2026-01-01", periods=3, freq="D"),
            "y": ["100", "200", "300"],
        })
        result = prepare_prophet_df(ts)
        assert result["y"].dtype in [np.float64, np.int64]
