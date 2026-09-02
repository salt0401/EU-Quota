"""The rendering seam: one Jinja environment, one set of filters.

Three callers now render these templates -- the live Flask site, the server-side
static exporter, and the downloader rendering locally on a colleague's machine.
All three come through here, so a change to a display filter cannot apply to two
of them and not the third.

It also keeps Flask out of the downloader. The exporter used to borrow the Flask
app purely for its Jinja environment, which would have dragged Flask and
Werkzeug into the exe for no benefit. Building the environment directly costs a
dozen lines and keeps the dependency set to Jinja2 + SQLAlchemy.
"""

from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal, ROUND_FLOOR

__all__ = ["templates_dir", "build_jinja_env", "FILTERS", "fmt_tonnes", "fmt_pct",
           "fmt_date", "displayed_pct", "DISPLAY_DP"]

EM_DASH = "—"


def fmt_tonnes(v):
    return EM_DASH if v is None else "{:,.0f}".format(v)


#: How many decimals the site prints a percentage to. Every threshold in the
#: system classifies on THIS figure, so what a reader sees and what the system
#: decided cannot disagree.
DISPLAY_DP = 1
_QUANTUM = Decimal(1).scaleb(-DISPLAY_DP)


def displayed_pct(v):
    """The percentage as the reader sees it: TRUNCATED, never rounded up.

    This lives here, in the display seam, because it *is* the display rule --
    ``fmt_pct`` below prints exactly what it returns, and every band, filter and
    sort in ``queries`` classifies on it. One definition, one behaviour, three
    renderers.

    Truncating rather than rounding is a deliberate decision (2026-09-02) and it
    is what makes the whole defect class structural rather than a list of
    patched thresholds. Because ``displayed_pct(v) <= v`` always holds, the
    displayed figure can never cross a boundary the raw value has not already
    crossed. So "shown at or above 90%" implies "actually at or above 90%" for
    every threshold, present and future, without anyone re-checking each one.
    Rounding gave the opposite guarantee at exactly the moment it mattered: 89.96
    printed as 90.0 while the authoritative figure was below 90 -- and 90 is not
    a colour, it is the point where imports go through a different customs
    process.

    The accepted cost, stated plainly: a quota at 99.99% now prints 99.9% and
    sits in the critical band rather than the exhausted one. It is not yet
    exhausted, so that is defensible, but it is a real change in what the page
    says about a real quota.
    """
    if v is None:
        return None
    # Decimal, not ``math.floor(v * 10) / 10``. Truncation on binary floats is
    # where this kind of helper usually goes wrong: 2.9 is not exactly 2.9, so
    # multiplying up can land a hair under an integer and truncate a whole step
    # down. A sweep of every percentage this system can carry (0-100 at 4dp)
    # happens to find no disagreement between the two -- but "no counterexample
    # in the domain I tested" is the weaker guarantee, and the entire point of
    # this change is to close the class structurally. ``Decimal(str(v))`` takes
    # the shortest decimal that round-trips the float, which is the number a
    # human would say it is, and quantizes that.
    return float(Decimal(str(v)).quantize(_QUANTUM, rounding=ROUND_FLOOR))


def fmt_pct(v):
    """Print the displayed figure -- never re-derive it from the raw value.

    Formatting with ``{:.1f}`` directly would round here while ``displayed_pct``
    truncates elsewhere, which would put the number on the page back out of step
    with the band beside it. That is the exact defect this seam exists to close.
    """
    d = displayed_pct(v)
    return EM_DASH if d is None else "{:,.1f}%".format(d)


def fmt_date(v):
    if not v:
        return EM_DASH
    return v.isoformat() if isinstance(v, date) else str(v)


#: Registered identically on the Flask app and on the bare environment.
FILTERS = {"tonnes": fmt_tonnes, "pct": fmt_pct, "d": fmt_date}


def templates_dir() -> str:
    """Where the templates live, whether running from source or from an exe.

    PyInstaller unpacks bundled data under ``sys._MEIPASS`` at run time, so the
    downloader exe finds them there; everything else finds them next to this
    file.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = os.path.join(meipass, "webapp", "templates")
        if os.path.isdir(bundled):
            return bundled
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


def build_jinja_env(searchpath: str = None):
    """A Jinja environment configured exactly as the live site's is.

    Autoescaping is on for the same reason Flask turns it on: quota categories
    and country names are data, and one stray angle bracket should not become
    markup.
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(searchpath or templates_dir()),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters.update(FILTERS)
    return env
