# -*- coding: utf-8 -*-
"""
Tests for load_history() — the published daily history as the forecasting
source, replacing the snapshot workbooks that nothing produces any more.
"""
import io
import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from beta.forecasting import data_loader as dl


HEADER = ("date,region,order_number,quota_category,country,quota_limit_t,"
          "quota_allocated_t,pct_allocated,balance_remaining_t,pct_remaining,"
          "awaiting_allocation_t,validity_start,validity_end,status,scrape_status\n")


def _row(date, region="EU", order="099491", bal="100.5", status="ok", pct="42.0"):
    return (f"{date},{region},{order},Cat 1 Hot-rolled,Turkiye,1000.0,"
            f"500.0,{pct},{bal},58.0,10.0,2026-07-01,2026-09-30,,{status}\n")


@pytest.fixture
def history(tmp_path):
    """A small history file shaped exactly like the real one (BOM included)."""
    p = tmp_path / "quota_history_2026.csv"
    body = HEADER
    for d in ("2026-07-06", "2026-07-07", "2026-07-08"):
        body += _row(d, "EU", "099491", bal="100.5")
        body += _row(d, "UK", "058600", bal="200.0")
    with io.open(p, "w", encoding="utf-8-sig", newline="") as f:
        f.write(body)
    return str(p)


class TestLoadHistory:

    def test_reads_the_bom_encoded_file(self, history):
        df = dl.load_history(history_path=history)
        assert not df.empty
        # A mis-read BOM shows up as a mangled first column name.
        assert "snapshot_date" in df.columns
        assert len(df) == 6

    def test_maps_columns_onto_the_existing_shape(self, history):
        df = dl.load_history(history_path=history)
        for col in ("snapshot_date", "order_number", "balance",
                    "input_quota_category", "origin"):
            assert col in df.columns, f"{col} missing — downstream funcs rely on it"
        assert pd.api.types.is_datetime64_any_dtype(df["snapshot_date"])

    def test_keeps_leading_zeros_on_order_numbers(self, history):
        df = dl.load_history(history_path=history)
        assert "099491" in set(df["order_number"])
        assert "058600" in set(df["order_number"])

    def test_filters_by_region(self, history):
        assert len(dl.load_history(history_path=history, region="UK")) == 3
        assert len(dl.load_history(history_path=history, region="eu")) == 3

    def test_missing_file_returns_empty_not_an_error(self, tmp_path):
        assert dl.load_history(history_path=str(tmp_path / "nope.csv")).empty


class TestDataQualityGuards:

    def test_drops_failed_scrapes(self, tmp_path):
        # A failed scrape is a MISSING observation, not a zero. Feeding it to a
        # model would invent a cliff that never happened.
        p = tmp_path / "quota_history_2026.csv"
        body = HEADER + _row("2026-07-06") + _row("2026-07-07", status="error", bal="")
        io.open(p, "w", encoding="utf-8-sig", newline="").write(body)
        df = dl.load_history(history_path=str(p))
        assert len(df) == 1
        assert df["snapshot_date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-07-06"]

    def test_excludes_rows_before_the_regime_boundary_by_default(self, tmp_path):
        # Pre- and post-1-July-2026 rows are different quota populations.
        p = tmp_path / "quota_history_2026.csv"
        body = HEADER + _row("2026-06-28") + _row("2026-07-06")
        io.open(p, "w", encoding="utf-8-sig", newline="").write(body)
        df = dl.load_history(history_path=str(p))
        assert len(df) == 1
        assert df.iloc[0]["snapshot_date"] == pd.Timestamp("2026-07-06")

    def test_regime_boundary_can_be_disabled_explicitly(self, tmp_path):
        p = tmp_path / "quota_history_2026.csv"
        body = HEADER + _row("2026-06-28") + _row("2026-07-06")
        io.open(p, "w", encoding="utf-8-sig", newline="").write(body)
        assert len(dl.load_history(history_path=str(p), regime_start=None)) == 2

    def test_regime_start_matches_the_documented_boundary(self):
        assert dl.REGIME_START == "2026-07-01"


class TestInteropWithExistingFunctions:
    """The whole point of the column mapping: nothing downstream changes."""

    def test_get_quota_time_series_works_unchanged(self, history):
        df = dl.load_history(history_path=history)
        ts = dl.get_quota_time_series(df, order_number="099491")
        assert list(ts.columns) == ["ds", "y"]
        assert len(ts) == 3
        assert ts["y"].iloc[0] == 100.5
        assert ts["ds"].is_monotonic_increasing

    def test_eu_and_uk_order_numbers_do_not_collide(self, history):
        df = dl.load_history(history_path=history)
        assert dl.get_quota_time_series(df, "099491")["y"].iloc[0] == 100.5
        assert dl.get_quota_time_series(df, "058600")["y"].iloc[0] == 200.0

    def test_get_snapshot_summary_works_unchanged(self, history):
        summary = dl.get_snapshot_summary(dl.load_history(history_path=history))
        assert summary["snapshot_count"] == 3
        assert summary["quota_count"] == 2
        assert summary["prophet_ready"] is False   # 3 days, threshold is 30

    def test_get_all_quota_ids_works_unchanged(self, history):
        ids = dl.get_all_quota_ids(dl.load_history(history_path=history))
        assert len(ids) == 2
        assert {"order_number", "category", "origin"} <= set(ids[0])

    def test_prepare_prophet_df_works_unchanged(self, history):
        df = dl.load_history(history_path=history)
        ts = dl.get_quota_time_series(df, "099491")
        out = dl.prepare_prophet_df(ts, cap=1000.0, floor=0.0)
        assert {"ds", "y", "cap", "floor"} <= set(out.columns)


class TestAgainstTheRealFile:
    """Skipped in a fresh clone that has not pulled published data."""

    def _real(self):
        return os.path.join(dl._get_published_folder(), "quota_history_2026.csv")

    def test_loads_the_committed_history(self):
        if not os.path.exists(self._real()):
            pytest.skip("no published history in this checkout")
        df = dl.load_history()
        assert not df.empty
        summary = dl.get_snapshot_summary(df)
        assert summary["quota_count"] > 300, "expected 283 EU + 75 UK quotas"
        assert summary["snapshot_count"] >= 1
        # Every retained row must be inside the current regime.
        assert df["snapshot_date"].min() >= pd.Timestamp(dl.REGIME_START)
