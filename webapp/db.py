# -*- coding: utf-8 -*-
"""
Database schema for the internal quota tracker.

**The database is a derived read model, not the system of record.**
`data/published/quota_history_<YEAR>.csv` remains canonical: it is what the
daily run writes, what git versions, and what colleagues download. This
database is a projection of it, rebuilt with `python -m webapp.etl --rebuild`
at any time.

Two consequences worth stating, because they are the reason for the design:

1. A database outage, a permissions change, or a schema migration **cannot
   break the daily publish**. The scraper does not import this module and the
   daily task treats the ETL step as non-fatal.
2. Anything wrong in here is fixable by re-running the ETL. There is no state
   in this database that exists nowhere else.

Portability: SQLAlchemy Core, with column types chosen to mean the same thing
on SQLite (development, and a perfectly adequate production fallback) and on
SQL Server (the target, and what MEPS already runs behind Power BI). Switching
is the `QUOTA_DB_URL` environment variable; no code changes.

    sqlite:///C:/DataScienceProject/EUQuota/data/quota_tracker.db
    mssql+pyodbc://@localhost/MEPSQuota?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes
"""

from __future__ import annotations

import os

from sqlalchemy import (
    Column, Date, DateTime, Index, Integer, MetaData, Numeric,
    SmallInteger, String, Table, Unicode, create_engine,
)

DEFAULT_SQLITE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "quota_tracker.db")

metadata = MetaData()

# One row per quota per day. The natural key is (date, region, order number):
# order numbers are unique within a region and a quota is reported once a day.
#
# Region is part of the key rather than trusted to be implied by the order
# number range. EU numbers are 0994xx-0999xx and UK are 0586xx today, but that
# is a fact about the current regulations, not a guarantee, and the January
# 2027 renewal may reallocate ranges.
quota_daily = Table(
    "quota_daily", metadata,
    Column("snapshot_date", Date, primary_key=True, nullable=False),
    Column("region", String(2), primary_key=True, nullable=False),
    Column("order_number", String(6), primary_key=True, nullable=False),

    Column("quota_category", Unicode(200)),
    # "country or residual allocation" -- this column carries both. Residual
    # rows read like 'Other countries' or 'FTA Quota - Other'.
    Column("country", Unicode(200)),

    # Volumes in tonnes, exactly as published. The quota limit is taken from
    # the source and NEVER recomputed here: any rollover between periods is
    # already reflected upstream by TARIC / the UK tariff, and re-deriving it
    # would risk disagreeing with the authoritative figure.
    Column("quota_limit_t", Numeric(18, 3)),
    Column("quota_allocated_t", Numeric(18, 3)),
    Column("balance_remaining_t", Numeric(18, 3)),
    Column("pct_allocated", Numeric(9, 4)),
    Column("pct_remaining", Numeric(9, 4)),
    # EU only: requests pooled but not yet allocated. Decides whether a quota
    # is really open early in a quarter, so it is shown rather than hidden.
    Column("awaiting_allocation_t", Numeric(18, 3)),

    Column("validity_start", Date),
    Column("validity_end", Date),
    Column("status", Unicode(50)),

    # Quota-year framing (Jul-Jun), denormalised deliberately. These are pure
    # functions of snapshot_date, but storing them means the reporting queries
    # are plain WHERE clauses instead of date arithmetic that has to be
    # reimplemented identically in SQLite and T-SQL.
    Column("quota_year", String(9), nullable=False),
    Column("quota_quarter", SmallInteger, nullable=False),
    Column("quarter_start", Date, nullable=False),
    # The axis for "compare the same point in different quarters".
    Column("day_in_quarter", Integer, nullable=False),
)

# Drill-down: one quota's series within a quarter.
Index("ix_quota_daily_series", quota_daily.c.region, quota_daily.c.order_number,
      quota_daily.c.snapshot_date)
# Main view: everything on the latest day, grouped by category.
Index("ix_quota_daily_day", quota_daily.c.snapshot_date, quota_daily.c.quota_category)
# Cross-quarter comparison at a fixed offset.
Index("ix_quota_daily_offset", quota_daily.c.quota_year, quota_daily.c.quota_quarter,
      quota_daily.c.day_in_quarter)


# Provenance, so the site can answer "how fresh is this?" honestly rather than
# implying the page-load time is the data time.
etl_run = Table(
    "etl_run", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("loaded_at_utc", DateTime, nullable=False),
    # Straight from metadata.json: when the scrape that produced this data ran.
    Column("source_generated_utc", String(32)),
    Column("source_data_date", Date),
    Column("rows_loaded", Integer),
    Column("note", Unicode(400)),
)


def database_url() -> str:
    """Connection URL: ``QUOTA_DB_URL`` if set, else a local SQLite file."""
    return os.environ.get("QUOTA_DB_URL") or f"sqlite:///{DEFAULT_SQLITE_PATH}"


def get_engine(url: str | None = None, echo: bool = False):
    """Create an engine. ``future=True`` keeps 1.x and 2.x behaviour identical."""
    url = url or database_url()
    kwargs = {"echo": echo, "future": True}
    if url.startswith("sqlite"):
        # The web app reads from request threads; the ETL writes from one.
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def create_all(engine) -> None:
    """Create tables if absent. Safe to call on every start."""
    metadata.create_all(engine)


def is_sqlite(engine) -> bool:
    return engine.dialect.name == "sqlite"
