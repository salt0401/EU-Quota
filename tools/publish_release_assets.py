# -*- coding: utf-8 -*-
"""
Upload the published workbooks to the rolling 'latest-data' GitHub release.

This replaces the `gh release upload --clobber` step that ran in
.github/workflows/daily-quota-update.yml while the daily job lived on GitHub
Actions. The company server has no GitHub CLI installed and deliberately does
not get one -- see docs/SERVER_DEPLOYMENT.md -- so the same work is done here
against the REST API with `requests`, which is already a pinned dependency.

Semantics deliberately match the workflow step it replaces:

  * the release is created if it does not exist (make_latest=false, so it never
    displaces a real version tag),
  * an asset of the same name is deleted before re-upload, which is what
    `--clobber` did,
  * anything unexpected raises, so the caller exits non-zero and the scheduled
    task reports failure rather than silently publishing a stale workbook.

The token is read from a file, never from a command-line argument: arguments
are visible in the process list to every account on a shared machine.

Usage:
    python tools/publish_release_assets.py --token-file C:\\path\\to\\token
    python tools/publish_release_assets.py --token-file ... --dry-run
"""

import argparse
import io
import os
import re
import sys
import time
from datetime import datetime, timezone

import requests

DEFAULT_REPO = "salt0401/EU-Quota"
DEFAULT_TAG = "latest-data"
DEFAULT_PUBLISH_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "published")

RELEASE_NOTES = (
    "Rolling data release - assets are overwritten every day by the daily "
    "quota update. Use MEPS_Quota_Downloader.exe (or download.py) to fetch "
    "them."
)

API_ROOT = "https://api.github.com"
UPLOAD_ROOT = "https://uploads.github.com"
TIMEOUT = 120

# GitHub returns the expiry of a fine-grained PAT on every authenticated
# response. Without this check, an expired token first announces itself as a
# failed push the morning after it expires; with it, the daily log warns for
# two weeks beforehand.
EXPIRY_HEADER = "github-authentication-token-expiration"
EXPIRY_WARN_DAYS = 14


def read_token(token_file: str) -> str:
    """Read the PAT from a file. Whitespace-stripped; must be non-empty."""
    with io.open(token_file, "r", encoding="utf-8") as f:
        token = f.read().strip()
    if not token:
        raise RuntimeError(f"Token file {token_file} is empty.")
    return token


def make_session(token: str) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MEPS-EUQuota-Publisher",
    })
    return s


