# -*- coding: utf-8 -*-
"""
MEPS internal quota tracker — web application.

Internal only. This is deliberately NOT the customer-facing MEPS site.

    python -m webapp.app                      # http://127.0.0.1:8081
    python -m webapp.app --host 0.0.0.0       # only behind a firewall/proxy

Binds to 127.0.0.1 by default on purpose. The host it runs on has SQL Server
already exposed to the open internet, so nothing here should widen that surface
by accident — see docs/INTERNAL_SITE.md for the three ways to let researchers
reach it, and which of them needs the IONOS account holder.

Server-rendered HTML with a small amount of vanilla JavaScript. No CDN, no npm,
no build step: the site must still work in five years without anyone
reconstructing a toolchain, and an internal tool that cannot reach a CDN should
not degrade.
"""

from __future__ import annotations

import argparse
import io
import os
import secrets
from datetime import date

from flask import Flask, Response, abort, g, redirect, render_template, request, url_for

from webapp import quota_period as qp
from webapp import queries
from webapp.db import create_all, get_engine

# A password here makes the site useless to a casual passer-by; it is not a
# substitute for restricting who can reach the port. Both, or neither is worth
# much.
PASSWORD_FILE = os.environ.get(
    "QUOTA_SITE_PASSWORD_FILE",
    r"C:\DataScienceProject\_secrets\quota-site-password.txt")


def _read_password() -> str | None:
    path = os.environ.get("QUOTA_SITE_PASSWORD_FILE", PASSWORD_FILE)
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def create_app(db_url: str | None = None, require_auth: bool | None = None) -> Flask:
    app = Flask(__name__)
    engine = get_engine(db_url)
    create_all(engine)
    app.config["ENGINE"] = engine

    password = _read_password()
    if require_auth is None:
        require_auth = password is not None
    app.config["PASSWORD"] = password
    app.config["REQUIRE_AUTH"] = require_auth

    @app.before_request
    def _auth():
        if not app.config["REQUIRE_AUTH"] or request.path == "/healthz":
            return None
        auth = request.authorization
        expected = app.config["PASSWORD"] or ""
        # compare_digest: constant-time, so a wrong password cannot be guessed
        # one character at a time by timing the response.
        if (auth and auth.password
                and secrets.compare_digest(auth.password, expected)):
            return None
        return Response(
            "Authentication required.", 401,
            {"WWW-Authenticate": 'Basic realm="MEPS Quota Tracker"'})

    @app.before_request
    def _connect():
        g.conn = engine.connect()

    @app.teardown_request
    def _close(exc):
        conn = g.pop("conn", None)
        if conn is not None:
            conn.close()

    # ---------------------------------------------------------------- views --

    @app.route("/healthz")
    def healthz():
        try:
            with engine.connect() as c:
                latest = queries.latest_snapshot_date(c)
            return {"ok": latest is not None, "data_date": latest.isoformat() if latest else None}
        except Exception as e:                      # noqa: BLE001 - health must not 500
            return {"ok": False, "error": str(e)}, 503

    @app.route("/")
    def index():
        latest = queries.latest_snapshot_date(g.conn)
        if latest is None:
            return render_template("empty.html", db=engine.dialect.name)

        region = (request.args.get("region") or "").upper() or None
        if region not in (None, "EU", "UK"):
            region = None
        search = request.args.get("q") or None
        try:
            min_pct = float(request.args["min_pct"]) if request.args.get("min_pct") else None
        except ValueError:
            min_pct = None
        pressure_only = request.args.get("pressure") == "1"
        # Anything unrecognised falls back to the default rather than 500ing:
        # these arrive from a URL and a bad value is a bad request, not a crash.
        sort = request.args.get("sort") if request.args.get("sort") in ("pressure", "name") else "pressure"

        return render_template(
            "index.html",
            groups=queries.categories_overview(g.conn, latest, region=region,
                                               search=search, min_pct=min_pct,
                                               pressure_only=pressure_only,
                                               sort=sort),
            summary=queries.summary_counts(g.conn, latest),
            freshness=queries.freshness(g.conn),
            region=region, search=search or "", min_pct=min_pct,
            pressure_only=pressure_only, sort=sort,
        )

    @app.route("/quota/<region>/<order_number>")
    def quota(region: str, order_number: str):
        region = region.upper()
        if region not in ("EU", "UK"):
            abort(404)

        detail = queries.quota_detail(g.conn, region, order_number)
        if detail is None:
            abort(404)

        quarters = queries.available_quarters(g.conn, region, order_number)
        requested = request.args.get("period")
        start = qp.parse_period_key(requested) if requested else None
        if start is None and quarters:
            start = quarters[0]["start"]

        series = queries.quota_series(g.conn, region, order_number, quarter_start=start)

        # Describe the LATEST DAY WE HAVE DATA FOR, not the quarter's first day.
        # describe(quarter_start) always reports "day 1 of 92, 1.1% elapsed",
        # which silently breaks the ahead/behind-the-calendar verdict below it:
        # every quota would be compared against 1.1% and so read as "ahead".
        period = None
        if series:
            period = qp.describe(date.fromisoformat(series[-1]["date"]))
        elif start:
            period = qp.describe(start)

        return render_template(
            "quota.html",
            quota=detail, series=series, quarters=quarters,
            period=period, selected=period.key if period else None,
            freshness=queries.freshness(g.conn),
        )

    # ------------------------------------------------------------- filters --

    @app.template_filter("tonnes")
    def _tonnes(v):
        return "—" if v is None else f"{v:,.0f}"

    @app.template_filter("pct")
    def _pct(v):
        return "—" if v is None else f"{v:,.1f}%"

    @app.template_filter("d")
    def _d(v):
        return "—" if not v else (v.isoformat() if isinstance(v, date) else str(v))

    return app


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the internal quota tracker site.")
    parser.add_argument("--host", default="127.0.0.1",
                        help="default 127.0.0.1; do not widen without reading "
                             "docs/INTERNAL_SITE.md")
    parser.add_argument("--port", type=int, default=8081)
    parser.add_argument("--db-url", default=None)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--no-auth", action="store_true",
                        help="local development only")
    args = parser.parse_args(argv)

    app = create_app(db_url=args.db_url,
                     require_auth=False if args.no_auth else None)
    if not app.config["REQUIRE_AUTH"]:
        print("  WARNING: no password configured - the site is UNAUTHENTICATED.")
        print(f"  Create {PASSWORD_FILE} to enable Basic auth.")
    print(f"  Serving on http://{args.host}:{args.port}  (db: {app.config['ENGINE'].dialect.name})")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
