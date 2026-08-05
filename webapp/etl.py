# -*- coding: utf-8 -*-
"""
Project the published history CSV into the tracker database.

Run after the daily publish (the scheduled task does this automatically), or by
hand at any time:

    python -m webapp.etl                 # load whatever is new
    python -m webapp.etl --rebuild       # drop and reload everything
    python -m webapp.etl --dry-run       # report what would change

**Idempotent by construction.** Every date present in the CSV is deleted from
the table and re-inserted, so the database always ends up an exact mirror of
the file. Re-running it twice, or after a same-day re-scrape that revised
today's numbers, converges instead of duplicating — which matters because the
daily publish itself replaces rows per (date, region) rather than appending.

At current volume (358 rows/day, ~131k/year) a full mirror is a second's work,
so there is no incremental-update cleverness to get subtly wrong.
"""

from __future__ import annotations

import argparse
import csv
import glob
import io
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from typing import Iterable, Iterator, Optional

from sqlalchemy import delete, func, select

from webapp import quota_period as qp
from webapp.db import create_all, database_url, etl_run, get_engine, quota_daily

PUBLISHED_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "published")

# Only strictly year-named files, matching the rule src/publisher.py applies to
# the download manifest: a stray OneDrive conflict copy
# ('quota_history_2026 (1).csv') must not reach the database either.
_HISTORY_RE = re.compile(r"quota_history_(\d{4})\.csv$")


def history_files(published_dir: str = PUBLISHED_DIR) -> list[str]:
    return sorted(p for p in glob.glob(os.path.join(published_dir, "quota_history_*.csv"))
                  if _HISTORY_RE.search(os.path.basename(p)))


def _num(value) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _iso_date(value) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def read_history(paths: Iterable[str],
                 regime_start: Optional[date] = qp.REGIME_START) -> Iterator[dict]:
    """Yield database rows from the published CSVs.

    Two filters, both deliberate:

    * ``scrape_status != 'ok'`` rows are dropped. A failed scrape is a *missing*
      observation, not a zero; charting it would draw a cliff that never
      happened.
    * rows before ``regime_start`` are dropped. The pre-July-2026 safeguard was
      a different quota population, so mixing it in would make category
      groupings and cross-quarter comparisons meaningless.
    """
    for path in paths:
        with io.open(path, "r", encoding="utf-8-sig", newline="") as f:
            for raw in csv.DictReader(f):
                if (raw.get("scrape_status") or "ok") != "ok":
                    continue
                snapshot = _iso_date(raw.get("date"))
                if snapshot is None:
                    continue
                if regime_start is not None and snapshot < regime_start:
                    continue
                period = qp.describe(snapshot)
                yield {
                    "snapshot_date": snapshot,
                    "region": (raw.get("region") or "").strip().upper()[:2],
                    "order_number": (raw.get("order_number") or "").strip(),
                    "quota_category": (raw.get("quota_category") or "").strip() or None,
                    "country": (raw.get("country") or "").strip() or None,
                    "quota_limit_t": _num(raw.get("quota_limit_t")),
                    "quota_allocated_t": _num(raw.get("quota_allocated_t")),
                    "balance_remaining_t": _num(raw.get("balance_remaining_t")),
                    "pct_allocated": _num(raw.get("pct_allocated")),
                    "pct_remaining": _num(raw.get("pct_remaining")),
                    "awaiting_allocation_t": _num(raw.get("awaiting_allocation_t")),
                    "validity_start": _iso_date(raw.get("validity_start")),
                    "validity_end": _iso_date(raw.get("validity_end")),
                    "status": (raw.get("status") or "").strip() or None,
                    "quota_year": period.year_label,
                    "quota_quarter": period.quarter,
                    "quarter_start": period.start,
                    "day_in_quarter": period.day_in_quarter,
                }


def read_metadata(published_dir: str = PUBLISHED_DIR) -> dict:
    """The daily run's own freshness stamp, or {} if unreadable."""
    path = os.path.join(published_dir, "metadata.json")
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def load(engine, published_dir: str = PUBLISHED_DIR, rebuild: bool = False,
         dry_run: bool = False) -> dict:
    """Mirror the CSVs into the database. Returns a summary dict."""
    paths = history_files(published_dir)
    if not paths:
        raise RuntimeError(
            f"No quota_history_<YEAR>.csv found in {published_dir}. "
            f"Has the daily publish run?")

    rows = list(read_history(paths))
    if not rows:
        raise RuntimeError("History files contained no usable rows.")

    dates = sorted({r["snapshot_date"] for r in rows})
    summary = {
        "files": [os.path.basename(p) for p in paths],
        "rows": len(rows),
        "dates": len(dates),
        "date_min": dates[0].isoformat(),
        "date_max": dates[-1].isoformat(),
        "rebuild": rebuild,
        "dry_run": dry_run,
    }

    if dry_run:
        return summary

    create_all(engine)
    meta = read_metadata(published_dir)

    with engine.begin() as conn:
        if rebuild:
            conn.execute(delete(quota_daily))
        else:
            # Replace only the dates this load covers, so a database holding
            # older archived dates than the CSVs keeps them.
            conn.execute(delete(quota_daily).where(
                quota_daily.c.snapshot_date.in_(dates)))

        # Chunked: SQL Server caps parameters per statement, and a year of
        # history is ~131k rows.
        for i in range(0, len(rows), 500):
            conn.execute(quota_daily.insert(), rows[i:i + 500])

        conn.execute(etl_run.insert().values(
            loaded_at_utc=datetime.now(timezone.utc).replace(tzinfo=None),
            source_generated_utc=meta.get("generated_utc"),
            source_data_date=_iso_date(meta.get("data_date")),
            rows_loaded=len(rows),
            note=("rebuild" if rebuild else "incremental") + f"; {len(dates)} dates",
        ))

    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Load the published quota history into the tracker database.")
    parser.add_argument("--published-dir", default=PUBLISHED_DIR)
    parser.add_argument("--db-url", default=None,
                        help="overrides QUOTA_DB_URL for this run")
    parser.add_argument("--rebuild", action="store_true",
                        help="delete every row first, then reload")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be loaded; change nothing")
    args = parser.parse_args(argv)

    url = args.db_url or database_url()
    engine = get_engine(url)
    # Never print the URL raw: a SQL Server URL can carry a password.
    print(f"  Database: {engine.dialect.name}")

    summary = load(engine, published_dir=args.published_dir,
                   rebuild=args.rebuild, dry_run=args.dry_run)

    verb = "Would load" if args.dry_run else "Loaded"
    print(f"  {verb} {summary['rows']:,} rows across {summary['dates']} days "
          f"({summary['date_min']} -> {summary['date_max']}) "
          f"from {', '.join(summary['files'])}")
    if not args.dry_run:
        with engine.connect() as conn:
            total = conn.execute(select(func.count()).select_from(quota_daily)).scalar()
        print(f"  Table now holds {total:,} rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
