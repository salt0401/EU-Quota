"""Static, offline rendering of the internal quota tracker.

Produces a self-contained bundle -- the index plus one page per quota -- that
opens from ``file://`` with no server, no Python and no network, so colleagues
can read the dashboard alongside the workbooks the downloader already fetches.

SINGLE SOURCE OF TRUTH. This module renders the *same* Jinja templates through
the *same* Jinja environment, from the *same* contexts in ``webapp.views``,
that the live site uses. It is a different output target, not a second
implementation. The two things that genuinely differ are isolated:

  * links   -- ``webapp.views.static_link_provider`` swaps ``url_for`` routes
               for relative file paths.
  * filters -- the live index filters server-side and re-renders; a file:// page
               cannot, so the static index renders EVERY row and the template's
               ``static_mode`` branch hides what does not match. The band that
               drives the >=90% classification is NEVER recomputed in
               JavaScript; it is emitted as ``data-band`` from the value Python
               already computed. See the comment in ``index.html``.

FAILURE ISOLATION. Nothing here may endanger the daily data publish. The whole
bundle is built into a temporary directory and only moved into place once every
page has rendered, so a failure part-way leaves no partial bundle for the
uploader to find. The caller (``tools/server-daily-task.ps1``) runs this as a
separate, explicitly non-fatal step after the data is already committed and
pushed.

Usage:
    <venv>\\Scripts\\python.exe -m webapp.export --out data/output/2026-08-23
    <venv>\\Scripts\\python.exe -m webapp.export --out DIR --zip DIR/MEPS_Quota_Site.zip
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
import time
import zipfile
from datetime import date
from typing import Optional

BUNDLE_DIRNAME = "quota-site"
ZIP_BASENAME = "MEPS_Quota_Site.zip"


def _render(env, name, **ctx) -> str:
    """Render through the app's own Jinja environment.

    Deliberately not ``flask.render_template``: that would also apply the live
    site's context processors, and this needs the static link helpers instead.
    Using the environment directly makes the substitution explicit rather than
    relying on which context wins.
    """
    return env.get_template(name).render(**ctx)


def build(out_dir: str, db_url: Optional[str] = None, quiet: bool = False) -> dict:
    """Render the whole bundle into ``out_dir``. Returns a small stats dict."""
    # Imported here so a missing webapp extra cannot break module import for
    # callers that only want the constants above.
    from webapp import queries, views
    from webapp.app import create_app

    t0 = time.time()
    app = create_app(db_url=db_url, require_auth=False)
    env = app.jinja_env
    engine = app.config["ENGINE"]

    staging = tempfile.mkdtemp(prefix="quota-site-")
    pages = 0
    skipped = 0
    try:
        with engine.connect() as conn:
            latest = queries.latest_snapshot_date(conn)
            if latest is None:
                raise RuntimeError("no data in the tracker database -- nothing to export")

            # --- index: every row, unfiltered. The client filter needs them all.
            idx = views.index_context(conn)
            if idx is None:
                raise RuntimeError("index context unavailable despite a snapshot date")
            html = _render(env, "index.html", static_mode=True,
                           **views.static_link_provider(depth=0), **idx)
            with open(os.path.join(staging, "index.html"), "w", encoding="utf-8") as f:
                f.write(html)
            pages += 1

            # --- one page per quota in the latest snapshot
            quota_dir = os.path.join(staging, "quota")
            os.makedirs(quota_dir, exist_ok=True)
            targets = [(q["region"], q["order_number"])
                       for g in idx["groups"] for q in g["quotas"]]

            links = views.static_link_provider(depth=1)
            for region, order_number in targets:
                ctx = views.quota_context(conn, region, order_number)
                if ctx is None:
                    skipped += 1
                    continue
                html = _render(env, "quota.html", static_mode=True, **links, **ctx)
                fname = views.quota_filename(region, order_number)
                with open(os.path.join(quota_dir, fname), "w", encoding="utf-8") as f:
                    f.write(html)
                pages += 1
                if not quiet and pages % 100 == 0:
                    print("    rendered {} pages...".format(pages))

            _write_readme(staging, latest, pages)

        # Only now, with every page written, put the bundle where the caller
        # expects it. A failure above leaves the destination untouched.
        dest = os.path.join(out_dir, BUNDLE_DIRNAME)
        os.makedirs(out_dir, exist_ok=True)
        if os.path.exists(dest):
            shutil.rmtree(dest)
        shutil.move(staging, dest)
        staging = None
    finally:
        if staging and os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)

    elapsed = time.time() - t0
    if not quiet:
        print("  Static site: {} pages ({} skipped) in {:.1f}s -> {}".format(
            pages, skipped, elapsed, dest))
    return {"pages": pages, "skipped": skipped, "seconds": round(elapsed, 1),
            "dir": dest, "data_date": latest.isoformat()}


def _write_readme(root: str, data_date: date, pages: int) -> None:
    text = (
        "MEPS EU/UK Steel Quota Tracker - offline copy\n"
        "=============================================\n\n"
        "Data date: {}\n"
        "Pages    : {}\n\n"
        "Open index.html in any browser. No internet connection is needed and\n"
        "nothing is installed: this is a snapshot of the internal tracker as it\n"
        "stood on the data date above.\n\n"
        "The figures come from the same daily scrape as the spreadsheets in this\n"
        "download. They are a SNAPSHOT and do not update themselves - fetch again\n"
        "for a newer day.\n\n"
        "Search, region, usage and sort controls on the index work offline.\n"
    ).format(data_date.isoformat(), pages)
    with open(os.path.join(root, "README.txt"), "w", encoding="utf-8") as f:
        f.write(text)


def make_zip(bundle_dir: str, zip_path: str) -> str:
    """Zip ``bundle_dir`` atomically: build beside the target, then rename.

    A half-written zip must never be visible to the uploader, because it would
    be published as though it were complete.
    """
    tmp = zip_path + ".part"
    if os.path.exists(tmp):
        os.remove(tmp)
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _dirs, files in os.walk(bundle_dir):
            for name in files:
                full = os.path.join(folder, name)
                rel = os.path.relpath(full, bundle_dir)
                z.write(full, rel)
    os.replace(tmp, zip_path)
    return zip_path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Render the quota tracker as a static offline bundle.")
    p.add_argument("--out", required=True, help="directory to write the bundle into")
    p.add_argument("--zip", dest="zip_path", default=None,
                   help="also produce a zip at this path (default: <out>/" + ZIP_BASENAME + ")")
    p.add_argument("--no-zip", action="store_true", help="render only, do not zip")
    p.add_argument("--db-url", default=None)
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args(argv)

    try:
        stats = build(args.out, db_url=args.db_url, quiet=args.quiet)
    except Exception as exc:                       # noqa: BLE001 - reported, never raised on
        print("  Static site generation FAILED: {}: {}".format(type(exc).__name__, exc),
              file=sys.stderr)
        return 1

    if not args.no_zip:
        zip_path = args.zip_path or os.path.join(args.out, ZIP_BASENAME)
        try:
            make_zip(stats["dir"], zip_path)
            size = os.path.getsize(zip_path)
            if not args.quiet:
                print("  Static site zip: {} ({:,} bytes)".format(zip_path, size))
        except Exception as exc:                   # noqa: BLE001
            print("  Static site zip FAILED: {}: {}".format(type(exc).__name__, exc),
                  file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
