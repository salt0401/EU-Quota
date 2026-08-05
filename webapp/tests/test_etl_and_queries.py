# -*- coding: utf-8 -*-
"""
Tests for the ETL projection and the read queries.

Everything runs against an in-memory/temporary SQLite database built from a
synthetic CSV shaped exactly like the real published history, so these tests
need no network, no server and no committed data.
"""
import io
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

sqlalchemy = pytest.importorskip("sqlalchemy",
                                 reason="webapp extras not installed (requirements-webapp.txt)")

from sqlalchemy import func, select                    # noqa: E402

from webapp import etl, queries                        # noqa: E402
from webapp.db import etl_run, get_engine, quota_daily  # noqa: E402

HEADER = ("date,region,order_number,quota_category,country,quota_limit_t,"
          "quota_allocated_t,pct_allocated,balance_remaining_t,pct_remaining,"
          "awaiting_allocation_t,validity_start,validity_end,status,scrape_status\n")


def row(d, region="EU", order="099491", cat="Quarto Plates - 7", country="Turkiye",
        limit="1000", alloc="250", pct="25.0", bal="750", pct_rem="75.0",
        await_t="10", status="", scrape="ok"):
    return (f"{d},{region},{order},{cat},{country},{limit},{alloc},{pct},{bal},"
            f"{pct_rem},{await_t},2026-07-01,2026-09-30,{status},{scrape}\n")


def write_history(tmp_path, body, metadata=True):
    d = tmp_path / "published"
    d.mkdir(exist_ok=True)
    with io.open(d / "quota_history_2026.csv", "w", encoding="utf-8-sig", newline="") as f:
        f.write(HEADER + body)
    if metadata:
        io.open(d / "metadata.json", "w", encoding="utf-8").write(
            '{"generated_utc":"2026-08-02T05:43:08Z","data_date":"2026-08-02"}')
    return str(d)


@pytest.fixture
def loaded(tmp_path):
    """Three days of two quotas, plus one bad row and one pre-regime row."""
    body = ""
    for i, d in enumerate(("2026-07-06", "2026-07-07", "2026-07-08")):
        body += row(d, "EU", "099491", alloc=str(100 * (i + 1)),
                    pct=str(10.0 * (i + 1)), bal=str(1000 - 100 * (i + 1)))
        body += row(d, "UK", "058600", cat="Rebar - 13", country="Other countries",
                    alloc=str(500 * (i + 1)), pct=str(50.0 * (i + 1)),
                    bal=str(1000 - 500 * (i + 1)))
    body += row("2026-07-09", "EU", "099492", scrape="error")      # dropped
    body += row("2026-06-28", "EU", "099491")                      # pre-regime, dropped
    published = write_history(tmp_path, body)
    engine = get_engine(f"sqlite:///{tmp_path/'t.db'}")
    etl.load(engine, published_dir=published)
    return engine, published


