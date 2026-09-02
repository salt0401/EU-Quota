# -*- coding: utf-8 -*-
"""The one definition of how a quota percentage is shown and classified.

**Why this is a root module rather than living in `src/` or `webapp/`.** Both
need it, and neither may import the other: `webapp/__init__.py` states that
nothing in `src/` imports the webapp, so the daily scraper never grows a web
dependency; and `webapp/render.py` is bundled into the downloader exe, so it
must not reach into `src/` and drag pandas in behind it. A dependency-free leaf
module that both import is the only shape that keeps those two rules and still
leaves one definition of the rule.

Standard library only, deliberately. Import it from anywhere.

The rule it holds is the resolution of a defect class this project hit three
times: a value rounded for display while logic ran on the raw value, so what a
person saw contradicted what the system decided.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR

__all__ = ["DISPLAY_DP", "displayed_pct", "BAND_EXHAUSTED", "BAND_CRITICAL",
           "BAND_HIGH", "band_for"]

#: How many decimals a percentage is printed to.
DISPLAY_DP = 1
_QUANTUM = Decimal(1).scaleb(-DISPLAY_DP)

#: Band boundaries, in percent. 90 is not a colour: past it, imports against
#: that quota go through a different customs process, so the boundary is a state
#: change in somebody's job.
BAND_EXHAUSTED = 100.0
BAND_CRITICAL = 90.0
BAND_HIGH = 75.0


def displayed_pct(v):
    """The percentage as the reader sees it: TRUNCATED, never rounded up.

    Truncating rather than rounding is a deliberate decision (2026-09-02) and it
    is what makes the defect class structural rather than a list of patched
    thresholds. Because ``displayed_pct(v) <= v`` always holds, the displayed
    figure can never cross a boundary the raw value has not already crossed. So
    "shown at or above 90%" implies "actually at or above 90%" for every
    threshold, present and future, without anyone re-checking each one. Rounding
    gave the opposite guarantee at exactly the moment it mattered: 89.96 printed
    as 90.0 while the authoritative figure was below 90.

    The accepted cost, stated plainly: a quota at 99.99% prints 99.9% and sits
    in the critical band rather than the exhausted one. It is not yet exhausted,
    so that is defensible, but it is a real change in what the page says.

    ``Decimal``, not ``math.floor(v * 10) / 10``. Truncation on binary floats is
    where this kind of helper usually goes wrong: 2.9 is not exactly 2.9, so
    multiplying up can land a hair under an integer and truncate a whole step
    down. A sweep of every percentage this system can carry (0-100 at 4dp) finds
    no disagreement between the two -- but "no counterexample in the domain I
    tested" is the weaker guarantee, and the point of this rule is to stop
    relying on that. ``Decimal(str(v))`` takes the shortest decimal that
    round-trips the float, which is the number a human would say it is.
    """
    if v is None:
        return None
    return float(Decimal(str(v)).quantize(_QUANTUM, rounding=ROUND_FLOOR))


def band_for(pct):
    """``exhausted`` / ``critical`` / ``high`` / ``normal``, or None if unknown.

    Classifies on the DISPLAYED figure, so the band always agrees with the
    number printed beside it. Banding on the raw figure is what once put a row
    reading "100.0%" under a tile labelled "75-99% used".

    Takes the raw percentage and truncates it here, so no caller has to remember
    to do it first.
    """
    d = displayed_pct(pct)
    if d is None:
        return None
    if d >= BAND_EXHAUSTED:
        return "exhausted"
    if d >= BAND_CRITICAL:
        return "critical"
    if d >= BAND_HIGH:
        return "high"
    return "normal"
