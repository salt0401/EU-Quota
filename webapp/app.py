# -*- coding: utf-8 -*-
"""
MEPS internal quota tracker — web application.

Internal only. This is deliberately NOT the customer-facing MEPS site.

    python -m webapp.app                      # http://127.0.0.1:8081
    python -m webapp.app --host 0.0.0.0       # only behind a firewall/proxy

Binds to 127.0.0.1 by default on purpose. The host it runs on is a production
server, and nothing here should widen its surface by accident. Researchers get
this data through Power BI (see docs/INTERNAL_SITE.md); this site is a local
diagnostics tool, not a deployment target.

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
from webapp import views
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
        # Context is built by webapp.views so the static export renders the
        # identical page from the identical data. See webapp/export.py.
        ctx = views.index_context(
            g.conn,
            region=request.args.get("region"),
            search=request.args.get("q"),
            min_pct=request.args.get("min_pct"),
            pressure_only=request.args.get("pressure") == "1",
            sort=request.args.get("sort"),
        )
        if ctx is None:
            return render_template("empty.html", db=engine.dialect.name)
        return render_template("index.html", **ctx)

    @app.route("/quota/<region>/<order_number>")
    def quota(region: str, order_number: str):
        ctx = views.quota_context(g.conn, region, order_number,
                                  period_key=request.args.get("period"))
        if ctx is None:
            abort(404)
        return render_template("quota.html", **ctx)

    # The templates reach links through these rather than url_for, so the very
    # same template file also renders into the offline bundle. Live mode simply
    # forwards to url_for; static mode substitutes relative paths.
    @app.context_processor
    def _links():
        return {
            "link_index": lambda **kw: url_for("index", **kw),
            "link_quota": lambda region, order_number: url_for(
                "quota", region=region, order_number=order_number),
            "static_mode": False,
        }

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