class TestEtlFiltering:

    def test_drops_failed_scrapes(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            assert c.execute(select(func.count()).select_from(quota_daily).where(
                quota_daily.c.order_number == "099492")).scalar() == 0

    def test_drops_rows_before_the_regime_boundary(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            earliest = c.execute(select(func.min(quota_daily.c.snapshot_date))).scalar()
        assert earliest == date(2026, 7, 6)

    def test_loads_the_good_rows(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            assert c.execute(select(func.count()).select_from(quota_daily)).scalar() == 6

    def test_ignores_onedrive_conflict_copies(self, tmp_path):
        published = write_history(tmp_path, row("2026-07-06"))
        open(os.path.join(published, "quota_history_2026 (1).csv"), "w").close()
        assert len(etl.history_files(published)) == 1

    def test_refuses_when_no_history_exists(self, tmp_path):
        empty = tmp_path / "nothing"
        empty.mkdir()
        with pytest.raises(RuntimeError, match="No quota_history"):
            etl.load(get_engine("sqlite://"), published_dir=str(empty))


class TestEtlIdempotency:
    """A re-run must converge, not duplicate -- the daily publish itself
    replaces rows per (date, region), so the ETL must mirror that."""

    def test_reloading_does_not_duplicate(self, loaded):
        engine, published = loaded
        etl.load(engine, published_dir=published)
        etl.load(engine, published_dir=published)
        with engine.connect() as c:
            assert c.execute(select(func.count()).select_from(quota_daily)).scalar() == 6

    def test_revised_figures_replace_rather_than_append(self, tmp_path):
        published = write_history(tmp_path, row("2026-07-06", alloc="100", pct="10.0"))
        engine = get_engine(f"sqlite:///{tmp_path/'t.db'}")
        etl.load(engine, published_dir=published)
        # Same day re-scraped with revised numbers, as a same-day re-run does.
        write_history(tmp_path, row("2026-07-06", alloc="880", pct="88.0"))
        etl.load(engine, published_dir=published)
        with engine.connect() as c:
            rows = c.execute(select(quota_daily)).mappings().all()
        assert len(rows) == 1
        assert float(rows[0]["pct_allocated"]) == 88.0

    def test_rebuild_clears_first(self, loaded):
        engine, published = loaded
        etl.load(engine, published_dir=published, rebuild=True)
        with engine.connect() as c:
            assert c.execute(select(func.count()).select_from(quota_daily)).scalar() == 6

    def test_dry_run_changes_nothing(self, tmp_path):
        published = write_history(tmp_path, row("2026-07-06"))
        engine = get_engine(f"sqlite:///{tmp_path/'t.db'}")
        summary = etl.load(engine, published_dir=published, dry_run=True)
        assert summary["dry_run"] and summary["rows"] == 1
        from webapp.db import create_all
        create_all(engine)
        with engine.connect() as c:
            assert c.execute(select(func.count()).select_from(quota_daily)).scalar() == 0


class TestEtlDerivedColumns:

    def test_stamps_quota_year_and_quarter(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            r = c.execute(select(quota_daily).where(
                quota_daily.c.snapshot_date == date(2026, 7, 8))).mappings().first()
        assert r["quota_year"] == "2026/27"
        assert r["quota_quarter"] == 1              # Jul-Sep is Q1, not calendar Q3
        assert r["quarter_start"] == date(2026, 7, 1)
        assert r["day_in_quarter"] == 8

    def test_records_provenance(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            r = c.execute(select(etl_run).order_by(etl_run.c.id.desc())).mappings().first()
        assert r["source_generated_utc"] == "2026-08-02T05:43:08Z"
        assert r["rows_loaded"] == 6


class TestQueries:

    def test_latest_snapshot_date(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            assert queries.latest_snapshot_date(c) == date(2026, 7, 8)

    def test_overview_groups_by_category(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            groups = queries.categories_overview(c, date(2026, 7, 8))
        assert {g["category"] for g in groups} == {"Quarto Plates - 7", "Rebar - 13"}
        assert all(g["count"] == 1 for g in groups)

    def test_overview_orders_most_pressed_category_first(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            groups = queries.categories_overview(c, date(2026, 7, 8))
        # UK rebar is at 150% (exhausted); EU plates at 30%.
        assert groups[0]["category"] == "Rebar - 13"

    def test_region_filter(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            assert all(g["region"] == "UK"
                       for g in queries.categories_overview(c, date(2026, 7, 8), region="UK"))

    def test_search_matches_country_category_and_order_number(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            for needle in ("turkiye", "quarto", "099491"):
                got = queries.categories_overview(c, date(2026, 7, 8), search=needle)
                assert len(got) == 1 and got[0]["category"] == "Quarto Plates - 7", needle

    def test_min_pct_filter(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            got = queries.categories_overview(c, date(2026, 7, 8), min_pct=100)
        assert len(got) == 1 and got[0]["category"] == "Rebar - 13"

    def test_bands_match_the_thresholds(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            eu = queries.quota_detail(c, "EU", "099491")
            uk = queries.quota_detail(c, "UK", "058600")
        assert eu["band"] == "normal"        # 30%
        assert uk["band"] == "exhausted"     # 150%

    def test_summary_counts_keeps_exhausted_and_at_risk_disjoint(self, loaded):
        # The two are shown side by side, so a quota must appear in exactly one.
        # 30% -> normal, 150% -> exhausted, neither is 75-99%.
        engine, _ = loaded
        with engine.connect() as c:
            s = queries.summary_counts(c, date(2026, 7, 8))
        assert s == {"total": 2, "eu": 1, "uk": 1, "exhausted": 1, "at_risk": 0}

    def test_at_risk_counts_the_75_to_99_band(self, tmp_path):
        published = write_history(tmp_path, "".join([
            row("2026-07-06", "EU", "099491", pct="80.0"),     # high
            row("2026-07-06", "EU", "099492", pct="95.0"),     # critical
            row("2026-07-06", "EU", "099493", pct="100.0"),    # exhausted
            row("2026-07-06", "EU", "099494", pct="10.0"),     # normal
        ]))
        engine = get_engine(f"sqlite:///{tmp_path/'r.db'}")
        etl.load(engine, published_dir=published)
        with engine.connect() as c:
            s = queries.summary_counts(c, date(2026, 7, 6))
        assert s["at_risk"] == 2 and s["exhausted"] == 1 and s["total"] == 4


class TestQuotaSeries:

    def test_returns_the_full_quarter_series_in_order(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            pts = queries.quota_series(c, "EU", "099491")
        assert [p["date"] for p in pts] == ["2026-07-06", "2026-07-07", "2026-07-08"]
        assert [p["day_in_quarter"] for p in pts] == [6, 7, 8]

    def test_daily_delta_is_day_over_day_not_cumulative(self, loaded):
        # "How quickly is it being used" is the delta; the cumulative line
        # alone hides a quota that took 80% in three days.
        engine, _ = loaded
        with engine.connect() as c:
            pts = queries.quota_series(c, "EU", "099491")
        assert pts[0]["used_today_t"] is None      # nothing to diff against
        assert pts[1]["used_today_t"] == 100.0
        assert pts[2]["used_today_t"] == 100.0

    def test_unknown_quota_returns_empty(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            assert queries.quota_series(c, "EU", "000000") == []
            assert queries.quota_detail(c, "EU", "000000") is None

    def test_available_quarters_are_data_driven(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            qs = queries.available_quarters(c)
        assert [q["key"] for q in qs] == ["2026/27-Q1"]
        assert qs[0]["label"] == "2026/27 Q1 (Jul-Sep)"


class TestFreshness:

    def test_reports_the_source_scrape_time_not_the_load_time(self, loaded):
        engine, _ = loaded
        with engine.connect() as c:
            f = queries.freshness(c)
        assert f["source_generated_utc"] == "2026-08-02T05:43:08Z"
        assert f["data_date"] == date(2026, 7, 8)
        assert f["period"].key == "2026/27-Q1"
