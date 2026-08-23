# -*- coding: utf-8 -*-
"""Tests for the static offline bundle.

The failure this suite exists to prevent is DRIFT: the offline bundle silently
disagreeing with the live site. So the tests compare the two rather than
checking the bundle in isolation.

ONE HONEST LIMITATION, stated rather than hidden. No JavaScript engine is
available on this host (no node, no playwright, and installing either onto a
production box to run a test is not a trade worth making). So the client-side
filter is NOT executed by these tests. What is tested instead:

  * the DATA CONTRACT -- that every attribute the filter reads is emitted, and
    carries the value the server used;
  * the ALGORITHM -- a Python transcription of the client predicate produces
    the same rows as the server for the same inputs;
  * a SOURCE GUARD -- that the JavaScript never re-derives the band from a raw
    percentage, which is the specific way this could break.

If the transcription below and the JavaScript in index.html ever disagree, this
suite passes while the bundle is wrong. Keep them in step; the source guard is
there to make the dangerous edit fail loudly.
"""
import io
import os
import re
import sys
import zipfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

pytest.importorskip("flask", reason="webapp extras not installed")
pytest.importorskip("sqlalchemy", reason="webapp extras not installed")

from webapp import etl, export, queries, views          # noqa: E402
from webapp.db import get_engine                        # noqa: E402
from webapp.tests.test_etl_and_queries import row, write_history   # noqa: E402


@pytest.fixture
def built(tmp_path):
    """A loaded database plus a rendered bundle.

    Includes a quota at 99.98%, which rounds to 100.0% for display. That single
    row is the reason this suite exists: it must be classified identically on
    both sides of the boundary.
    """
    body = ""
    for d in ("2026-07-06", "2026-07-07"):
        body += row(d, region="EU", order="099491", cat="Quarto Plates - 7",
                    country="Turkiye", limit="1000", alloc="250", pct="25.0")
        body += row(d, region="EU", order="099716", cat="Hot Rolled - 1",
                    country="India", limit="1000", alloc="999.8", pct="99.98")
        body += row(d, region="UK", order="058627", cat="Rebar - 13",
                    country="Egypt", limit="1000", alloc="920", pct="92.0")
        body += row(d, region="UK", order="058600", cat="Wire Rod - 16",
                    country="Norway", limit="1000", alloc="800", pct="80.0")
    pub = write_history(tmp_path, body)
    db = "sqlite:///" + str(tmp_path / "t.db").replace("\\", "/")
    etl.main(["--published", pub, "--db-url", db, "--rebuild"])

    out = tmp_path / "out"
    stats = export.build(str(out), db_url=db, quiet=True)
    return {"db": db, "dir": stats["dir"], "stats": stats, "out": str(out)}


def _read(path):
    return io.open(path, encoding="utf-8").read()


def _rows_from_index(html):
    """Parse the data attributes the client filter reads."""
    out = []
    for tr in re.findall(r"<tr\s+data-region=.*?</tr>", html, re.S):
        attrs = dict(re.findall(r'data-([a-z]+)="([^"]*)"', tr))
        out.append(attrs)
    return out


def _client_filter(rows, region="", needle="", min_pct=None, pressure_only=False):
    """Python transcription of the client-side predicate in index.html.

    Must mirror it exactly. Note the deliberate asymmetry, which is the live
    site's own behaviour and is preserved rather than tidied:
      * min_pct compares the RAW percentage;
      * the band is READ, never recomputed.
    """
    kept = []
    for r in rows:
        if region and r["region"] != region:
            continue
        if needle:
            n = needle.strip().lower()
            if not (n in r["cat"].lower() or n in r["country"].lower() or n in r["order"]):
                continue
        if min_pct is not None:
            if r["pct"] == "" or float(r["pct"]) < min_pct:
                continue
        kept.append(r)

    if pressure_only:
        by_cat = {}
        for r in kept:
            by_cat.setdefault((r["region"], r["cat"]), []).append(r)
        keep_cats = {k for k, items in by_cat.items()
                     if any(i["band"] == "exhausted" for i in items)
                     or any(i["band"] in ("critical", "high") for i in items)}
        kept = [r for r in kept if (r["region"], r["cat"]) in keep_cats]
    return {(r["region"], r["order"]) for r in kept}


def _server_filter(db, **kw):
    with get_engine(db).connect() as conn:
        latest = queries.latest_snapshot_date(conn)
        groups = queries.categories_overview(conn, latest, **kw)
    return {(q["region"], q["order_number"]) for g in groups for q in g["quotas"]}


# --------------------------------------------------------------- shape -----

def test_bundle_has_index_and_a_page_per_quota(built):
    root = built["dir"]
    assert os.path.exists(os.path.join(root, "index.html"))
    assert os.path.exists(os.path.join(root, "README.txt"))
    pages = os.listdir(os.path.join(root, "quota"))
    assert len(pages) == 4
    assert "EU-099491.html" in pages and "UK-058627.html" in pages


def test_index_renders_without_a_server(built):
    html = _read(os.path.join(built["dir"], "index.html"))
    assert "<html" in html.lower()
    assert "quotas tracked" in html
    # every quota is present, because the client filter needs them all
    for order in ("099491", "099716", "058627", "058600"):
        assert order in html


def test_quota_page_renders(built):
    html = _read(os.path.join(built["dir"], "quota", "EU-099491.html"))
    assert "099491" in html
    assert "Quarto Plates - 7" in html


