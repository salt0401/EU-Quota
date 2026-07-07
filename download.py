# -*- coding: utf-8 -*-
"""
MEPS Quota Data Downloader

Downloads the latest quota data published by the daily GitHub Actions run.
No scraping happens here — a GitHub server scrapes the EU TARIC and UK
Trade Tariff sites every morning and commits the results to the public
repository; this program simply fetches those files.

Standard library only (no third-party packages), so the frozen EXE is a
small single file.

Usage:
    python download.py                # or double-click MEPS_Quota_Downloader.exe
    python download.py --dest FOLDER  # custom destination
    python download.py --no-pause     # don't wait for Enter at the end
"""

import argparse
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone

__version__ = "2.8.0"

REPO = "salt0401/EU-Quota"
BRANCH = "main"
BASE_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/data/published"
# Workbooks are published as rolling release assets (not committed to git,
# to keep the repository small); this URL is public and needs no login.
RELEASE_BASE = f"https://github.com/{REPO}/releases/download/latest-data"

# Self-update: CI rebuilds the exe whenever download.py changes on main and
# uploads it (plus this version marker) to the same rolling release.
UPDATE_VERSION_URL = f"{RELEASE_BASE}/downloader_version.txt"
UPDATE_EXE_URL = f"{RELEASE_BASE}/MEPS_Quota_Downloader.exe"
MIN_PLAUSIBLE_EXE_BYTES = 1_000_000  # a real PyInstaller exe is several MB

METADATA_FILE = "metadata.json"
DATA_FILES = [
    "MEPS_Quota_Update_latest.xlsx",
    "Quota_History.xlsx",
    "quota_history.csv",
]
FILE_SOURCES = {
    "MEPS_Quota_Update_latest.xlsx": RELEASE_BASE,
    "Quota_History.xlsx": RELEASE_BASE,
    "quota_history.csv": BASE_URL,
    METADATA_FILE: BASE_URL,
}

USER_AGENT = f"MEPS-Quota-Downloader/{__version__}"
TIMEOUT = 60
RETRIES = 3
STALE_AFTER_DAYS = 3   # weekend gap is fine; older than this gets a warning
CONSISTENCY_RETRY_WAIT = 30  # seconds; covers the raw CDN's cache window


