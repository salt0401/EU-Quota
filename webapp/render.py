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

# The display rule itself lives in a dependency-free root module, because
# `src/` needs the same rule and may not import this package. See
# `quota_display.py` for why that shape is the only one that works.
from quota_display import DISPLAY_DP, displayed_pct  # noqa: F401 - re-exported

__all__ = ["templates_dir", "build_jinja_env", "FILTERS", "fmt_tonnes", "fmt_pct",
           "fmt_date", "displayed_pct", "DISPLAY_DP"]

EM_DASH = "—"


def fmt_tonnes(v):
    return EM_DASH if v is None else "{:,.0f}".format(v)


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