# ---------------------------------------------------------- self-contained --

def test_no_external_references_anywhere(built):
    for folder, _d, files in os.walk(built["dir"]):
        for name in files:
            if not name.endswith(".html"):
                continue
            html = _read(os.path.join(folder, name))
            assert "http://" not in html and "https://" not in html, name
            assert 'href="/' not in html and 'src="/' not in html, name
            assert "cdn." not in html and "fonts.googleapis" not in html, name


def test_nothing_secret_in_the_bundle(built):
    pattern = re.compile(r"password|secret|api[_-]?key|authorization", re.I)
    for folder, _d, files in os.walk(built["dir"]):
        for name in files:
            body = _read(os.path.join(folder, name))
            assert not pattern.search(body), "{} contains a sensitive-looking token".format(name)


def test_every_internal_link_resolves(built):
    root = built["dir"]
    checked = 0
    for folder, _d, files in os.walk(root):
        for name in files:
            if not name.endswith(".html"):
                continue
            html = _read(os.path.join(folder, name))
            for href in re.findall(r'href="([^"]+)"', html):
                if href.startswith(("http://", "https://", "#", "mailto:", "data:")):
                    continue
                checked += 1
                target = os.path.normpath(os.path.join(folder, href.split("#")[0]))
                assert os.path.exists(target), "{} -> {}".format(name, href)
    assert checked > 0


# ------------------------------------------------- client vs server parity --

@pytest.mark.parametrize("kw", [
    {},
    {"region": "EU"},
    {"region": "UK"},
    {"search": "rebar"},
    {"search": "099"},
    {"min_pct": 50.0},
    {"min_pct": 90.0},
    {"min_pct": 100.0},
    {"pressure_only": True},
    {"region": "EU", "min_pct": 90.0},
])
def test_client_filter_matches_server_filter(built, kw):
    rows = _rows_from_index(_read(os.path.join(built["dir"], "index.html")))
    client = _client_filter(
        rows,
        region=kw.get("region") or "",
        needle=kw.get("search") or "",
        min_pct=kw.get("min_pct"),
        pressure_only=kw.get("pressure_only", False),
    )
    assert client == _server_filter(built["db"], **kw)


def test_ninety_percent_boundary_is_identical_on_both_sides(built):
    """The rounding rule with an operational consequence.

    099716 sits at 99.98%: it DISPLAYS as 100.0% and is banded 'exhausted'.
    The static bundle must classify it the same way the live site does -- and
    must reproduce the live site's own quirk that the numeric 'Exhausted only'
    filter (raw >= 100) excludes it, rather than quietly 'fixing' it and
    diverging.
    """
    rows = {r["order"]: r for r in _rows_from_index(
        _read(os.path.join(built["dir"], "index.html")))}

    edge = rows["099716"]
    assert float(edge["pct"]) < 100.0            # raw value is below the line
    assert round(float(edge["pct"]), 1) >= 100.0  # displayed value is on it
    assert edge["band"] == "exhausted"            # server said so; bundle carries it

    # >=90% filter: the edge row and the 92% row qualify, the 80% one does not
    at90 = _client_filter(list(rows.values()), min_pct=90.0)
    assert ("EU", "099716") in at90 and ("UK", "058627") in at90
    assert ("UK", "058600") not in at90
    assert at90 == _server_filter(built["db"], min_pct=90.0)

    # and the documented quirk, preserved deliberately
    at100 = _client_filter(list(rows.values()), min_pct=100.0)
    assert ("EU", "099716") not in at100
    assert at100 == _server_filter(built["db"], min_pct=100.0)


def test_band_is_carried_not_recomputed(built):
    """Guard against the specific dangerous edit.

    If someone replaces the data-band lookup with a numeric threshold on
    data-pct, the offline bundle starts disagreeing with the live site at the
    boundary. Assert the emitted rows carry the band, and that the script reads
    it rather than deriving it.
    """
    html = _read(os.path.join(built["dir"], "index.html"))
    for r in _rows_from_index(html):
        assert r["band"] in ("exhausted", "critical", "high", "normal")

    script = html[html.index("<script>", html.index("data-band")):]
    assert "data-band" in script, "the client filter must read the server's band"
    assert "getAttribute('data-band')" in script
    # it must not recompute the classification from the percentage
    assert not re.search(r"data-pct[^\n]*>=\s*(90|75|100)\b", script)
    assert "Math.round" not in script.split("cPct")[0], \
        "no rounding before the band is used -- classification stays in Python"


# ----------------------------------------------------------------- zip -----

def test_zip_round_trips(built, tmp_path):
    zp = str(tmp_path / "bundle.zip")
    export.make_zip(built["dir"], zp)
    with zipfile.ZipFile(zp) as z:
        names = z.namelist()
        assert "index.html" in names
        assert any(n.startswith("quota/") for n in names)
        assert z.read("index.html").decode("utf-8").strip().startswith("<!")
    assert not os.path.exists(zp + ".part"), "the temporary part-file must be gone"


def test_failed_build_leaves_no_partial_bundle(tmp_path):
    """A failure must not leave a half-written bundle for the uploader."""
    out = tmp_path / "out"
    db = "sqlite:///" + str(tmp_path / "empty.db").replace("\\", "/")
    get_engine(db)                                   # empty database, no rows
    with pytest.raises(Exception):
        export.build(str(out), db_url=db, quiet=True)
    assert not os.path.exists(os.path.join(str(out), export.BUNDLE_DIRNAME))
