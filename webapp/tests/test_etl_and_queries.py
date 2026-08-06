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

    def test_a_quota_that_displays_as_100_is_banded_exhausted(self, tmp_path):
        """Regression: bands must agree with the number printed beside them.

        Real data, 2026-08-05: order 058627 sat at 99.99% (2.15 t left of
        17,093). The site prints percentages to one decimal, so the row read
        "100.0%" while being banded critical — putting it under a tile labelled
        "75-99% used", and making the fastest-burning callout name a quota
        showing 100.0% in the same sentence as "exhausted quotas are excluded".
        """
        published = write_history(tmp_path, "".join([
            row("2026-08-02", "EU", "099491", pct="99.99", limit="17093",
                alloc="17090.85", bal="2.15"),
            row("2026-08-02", "EU", "099492", pct="99.94"),   # still prints 99.9
        ]))
        engine = get_engine(f"sqlite:///{tmp_path/'b.db'}")
        etl.load(engine, published_dir=published)
        with engine.connect() as c:
            assert queries.quota_detail(c, "EU", "099491")["band"] == "exhausted"
            assert queries.quota_detail(c, "EU", "099492")["band"] == "critical"
            assert queries.summary_counts(c, LATEST)["fastest"]["order_number"] == "099492"

    def test_summary_counts_keeps_exhausted_and_at_risk_disjoint(self, loaded):
        # The two are shown side by side, so a quota must appear in exactly one.
        # 30% -> normal, 150% -> exhausted, neither is 75-99%.
        engine, _ = loaded
        with engine.connect() as c:
            s = queries.summary_counts(c, date(2026, 7, 8))
        assert (s["total"], s["eu"], s["uk"]) == (2, 1, 1)
        assert (s["exhausted"], s["at_risk"]) == (1, 0)
        # The property the name promises, stated directly: no quota is counted
        # in both tiles. Previously this rested on a whole-dict equality, which
        # made the test fail for any added key regardless of disjointness.
        assert s["exhausted"] + s["at_risk"] <= s["total"]

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


@pytest.fixture
def sized(tmp_path):
    """One enormous quota barely touched, one small quota nearly full.

    Built specifically to separate the two candidate definitions of "burning
    fastest". By tonnes per day the huge quota wins by a factor of sixteen; by
    share of its own allowance the small one is the one about to close. Only
    the second answer is useful, so the fixture makes the two disagree.
    """
    body = ""
    for i, d in enumerate(("2026-07-06", "2026-08-02")):
        body += row(d, "EU", "099001", cat="Hot Rolled - 1", country="India",
                    limit="1500000", alloc=str(150000 * (i + 1)),
                    pct=str(10.0 * (i + 1)), bal=str(1500000 - 150000 * (i + 1)))
        body += row(d, "EU", "099002", cat="Rebar - 13", country="Egypt",
                    limit="20000", alloc=str(9000 * (i + 1)),
                    pct=str(45.0 * (i + 1)), bal=str(20000 - 9000 * (i + 1)))
        body += row(d, "UK", "058999", cat="Rebar - 13", country="Other countries",
                    limit="5000", alloc="6000", pct="120.0", bal="0")
    published = write_history(tmp_path, body)
    engine = get_engine(f"sqlite:///{tmp_path/'s.db'}")
    etl.load(engine, published_dir=published)
    return engine


LATEST = date(2026, 8, 2)          # day 33 of 92, so 35.9% of Q1 elapsed


class TestFastestBurning:

    def test_ranks_by_share_of_allowance_not_by_tonnage(self, sized):
        with sized.connect() as c:
            s = queries.summary_counts(c, LATEST)
            series = {o: queries.quota_series(c, "EU", o) for o in ("099001", "099002")}
        # The tonnage answer and the share answer genuinely disagree here...
        assert series["099001"][-1]["used_today_t"] > series["099002"][-1]["used_today_t"]
        # ...and we report the share answer.
        assert s["fastest"]["order_number"] == "099002"

    def test_reports_the_pace_ratio(self, sized):
        with sized.connect() as c:
            s = queries.summary_counts(c, LATEST)
        # 90.0% used / 35.9% elapsed
        assert s["fastest"]["pace_ratio"] == 2.51
        assert s["fastest"]["pct_used"] == 90.0

    def test_excludes_exhausted_quotas(self, sized):
        """They score highest by construction and have their own tile.

        The question this answers is which quota is *about to* close, not which
        one already has.
        """
        with sized.connect() as c:
            s = queries.summary_counts(c, LATEST)
        assert s["fastest"]["order_number"] != "058999"
        assert s["fastest"]["pct_used"] < 100

    def test_returns_none_when_every_quota_is_exhausted(self, tmp_path):
        body = row("2026-08-02", "EU", "099003", limit="100", alloc="120",
                   pct="120.0", bal="0")
        published = write_history(tmp_path, body)
        engine = get_engine(f"sqlite:///{tmp_path/'x.db'}")
        etl.load(engine, published_dir=published)
        with engine.connect() as c:
            assert queries.summary_counts(c, LATEST)["fastest"] is None


class TestSummaryExtras:

    def test_counts_categories_per_region(self, sized):
        """Rebar - 13 exists under both EU and UK and counts twice.

        That matches the number of collapsible sections on the page, which is
        what a reader who doubts the figure would count.
        """
        with sized.connect() as c:
            s = queries.summary_counts(c, LATEST)
        assert s["categories"] == 3
        assert s["total"] == 3

    def test_days_remaining_matches_the_snapshot_date(self, sized):
        with sized.connect() as c:
            s = queries.summary_counts(c, LATEST)
        assert s["days_remaining"] == 59


class TestOverviewFilteringAndSort:

    def test_pressure_only_drops_calm_categories_whole(self, sized):
        with sized.connect() as c:
            all_groups = queries.categories_overview(c, LATEST)
            pressed = queries.categories_overview(c, LATEST, pressure_only=True)
        assert len(all_groups) == 3
        assert {g["category"] for g in pressed} == {"Rebar - 13"}

    def test_pressure_only_keeps_every_row_of_a_kept_category(self, sized):
        """Unlike min_pct, which filters rows — the calm quotas inside a pressed
        category are the context that makes the pressed one legible."""
        with sized.connect() as c:
            pressed = queries.categories_overview(c, LATEST, pressure_only=True)
            rows = queries.categories_overview(c, LATEST, min_pct=100)
        assert sum(g["count"] for g in pressed) == 2
        assert sum(g["count"] for g in rows) == 1

    def test_sort_by_name_is_alphabetical(self, sized):
        with sized.connect() as c:
            named = queries.categories_overview(c, LATEST, sort="name")
        assert [g["category"] for g in named] == [
            "Hot Rolled - 1", "Rebar - 13", "Rebar - 13"]

    def test_default_sort_puts_the_exhausted_category_first(self, sized):
        with sized.connect() as c:
            default = queries.categories_overview(c, LATEST)
        assert default[0]["region"] == "UK" and default[0]["exhausted"] == 1
        assert default[-1]["category"] == "Hot Rolled - 1"

    def test_unknown_sort_value_falls_back_to_the_default(self, sized):
        with sized.connect() as c:
            junk = queries.categories_overview(c, LATEST, sort="nonsense")
            default = queries.categories_overview(c, LATEST)
        assert [g["category"] for g in junk] == [g["category"] for g in default]
