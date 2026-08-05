# -*- coding: utf-8 -*-
"""
Quota-year and quota-quarter arithmetic.

**The quota year runs 1 July to 30 June**, not January to December, and it is
split into four quarters:

    Q1  Jul - Sep        Q3  Jan - Mar
    Q2  Oct - Dec        Q4  Apr - Jun

This is deliberately NOT the same as the calendar quarters in ``src/config.py``.
Those exist to build the ``StartDate`` parameter TARIC expects, which is a
calendar quarter start; these exist to label and group data the way the business
reads it. Both are correct for their own job, and conflating them is the obvious
way to get this wrong — so they live in different modules and neither imports
the other.

The value that makes the reporting requirement possible is ``day_in_quarter``:
with it, "how used was this quota 34 days into the quarter?" is answerable
across different quarters, which raw dates cannot do because quarters have
different lengths and start on different weekdays.

Pure standard library — no dependencies, so it is cheap to test and cannot
break the scraper.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterator, Optional

# The month the quota year opens.
QUOTA_YEAR_START_MONTH = 7

# Quarter number -> the calendar month that quarter starts in.
_QUARTER_START_MONTH = {1: 7, 2: 10, 3: 1, 4: 4}

QUARTER_LABELS = {1: "Q1 (Jul-Sep)", 2: "Q2 (Oct-Dec)",
                  3: "Q3 (Jan-Mar)", 4: "Q4 (Apr-Jun)"}

# The regimes this tracker covers began on this date. Nothing before it is
# comparable: the previous EU safeguard had 189 quotas with different order
# numbers and volumes.
REGIME_START = date(2026, 7, 1)


def quota_quarter(d: date) -> int:
    """Quarter number 1-4 within the quota year (Jul-Sep is 1)."""
    return ((d.month - QUOTA_YEAR_START_MONTH) % 12) // 3 + 1


def quota_year_start(d: date) -> int:
    """The calendar year in which this date's quota year opened.

    A date in Jan-Jun belongs to the quota year that opened the *previous* July.
    """
    return d.year if d.month >= QUOTA_YEAR_START_MONTH else d.year - 1


def quota_year_label(d: date) -> str:
    """Human label for the quota year, e.g. ``'2026/27'``."""
    start = quota_year_start(d)
    return f"{start}/{(start + 1) % 100:02d}"


def quarter_start(d: date) -> date:
    """First day of the quota quarter containing ``d``.

    The quarter's start month always falls in the same calendar year as any
    date inside it, which is why no year adjustment is needed here even though
    the quota *year* does need one.
    """
    return date(d.year, _QUARTER_START_MONTH[quota_quarter(d)], 1)


def quarter_end(d: date) -> date:
    """Last day of the quota quarter containing ``d`` (inclusive)."""
    start = quarter_start(d)
    if start.month == 10:
        return date(start.year, 12, 31)
    return date(start.year, start.month + 3, 1) - timedelta(days=1)


def day_in_quarter(d: date) -> int:
    """1-based day offset within the quota quarter.

    ``quarter_start`` itself is day 1. This is the axis for comparing the same
    point across different quarters.
    """
    return (d - quarter_start(d)).days + 1


def quarter_length(d: date) -> int:
    """Number of days in the quota quarter containing ``d``."""
    return (quarter_end(d) - quarter_start(d)).days + 1


@dataclass(frozen=True)
class QuotaPeriod:
    """Everything about the quota period a date falls in."""

    year_label: str
    quarter: int
    quarter_label: str
    start: date
    end: date
    day_in_quarter: int
    quarter_length: int

    @property
    def key(self) -> str:
        """Stable sortable identifier, e.g. ``'2026/27-Q1'``."""
        return f"{self.year_label}-Q{self.quarter}"

    @property
    def pct_elapsed(self) -> float:
        """How far through the quarter this date is, 0-100.

        Useful as the honest yardstick for "is this quota being used too fast?":
        a quota 60% allocated 30% of the way through its quarter is on a very
        different trajectory from the same 60% at the end.
        """
        return round(100.0 * self.day_in_quarter / self.quarter_length, 1)


def describe(d: date) -> QuotaPeriod:
    """Resolve a date into its full quota period."""
    return QuotaPeriod(
        year_label=quota_year_label(d),
        quarter=quota_quarter(d),
        quarter_label=QUARTER_LABELS[quota_quarter(d)],
        start=quarter_start(d),
        end=quarter_end(d),
        day_in_quarter=day_in_quarter(d),
        quarter_length=quarter_length(d),
    )


def quarters_since(start: date, end: date) -> Iterator[QuotaPeriod]:
    """Yield each quota quarter touched by the range, oldest first.

    Used to populate the "compare against previous quarters" selector without
    guessing which quarters actually hold data.
    """
    seen: set[str] = set()
    cur = quarter_start(start)
    while cur <= end:
        period = describe(cur)
        if period.key not in seen:
            seen.add(period.key)
            yield period
        cur = period.end + timedelta(days=1)


def parse_period_key(key: str) -> Optional[date]:
    """Turn ``'2026/27-Q1'`` back into that quarter's start date.

    Returns None rather than raising: the value arrives from a URL query
    string, so a malformed one is a bad request, not a crash.
    """
    try:
        year_part, quarter_part = key.split("-Q")
        start_year = int(year_part.split("/")[0])
        quarter = int(quarter_part)
        if quarter not in _QUARTER_START_MONTH:
            return None
        month = _QUARTER_START_MONTH[quarter]
        # Q3/Q4 (Jan-Mar, Apr-Jun) fall in the calendar year AFTER the quota
        # year opened; Q1/Q2 fall in the same one.
        year = start_year if quarter in (1, 2) else start_year + 1
        return date(year, month, 1)
    except (ValueError, AttributeError, IndexError):
        return None