def _parse_expiry(raw: str):
    """Parse GitHub's expiry header. Returns an aware datetime, or None.

    Observed format is '2027-08-02 00:00:00 UTC'; ISO 8601 is accepted too so a
    format change upstream degrades to 'unknown' rather than to a crash.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S %Z", "%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:  # ISO with offset, e.g. '2027-08-02T00:00:00+00:00'
        parsed = datetime.fromisoformat(raw)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def check_token_expiry(session, warn_days: int = EXPIRY_WARN_DAYS):
    """Log how long the push token remains valid. Returns days left, or None.

    Never raises and never fails the run: a token that still works today must
    publish today's data even if this check cannot answer. A missing header is
    normal and means the token has no expiry (a classic PAT, or 'no expiration'
    on a fine-grained one) -- that is a security observation, not an error, so
    it is reported rather than warned about.
    """
    try:
        r = session.get(f"{API_ROOT}/rate_limit", timeout=30)
        raw = r.headers.get(EXPIRY_HEADER)
    except Exception as e:                       # noqa: BLE001 - never fatal
        print(f"  Token expiry: could not be checked ({e})")
        return None

    if not raw:
        print("  Token expiry: none set (the token does not expire)")
        return None

    expiry = _parse_expiry(raw)
    if expiry is None:
        print(f"  Token expiry: unrecognised format from GitHub ({raw!r})")
        return None

    days = (expiry - datetime.now(timezone.utc)).days
    stamp = expiry.strftime("%Y-%m-%d")
    if days < 0:
        print(f"  WARNING: the push token EXPIRED on {stamp}. "
              f"Re-issue it with tools/set-github-token.ps1.")
    elif days <= warn_days:
        print(f"  WARNING: the push token expires on {stamp}, in {days} day(s). "
              f"Re-issue it with tools/set-github-token.ps1 before then, or the "
              f"daily publish will start failing.")
    else:
        print(f"  Token expiry: {stamp} ({days} days away)")
    return days


def collect_assets(publish_dir: str) -> list:
    """The workbooks the downloader fetches from the release.

    Strictly year-named history workbooks only, mirroring the manifest rule in
    src/publisher.py: a stray copy (e.g. a OneDrive 'Quota_History_2026 (1).xlsx'
    conflict file) must not reach the release the downloader follows.
    """
    report = os.path.join(publish_dir, "MEPS_Quota_Update_latest.xlsx")
    paths = [report] if os.path.exists(report) else []
    paths += sorted(
        os.path.join(publish_dir, n) for n in os.listdir(publish_dir)
        if re.fullmatch(r"Quota_History_\d{4}\.xlsx", n))
    if not paths:
        raise RuntimeError(
            f"No workbooks found in {publish_dir}. Did run.py --publish "
            f"actually complete?")
    return paths


def get_release(session: requests.Session, repo: str, tag: str):
    r = session.get(f"{API_ROOT}/repos/{repo}/releases/tags/{tag}", timeout=TIMEOUT)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def create_release(session: requests.Session, repo: str, tag: str) -> dict:
    r = session.post(
        f"{API_ROOT}/repos/{repo}/releases",
        json={
            "tag_name": tag,
            "name": "Latest quota data",
            "body": RELEASE_NOTES,
            "make_latest": "false",
        },
        timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def delete_asset(session: requests.Session, repo: str, asset_id: int):
    r = session.delete(
        f"{API_ROOT}/repos/{repo}/releases/assets/{asset_id}", timeout=TIMEOUT)
    # 404 means someone else already removed it; that is the state we wanted.
    if r.status_code not in (204, 404):
        r.raise_for_status()


def upload_asset(session: requests.Session, repo: str, release_id: int,
                 path: str, retries: int = 3) -> dict:
    """Upload one file, retrying on transient transport failures.

    The retry is not defensive padding: this runs unattended once a day, and a
    single dropped connection would otherwise leave the release holding
    yesterday's workbook while today's metadata.json already names it.
    """
    name = os.path.basename(path)
    with io.open(path, "rb") as f:
        blob = f.read()
    last = None
    for attempt in range(1, retries + 1):
        try:
            r = session.post(
                f"{UPLOAD_ROOT}/repos/{repo}/releases/{release_id}/assets",
                params={"name": name},
                data=blob,
                headers={"Content-Type": "application/octet-stream"},
                timeout=TIMEOUT)
            r.raise_for_status()
            return r.json()
        except (requests.RequestException,) as e:
            last = e
            if attempt == retries:
                break
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Upload of {name} failed after {retries} attempts: {last}")


def publish_assets(repo: str, tag: str, token: str, paths: list,
                   dry_run: bool = False) -> dict:
    session = make_session(token)
    check_token_expiry(session)

    release = get_release(session, repo, tag)
    if release is None:
        if dry_run:
            print(f"  [dry-run] release '{tag}' does not exist; would create it")
            return {"created": True, "uploaded": [], "dry_run": True}
        print(f"  Release '{tag}' not found - creating it")
        release = create_release(session, repo, tag)

    existing = {a["name"]: a["id"] for a in release.get("assets", [])}
    uploaded = []
    for path in paths:
        name = os.path.basename(path)
        size_kb = os.path.getsize(path) / 1024.0
        if dry_run:
            verb = "replace" if name in existing else "add"
            print(f"  [dry-run] would {verb} {name} ({size_kb:.0f} KB)")
            continue
        if name in existing:
            delete_asset(session, repo, existing[name])
        upload_asset(session, repo, release["id"], path)
        print(f"  Uploaded {name} ({size_kb:.0f} KB)")
        uploaded.append(name)

    return {"created": False, "uploaded": uploaded, "dry_run": dry_run}


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Upload published workbooks to the rolling GitHub release.")
    parser.add_argument("--repo", default=DEFAULT_REPO,
                        help=f"owner/name (default: {DEFAULT_REPO})")
    parser.add_argument("--tag", default=DEFAULT_TAG,
                        help=f"release tag (default: {DEFAULT_TAG})")
    parser.add_argument("--publish-dir", default=DEFAULT_PUBLISH_DIR,
                        help="directory holding the workbooks")
    parser.add_argument("--token-file", required=True,
                        help="file containing the GitHub token (never pass the "
                             "token itself: arguments are visible in the "
                             "process list)")
    parser.add_argument("--assets", nargs="+", default=None,
                        help="upload exactly these files instead of the published "
                             "workbooks. Used by the daily task to publish the "
                             "offline dashboard bundle as a separate, non-fatal "
                             "step, so a failure there cannot disturb the data "
                             "upload that already succeeded.")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would be uploaded, change nothing")
    args = parser.parse_args(argv)

    if args.assets:
        missing = [a for a in args.assets if not os.path.exists(a)]
        if missing:
            raise RuntimeError("asset(s) not found: " + ", ".join(missing))
        paths = list(args.assets)
    else:
        paths = collect_assets(args.publish_dir)
    token = read_token(args.token_file)
    result = publish_assets(args.repo, args.tag, token, paths,
                            dry_run=args.dry_run)
    if args.dry_run:
        print("  Dry run complete - nothing was changed on the release.")
    else:
        print(f"  Release '{args.tag}' updated: {len(result['uploaded'])} asset(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
