"""View contexts shared by the live Flask site and the static export.

WHY THIS MODULE EXISTS. The static bundle in ``webapp/export.py`` must render
the *same* pages as the live site. The obvious way to build it -- a second
renderer with its own queries and its own copy of the templates -- drifts the
moment either side is touched, and the drift is silent. So both renderers call
the functions here, and both render the same Jinja templates. There is exactly
one place that decides what a page contains.

The one thing that genuinely cannot be shared is link generation: the live site
resolves routes through ``url_for`` and the static bundle needs relative file
paths that work from ``file://``. That difference is isolated into the two link
providers at the bottom, which the templates reach through ``link_index()`` and
``link_quota()`` rather than calling ``url_for`` directly.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from webapp import queries
from webapp import quota_period as qp

__all__ = [
    "index_context",
    "quota_context",
    "normalise_index_args",
    "static_link_provider",
]


def normalise_index_args(region=None, search=None, min_pct=None,
                         pressure_only=False, sort=None) -> dict:
    """Coerce raw query-string values into the shapes the queries expect.

    Kept here rather than in the route so the static exporter validates
    identically. Anything unrecognised falls back to the default rather than
    raising: these values arrive from a URL, and a bad one is a bad request,
    not a crash.
    """
    reg = (region or "").upper() or None
    if reg not in (None, "EU", "UK"):
        reg = None
    try:
        mp = float(min_pct) if min_pct not in (None, "") else None
    except (TypeError, ValueError):
        mp = None
    return {
        "region": reg,
        "search": search or None,
        "min_pct": mp,
        "pressure_only": bool(pressure_only),
        "sort": sort if sort in ("pressure", "name") else "pressure",
    }


def index_context(conn, *, region=None, search=None, min_pct=None,
                  pressure_only=False, sort="pressure") -> Optional[dict]:
    """Everything ``index.html`` needs, or ``None`` when there is no data.

    ``None`` means the caller should render ``empty.html``; it is not an error.
    """
    latest = queries.latest_snapshot_date(conn)
    if latest is None:
        return None

    args = normalise_index_args(region, search, min_pct, pressure_only, sort)
    return {
        "groups": queries.categories_overview(
            conn, latest,
            region=args["region"], search=args["search"],
            min_pct=args["min_pct"], pressure_only=args["pressure_only"],
            sort=args["sort"],
        ),
        "summary": queries.summary_counts(conn, latest),
        "freshness": queries.freshness(conn),
        "region": args["region"],
        "search": args["search"] or "",
        "min_pct": args["min_pct"],
        "pressure_only": args["pressure_only"],
        "sort": args["sort"],
    }


def quota_context(conn, region: str, order_number: str,
                  period_key: Optional[str] = None) -> Optional[dict]:
    """Everything ``quota.html`` needs, or ``None`` when the quota is unknown.

    ``None`` means 404 on the live site and "skip this page" in the export.
    """
    region = (region or "").upper()
    if region not in ("EU", "UK"):
        return None

    detail = queries.quota_detail(conn, region, order_number)
    if detail is None:
        return None

    quarters = queries.available_quarters(conn, region, order_number)
    start = qp.parse_period_key(period_key) if period_key else None
    if start is None and quarters:
        start = quarters[0]["start"]

    series = queries.quota_series(conn, region, order_number, quarter_start=start)

    # Describe the LATEST DAY WE HAVE DATA FOR, not the quarter's first day.
    # describe(quarter_start) always reports "day 1 of 92, 1.1% elapsed", which
    # silently breaks the ahead/behind-the-calendar verdict: every quota would
    # be compared against 1.1% and so read as "ahead".
    period = None
    if series:
        period = qp.describe(date.fromisoformat(series[-1]["date"]))
    elif start:
        period = qp.describe(start)

    return {
        "quota": detail,
        "series": series,
        "quarters": quarters,
        "period": period,
        "selected": period.key if period else None,
        "freshness": queries.freshness(conn),
    }


# --------------------------------------------------------------- links -----
#
# The templates call link_index() / link_quota() instead of url_for(), so the
# same template renders for a Flask route and for a file on disk. This is the
# only behavioural difference between the two renderers, and keeping it to one
# small seam is the point.

def quota_filename(region: str, order_number: str) -> str:
    """Filename for a quota page in the static bundle.

    Region is part of the name because order numbers are only unique *within*
    a region -- EU and UK number-spaces are separate and have collided before.
    """
    return "{}-{}.html".format(region.upper(), order_number)


def static_link_provider(depth: int = 0) -> dict:
    """Link helpers that resolve to relative paths under ``file://``.

    ``depth`` is how many directories deep the rendered page sits, so a quota
    page one level down gets ``../index.html``.
    """
    prefix = "../" * depth

    def link_index(**_kwargs) -> str:
        # Query-string arguments are meaningless in a static bundle: filtering
        # is done client-side. Swallow them rather than emitting a dead link.
        return prefix + "index.html"

    def link_quota(region: str, order_number: str) -> str:
        return prefix + "quota/" + quota_filename(region, order_number)

    return {"link_index": link_index, "link_quota": link_quota}