def app_root() -> str:
    """Folder the program lives in (next to the EXE when frozen)."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def fetch(url: str) -> bytes:
    """Download a URL with retries. Raises the last error if all attempts fail.

    OSError covers URLError/HTTPError plus mid-transfer failures like
    ConnectionResetError and SSL errors; HTTPException covers IncompleteRead
    and BadStatusLine. 4xx client errors (except 429) are not retried —
    the file genuinely isn't there.
    """
    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                raise
            last_err = e
        except (OSError, http.client.HTTPException) as e:
            last_err = e
        if attempt < RETRIES:
            wait = 2 * attempt
            print(f"    attempt {attempt} failed ({last_err}); retrying in {wait}s...")
            time.sleep(wait)
    raise last_err


def _parse_version(s: str) -> tuple:
    return tuple(int(part) for part in s.strip().split("."))


def self_update() -> bool:
    """Replace this frozen exe with the latest released build, if newer.

    A running exe on Windows cannot be overwritten but CAN be renamed, so:
    download new -> rename running exe to *.old -> move new into place.
    The update takes effect on the NEXT run; the current run continues.
    Any failure just skips the update — it must never block data downloads.
    Returns True if an update was installed.
    """
    exe = sys.executable
    old = exe + ".old"
    if os.path.exists(old):  # leftover from a previous update
        try:
            os.remove(old)
        except OSError:
            pass

    if not getattr(sys, "frozen", False):
        return False  # running as a script: updates come via git, not here

    try:
        latest = fetch(UPDATE_VERSION_URL).decode("ascii").strip()
        if _parse_version(latest) <= _parse_version(__version__):
            return False
        print(f"\nA newer version of this program is available "
              f"({__version__} -> {latest}); updating...")
        payload = fetch(UPDATE_EXE_URL)
        if len(payload) < MIN_PLAUSIBLE_EXE_BYTES:
            print("  update skipped: downloaded file does not look like the program")
            return False
        tmp = exe + ".new"
        with open(tmp, "wb") as f:
            f.write(payload)
        os.replace(exe, old)
        os.replace(tmp, exe)
        print(f"  Updated to {latest} — takes effect the next time you run the program.")
        return True
    except Exception as e:
        print(f"  (update check skipped: {e})")
        return False


def check_freshness(metadata: dict) -> None:
    """Print a summary of the published data and warn if it looks stale."""
    data_date = metadata.get("data_date", "unknown")
    generated = metadata.get("generated_utc", "unknown")
    print(f"  Data date       : {data_date}")
    print(f"  Generated (UTC) : {generated}")
    print(f"  Quota period    : {metadata.get('quota_period', 'unknown')}")
    print(f"  EU quotas       : {metadata.get('eu_quotas', '?')} "
          f"({metadata.get('eu_failed', 0)} failed)")
    print(f"  UK quotas       : {metadata.get('uk_quotas', '?')} "
          f"({metadata.get('uk_failed', 0)} failed)")
    print(f"  History rows    : {metadata.get('history_rows', '?')}")

    try:
        age = (date.today() - datetime.strptime(data_date, "%Y-%m-%d").date()).days
        if age > STALE_AFTER_DAYS:
            print(f"\n  WARNING: the published data is {age} days old — the daily "
                  f"update may have stopped. Please report this.")
    except (ValueError, TypeError):
        pass
    if not metadata.get('eu_quotas') or not metadata.get('uk_quotas'):
        print("\n  WARNING: the last run published zero quotas for one region — "
              "the dataset is incomplete. Please report this.")
    failed = (metadata.get('eu_failed') or 0) + (metadata.get('uk_failed') or 0)
    if failed:
        print(f"\n  NOTE: {failed} quota(s) failed to scrape in the last run; "
              f"they are missing from the latest report.")


def run(dest: str = None, skip_update: bool = False) -> int:
    print("=" * 64)
    print(f"  MEPS Quota Data Downloader  v{__version__}")
    print(f"  Source: github.com/{REPO} (updated daily by GitHub Actions)")
    print("=" * 64)

    # 0. keep the program itself current (never blocks the data download)
    if not skip_update:
        self_update()

    # 1. metadata first — freshness check + confirms the source is reachable
    print("\nChecking published data...")
    try:
        metadata = json.loads(fetch(f"{BASE_URL}/{METADATA_FILE}").decode("utf-8"))
    except Exception as e:
        print(f"\nERROR: could not reach the data repository: {e}")
        print("Check your internet connection. If the connection is fine, the")
        print(f"repository may have moved — expected it at github.com/{REPO}")
        return 1
    check_freshness(metadata)

    # 2. download the data files into a dated folder
    if dest is None:
        dest = os.path.join(app_root(), "data", "output",
                            date.today().strftime("%Y-%m-%d"))
    os.makedirs(dest, exist_ok=True)
    print(f"\nDownloading to: {dest}")

    ok, failed = 0, 0
    csv_payload = None
    for name in DATA_FILES:
        try:
            print(f"  {name} ...", end=" ", flush=True)
            payload = fetch(f"{FILE_SOURCES[name]}/{name}")
            with open(os.path.join(dest, name), "wb") as f:
                f.write(payload)
            print(f"OK ({len(payload):,} bytes)")
            if name == "quota_history.csv":
                csv_payload = payload
            ok += 1
        except Exception as e:
            print(f"FAILED ({e})")
            failed += 1

    # Consistency check: the raw CDN caches for a few minutes, so metadata and
    # the CSV can briefly come from different daily commits. Retry once.
    if csv_payload is not None and metadata.get("history_rows"):
        csv_rows = max(csv_payload.count(b"\n") - 1, 0)
        if csv_rows != metadata["history_rows"]:
            print(f"\n  History row count ({csv_rows}) does not match metadata "
                  f"({metadata['history_rows']}) — the source may be mid-update; "
                  f"retrying in {CONSISTENCY_RETRY_WAIT}s...")
            time.sleep(CONSISTENCY_RETRY_WAIT)
            try:
                metadata = json.loads(fetch(f"{BASE_URL}/{METADATA_FILE}").decode("utf-8"))
                csv_payload = fetch(f"{FILE_SOURCES['quota_history.csv']}/quota_history.csv")
                with open(os.path.join(dest, "quota_history.csv"), "wb") as f:
                    f.write(csv_payload)
                csv_rows = max(csv_payload.count(b"\n") - 1, 0)
            except Exception as e:
                print(f"  retry failed: {e}")
            if csv_rows != metadata.get("history_rows"):
                print("  WARNING: files are still inconsistent — the daily update "
                      "is probably running right now. Re-run this program in a "
                      "few minutes.")
                failed += 1

    print(f"\nDone: {ok} file(s) downloaded" + (f", {failed} failed" if failed else ""))
    if ok:
        print(f"Open {os.path.join(dest, DATA_FILES[0])} for the latest report,")
        print(f"and {DATA_FILES[1]} for the day-by-day history.")
    return 0 if failed == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="Download the latest MEPS quota data from GitHub")
    parser.add_argument("--dest", help="Destination folder (default: data/output/YYYY-MM-DD next to the program)")
    parser.add_argument("--no-pause", action="store_true", help="Do not wait for Enter before exiting")
    parser.add_argument("--skip-update", action="store_true", help="Do not self-update even if a newer version exists")
    parser.add_argument("--version", action="version", version=f"MEPS Quota Data Downloader {__version__}")
    args = parser.parse_args()

    try:
        code = run(dest=args.dest, skip_update=args.skip_update)
    except KeyboardInterrupt:
        code = 130
    except Exception as e:
        # never let the console window vanish before the pause on double-click
        print(f"\nUNEXPECTED ERROR: {e}")
        code = 1

    if not args.no_pause and sys.stdin is not None and sys.stdin.isatty():
        try:
            input("\nPress Enter to exit...")
        except EOFError:
            pass
    sys.exit(code)


if __name__ == "__main__":
    main()
