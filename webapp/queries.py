# -*- coding: utf-8 -*-
"""
Read queries for the tracker site.

Kept separate from the Flask layer so they can be tested without a request
context, and so a future consumer (Power BI, a notebook, an export job) can
import them directly.

Grouping and shaping happen in Python rather than SQL wherever the row count is
small — the main view is one day, 358 rows. That keeps the SQL portable between
SQLite and SQL Server instead of reaching for dialect-specific window functions
for no measurable gain.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import and_, distinct, func, select

from webapp import quota_period as qp
from webapp.db import etl_run, quota_daily
# Re-exported deliberately: callers and tests reach for `queries.displayed_pct`,
# and there must be exactly one implementation of it.
from quota_display import DISPLAY_DP, band_for, displayed_pct  # noqa: F401


def latest_snapshot_date(conn) -> Optional[date]:
    return conn.execute(select(func.max(quota_daily.c.snapshot_date))).scalar()


def freshness(conn) -> dict:
    """What the site shows as 'last update'.

    Reports the *source* scrape time, not the ETL time and certainly not the
    page-load time — those would overstate how fresh the numbers are.
    """
    row = conn.execute(
        select(etl_run).order_by(etl_run.c.id.desc()).limit(1)
    ).mappings().first()
    latest = latest_snapshot_date(conn)
    return {
        "data_date": latest,
        "source_generated_utc": row["source_generated_utc"] if row else None,
        "loaded_at_utc": row["loaded_at_utc"] if row else None,
        "period": qp.describe(latest) if latest else None,
    }


def _row_to_quota(r) -> dict:
    limit = float(r["quota_limit_t"]) if r["quota_limit_t"] is not None else None
    allocated = float(r["quota_allocated_t"]) if r["quota_allocated_t"] is not None else None
    remaining = float(r["balance_remaining_t"]) if r["balance_remaining_t"] is not None else None
    pct = float(r["pct_allocated"]) if r["pct_allocated"] is not None else None
    disp = displayed_pct(pct)
    awaiting = float(r["awaiting_allocation_t"]) if r["awaiting_allocation_t"] is not None else None
    return {
        "region": r["region"],
        "order_number": r["order_number"],
        "category": r["quota_category"] or "(uncategorised)",
        "country": r["country"] or "",
        "limit_t": limit,
        "allocated_t": allocated,
        "remaining_t": remaining,
        "pct_used": pct,
        # The same figure the page prints, computed ONCE here. The client-side
        # filter in the offline bundle compares this rather than rounding for
        # itself, so JavaScript still never owns a classification rule.
        "pct_display": disp,
        "awaiting_t": awaiting,
        "validity_start": r["validity_start"],
        "validity_end": r["validity_end"],
        "status": r["status"] or "",
        "snapshot_date": r["snapshot_date"],
        # Presentation band, computed once here so template and chart agree.
        #
        # All three boundaries classify on the value AS DISPLAYED, so the band
        # always agrees with the number printed beside it. Banding on the raw
        # figure is what put a row reading "100.0%" under a tile labelled
        # "75-99% used", and made the fastest-burning callout claim it excludes
        # exhausted quotas while naming one that showed 100.0%.
        #
        # This used to be asymmetric -- "exhausted" on the displayed figure,
        # "critical" and "high" on the raw one -- because with ROUNDED display a
        # quota at 89.96% displayed as 90.0%, and calling it critical would have
        # asserted a customs threshold the authoritative figure had not crossed.
        # Truncating removes that objection entirely: `displayed_pct(v) <= v`,
        # so a displayed 90.0 guarantees a raw >= 90. One rule, all boundaries.
        "band": band_for(pct) or "normal",
    }


def categories_overview(conn, snapshot_date: date, region: Optional[str] = None,
                        search: Optional[str] = None,
                        min_pct: Optional[float] = None,
                        pressure_only: bool = False,
                        sort: str = "pressure") -> list[dict]:
    """The main view: quotas grouped by product category.

    Categories are ordered by how pressed they are (most exhausted quotas
    first), because a list sorted alphabetically buries the thing the reader
    opened the page to find. ``sort='name'`` restores alphabetical order for
    someone who came looking for one specific category rather than for trouble.

    ``pressure_only`` and ``min_pct`` filter at different levels on purpose:
    ``min_pct`` drops individual quota *rows*, whereas ``pressure_only`` drops
    whole *categories* that have nothing under pressure — keeping every row of
    the categories it retains, so the calm quotas still provide context for the
    pressed ones beside them.
    """
    stmt = select(quota_daily).where(quota_daily.c.snapshot_date == snapshot_date)
    if region:
        stmt = stmt.where(quota_daily.c.region == region.upper())

    quotas = [_row_to_quota(r) for r in conn.execute(stmt).mappings()]

    if search:
        needle = search.strip().lower()
        quotas = [q for q in quotas
                  if needle in q["category"].lower()
                  or needle in q["country"].lower()
                  or needle in q["order_number"]]
    if min_pct is not None:
        # Compare the DISPLAYED figure, not the raw one, so the filter's answer
        # is checkable against the column the reader is looking at. `pct_display`
        # was computed once per row in `_row_to_quota`; recomputing it here would
        # be a second place for the rule to drift.
        quotas = [q for q in quotas
                  if q["pct_display"] is not None and q["pct_display"] >= min_pct]

    grouped: dict[tuple[str, str], list[dict]] = {}
    for q in quotas:
        grouped.setdefault((q["region"], q["category"]), []).append(q)

    out = []
    for (reg, category), items in grouped.items():
        # Sort on the DISPLAYED figure, then on country. Sorting on the raw
        # value while printing a rounded one produces orderings a reader cannot
        # explain: seven rows all printing "100.0%" appeared in an order driven
        # by digits nobody can see, with a 99.98% row last for no visible
        # reason. Ties now break on a column that is on the page.
        #
        # Explicit None test rather than `or -1`: 0.0 is falsy, so the old
        # idiom sorted a genuine 0.0% quota as if it were unknown.
        items.sort(key=lambda q: (
            -(q["pct_display"] if q["pct_display"] is not None else -1.0),
            q["country"]))
        exhausted = sum(1 for q in items if q["band"] == "exhausted")
        at_risk = sum(1 for q in items if q["band"] in ("critical", "high"))
        limits = [q["limit_t"] for q in items if q["limit_t"] is not None]
        allocs = [q["allocated_t"] for q in items if q["allocated_t"] is not None]
        total_limit = sum(limits) if limits else None
        total_alloc = sum(allocs) if allocs else None
        out.append({
            "region": reg,
            "category": category,
            "quotas": items,
            "count": len(items),
            "exhausted": exhausted,
            "at_risk": at_risk,
            "total_limit_t": total_limit,
            "total_allocated_t": total_alloc,
            # A displayed percentage like any other: truncate, do not round.
            # Rounding here would let a category header read 90.0% while its own
            # rows all sit below 90.
            "pct_used": (displayed_pct(100.0 * total_alloc / total_limit)
                         if total_limit else None),
        })

    if pressure_only:
        out = [c for c in out if c["exhausted"] or c["at_risk"]]

    if sort == "name":
        out.sort(key=lambda c: (c["category"].lower(), c["region"]))
    else:
        out.sort(key=lambda c: (-c["exhausted"], -c["at_risk"], c["region"], c["category"]))
    return out


def quota_detail(conn, region: str, order_number: str,
                 snapshot_date: Optional[date] = None) -> Optional[dict]:
    if snapshot_date is None:
        snapshot_date = conn.execute(
            select(func.max(quota_daily.c.snapshot_date)).where(and_(
                quota_daily.c.region == region.upper(),
                quota_daily.c.order_number == order_number))).scalar()
    if snapshot_date is None:
        return None
    row = conn.execute(select(quota_daily).where(and_(
        quota_daily.c.snapshot_date == snapshot_date,
        quota_daily.c.region == region.upper(),
        quota_daily.c.order_number == order_number))).mappings().first()
    return _row_to_quota(row) if row else None


def quota_series(conn, region: str, order_number: str,
                 quarter_start: Optional[date] = None) -> list[dict]:
    """Daily movement for one quota within one quarter.

    ``used_today_t`` is the day-over-day delta, which is what "how quickly is
    this being used" actually means — the cumulative line alone hides a quota
    that took 80% in three days.
    """
    stmt = select(quota_daily).where(and_(
        quota_daily.c.region == region.upper(),
        quota_daily.c.order_number == order_number))
    if quarter_start is not None:
        stmt = stmt.where(quota_daily.c.quarter_start == quarter_start)
    stmt = stmt.order_by(quota_daily.c.snapshot_date)

    points, prev = [], None
    for r in conn.execute(stmt).mappings():
        allocated = float(r["quota_allocated_t"]) if r["quota_allocated_t"] is not None else None
        delta = None
        if allocated is not None and prev is not None:
            delta = round(allocated - prev, 3)
        prev = allocated if allocated is not None else prev
        points.append({
            "date": r["snapshot_date"].isoformat(),
            "day_in_quarter": r["day_in_quarter"],
            "limit_t": float(r["quota_limit_t"]) if r["quota_limit_t"] is not None else None,
            "allocated_t": allocated,
            "remaining_t": float(r["balance_remaining_t"]) if r["balance_remaining_t"] is not None else None,
            "pct_used": float(r["pct_allocated"]) if r["pct_allocated"] is not None else None,
            "used_today_t": delta,
        })
    return points


def available_quarters(conn, region: Optional[str] = None,
                       order_number: Optional[str] = None) -> list[dict]:
    """Quarters that actually hold data, newest first.

    Driven by the data rather than by generating every quarter since the regime
    started, so the selector never offers an empty period.
    """
    stmt = select(distinct(quota_daily.c.quarter_start))
    if region and order_number:
        stmt = stmt.where(and_(quota_daily.c.region == region.upper(),
                               quota_daily.c.order_number == order_number))
    starts = sorted((r[0] for r in conn.execute(stmt)), reverse=True)
    out = []
    for s in starts:
        p = qp.describe(s)
        out.append({"key": p.key, "start": s, "label": f"{p.year_label} {p.quarter_label}"})
    return out


def _fastest_burning(rows: list[dict], period: qp.QuotaPeriod) -> Optional[dict]:
    """The quota consuming its allowance fastest relative to the calendar.

    Ranked by ``pct_used / pct_elapsed``, **not** by tonnes per day. Tonnes per
    day just finds the largest quota every time: a 1.5 Mt line out-consumes a
    20 kt line while sitting nowhere near its own limit, so the answer would be
    the same every day and tell nobody anything. The ratio is scale-free — 2.0
    means "using it twice as fast as the quarter is passing", whatever the size.

    Exhausted quotas are excluded. They score highest by construction, they are
    already counted in their own tile, and the useful question here is which
    quota is *about to* become a problem rather than which one already is.

    Returns None when no quota qualifies, which is the honest answer on a day
    when everything is either exhausted or missing a percentage.
    """
    elapsed = period.pct_elapsed
    if elapsed <= 0:
        return None
    best, best_ratio = None, None
    for r in rows:
        pct = r["pct_used"]
        # Reuse the band rather than re-testing the threshold, so this can never
        # drift out of step with what the tiles and the bars call exhausted.
        if pct is None or r["band"] == "exhausted":
            continue
        ratio = pct / elapsed
        if best_ratio is None or ratio > best_ratio:
            best, best_ratio = r, ratio
    if best is None:
        return None
    return dict(best, pace_ratio=round(best_ratio, 2))


def summary_counts(conn, snapshot_date: date) -> dict:
    """Headline numbers for the masthead."""
    rows = [_row_to_quota(r) for r in conn.execute(
        select(quota_daily).where(quota_daily.c.snapshot_date == snapshot_date)).mappings()]
    period = qp.describe(snapshot_date)
    # exhausted and at_risk are deliberately DISJOINT: they are displayed side
    # by side, so overlapping counts would double-count the same quota in two
    # tiles. at_risk therefore means 75-99% used, and the labels say exactly
    # that rather than "past 75%", which would also be true of an exhausted one.
    return {
        "total": len(rows),
        "eu": sum(1 for r in rows if r["region"] == "EU"),
        "uk": sum(1 for r in rows if r["region"] == "UK"),
        "exhausted": sum(1 for r in rows if r["band"] == "exhausted"),
        "at_risk": sum(1 for r in rows if r["band"] in ("critical", "high")),
        # Counted per (region, category) so this equals the number of
        # collapsible sections below it — a reader who doubts the figure can
        # count them. A bare category-name count would not match the page.
        "categories": len({(r["region"], r["category"]) for r in rows}),
        "days_remaining": period.days_remaining,
        "fastest": _fastest_burning(rows, period),
    }
