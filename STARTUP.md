# STARTUP — read this first (agent onboarding)

This file orients a fresh Claude Code session (or a developer) picking up this
repo on a new machine. Follow the steps in order; each has a check that proves
it worked before you move on.

---

## 1. What this project is (30-second orientation)

A pipeline that tracks **EU and UK steel import tariff-quota usage** and produces
a customer Excel report for MEPS. It runs in two halves:

- **Scraper half** (`src/`, `run.py`) — scrapes 283 EU quotas from the EU TARIC
  site and 75 UK quotas from the UK Trade Tariff API, then builds the MEPS report.
- **Automation half** — since August 2026 the **MEPS company server** runs the
  scraper every morning at 06:40 local and publishes results; colleagues run a
  tiny downloader exe to fetch them. Nobody runs the scraper by hand anymore.
  (It ran on GitHub Actions from July 2026 until the move.)

The repository is **public** on purpose — the downloader fetches data anonymously,
so it must stay public. Do not make it private.

Deeper detail lives in `README.md`, `docs/ARCHITECTURE.md`, the server runbook
`docs/SERVER_DEPLOYMENT.md`, and the pipeline runbook
`docs/DAILY_UPDATE_RUNBOOK.md`. Read those before changing behavior. What a
field *means* is documented in the code rather than in prose -- the MEPS
formulas at the top of `src/data_processor.py`, the published dataset's columns
in `HISTORY_COLUMNS` in `src/publisher.py` -- because the prose copy went out of
date within a day of a code change.

> **If you are working on the server rather than a laptop**, read
> `docs/SERVER_DEPLOYMENT.md` first, and the separate `meps-server-docs`
> repository for anything about the machine itself. The single thing that
> catches everyone: bare `python` and `py` on that box resolve to 3.13, not to
> this project's 3.12 — always call `venv\Scripts\python.exe` by full path.

---

## 2. Environment setup

Requirements: **Python 3.12** (developed on 3.12.10), git, and — only if you build
executables — PyInstaller. `gh` (GitHub CLI) is needed only for release/workflow work.

```bash
git clone https://github.com/salt0401/EU-Quota
cd EU-Quota
python -m venv .venv && . .venv/Scripts/activate    # Windows Git Bash; use .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
```

**Check:** `python -c "import pandas, bs4, openpyxl, requests, lxml; print('deps ok')"` prints `deps ok`.

### Windows / this-project quirks (important)

- **Always set `PYTHONUTF8=1`** when running Python that prints regulation text or
  writes CSV/XLSX. The console is often a non-UTF-8 codepage and will crash on
  characters like `Türkiye` / `–` otherwise. Example:
  `PYTHONUTF8=1 python run.py`.
- The repo often lives under **OneDrive**, which locks files mid-operation. The
  build scripts already handle this with a force-remove helper — don't "simplify"
  it away.
- Read files with UTF-8 explicitly (`io.open(path, encoding='utf-8')`); don't rely
  on the platform default.

---

## 3. Run the pipeline (no build needed)

```bash
PYTHONUTF8=1 python run.py             # scrape EU + UK, write report to data/output/<date>/
PYTHONUTF8=1 python run.py --skip-uk   # EU only
PYTHONUTF8=1 python run.py --publish    # also update data/published/ (what the daily server job does)
```

**Check:** a full run ends with `EU quotas scraped: 283` and `UK quotas scraped: 75`
and writes `data/output/<today>/MEPS_Quota_Update_<today>.xlsx`. Needs internet.

To fetch the already-published data instead of scraping (this is what colleagues do):

```bash
python download.py        # stdlib only — no dependencies required at all
```

---

## 4. Build the executables (the `.exe` is NOT in the repo)

`dist/` is gitignored, so a fresh clone has **no** exe — you rebuild from source.
Both build scripts live in `build/`.

### Downloader exe — what colleagues actually use

**You usually don't need to build it at all:** the latest exe is published on the
`latest-data` release —
<https://github.com/salt0401/EU-Quota/releases/download/latest-data/MEPS_Quota_Downloader.exe>
— and every installed copy **self-updates** on startup (it compares its version
against `downloader_version.txt` on the release and swaps itself in place; the
new version takes effect on the next run). CI rebuilds and republishes the exe
automatically whenever `download.py` changes on main
(`.github/workflows/build-downloader.yml`), so machines only ever need to obtain
the exe once. When bumping downloader behavior, bump `__version__` in
`download.py` or installed copies will not pick the change up.

To build locally anyway:

```bash
pip install pyinstaller
python build/build_downloader_exe.py
# -> dist/MEPS_Quota_Downloader.exe  (single file, ~7-8 MB)
```

`download.py` is standard-library only, so PyInstaller is the *only* extra install.

### The full scraper exe is gone

`build/build_exe.py` and `EU_Quota_Scraper.exe` were removed on 2026-09-02.
Nobody ran the scraper by hand once the daily server run existed, and the build
script had been sitting in `docs/archive/` while README and this file still told
you to run it. It is in git history if a local-scrape fallback is ever wanted.

**Check:** run the built downloader once.
`dist/MEPS_Quota_Downloader.exe --dest /tmp/x --no-pause` should print the
published data date and download 3 files.

---

## 5. Verify before you claim anything works

```bash
PYTHONUTF8=1 python -m pytest tests/ -q
```

**Check:** `222 passed` (this is the current baseline — if fewer, something regressed).
The same suite runs on the company server against Python 3.12.10 and gives the
same number; a divergence there is a portability bug, not a flaky test.
Run this before AND after any code change.

---

## 6. How the daily automation fits together

```
MEPS company server, Task Scheduler 06:40 local
  tools/server-daily-task.ps1 -Push
    -> venv\Scripts\python.exe run.py --publish
    -> data/published/quota_history_<YEAR>.csv + metadata.json  (committed to
       git; one history file per calendar year)
    -> MEPS_Quota_Update_latest.xlsx + Quota_History_<YEAR>.xlsx (uploaded to the
                                                            'latest-data' release,
                                                            NOT committed — keeps git small)
       ^ assets upload BEFORE the metadata commit is pushed, deliberately

Colleague: MEPS_Quota_Downloader.exe (download.py, self-updating)
    -> fetches csv/metadata from raw.githubusercontent.com and workbooks from the release
    -> on startup, checks downloader_version.txt on the release and replaces
       itself when CI has published a newer build

Still on GitHub Actions (both free on a public repo):
  build-downloader.yml         on any download.py change, a Windows runner
                               tests/builds/smoke-runs the exe and uploads it
                               + downloader_version.txt -> copies self-update
  data-freshness-watchdog.yml  09:00 UTC, asserts the committed metadata.json
                               names today; opens an issue if not. Deliberately
                               NOT on the server — a watchdog on the machine it
                               watches is not a watchdog
  daily-quota-update.yml       schedule disabled, workflow_dispatch kept as the
                               emergency fallback if the server is down
```

Key modules: `src/publisher.py` (writes `data/published/`), `download.py` (the
downloader; `__version__` + `self_update()`). Safety gates refuse to publish
garbage (mostly-failed scrapes, expired quota windows, UK-less datasets).
**When the daily run fails, read `docs/DAILY_UPDATE_RUNBOOK.md`** — it covers triage, quarterly maintenance, and the
January-2027 regulation renewal.

---

## 7. What's tracked vs generated

| In a fresh clone | NOT in a clone (gitignored / generated) |
|---|---|
| all `src/`, `run.py`, `download.py`, `build/` | `dist/` (both exes) |
| `data/input/` (the quota lists) + template | `data/output/`, `data/logs/`, `data/quota_tracker.db` |
| `data/published/quota_history_<YEAR>.csv` + `metadata.json` | `data/published/*.xlsx` (they're release assets) |
| all docs, tests, `requirements*.txt` | `__pycache__/`, `.venv/`, `*.spec` |

Reference extractions from the regulations are in `data/reference/regime-2026-07/`.

---

## 8. Open questions & future improvements

They do NOT live in this file — this file is onboarding only.

- `docs/TODO.md` — **the** open-items list. Only open work lives there; finished
  work is in `CHANGELOG.md` and git history.
- `docs/SESSION_LOG.md` — the current session handover: what is in flight, who is
  waiting on what, and the server rules. **Overwritten each handover**; the
  narrative of how the system was built lives in git history, not in a file.
- `docs/DAILY_UPDATE_RUNBOOK.md` — operational procedures (quarter turn,
  January-2027 regulation renewal, what the input workbooks must contain).

Nothing else. As of 2026-09-02 the roadmap does not also exist in
`FUTURE_IMPROVEMENTS.md`, a status page and an archive folder — those said
overlapping and drifting things about the same work, and are deleted. Parked
investigations, incident write-ups and anything about the server's security
posture are deliberately **outside** this repository, on the server under
`_notes\` and `_secrets\`.

---

## 9. Working conventions in this repo

- **Documentation is English only.** The Traditional Chinese README and
  instructions were removed in v2.10.2 (owner decision, 2026-08-02). Do not
  reintroduce translated docs — a second copy drifts out of date silently, and
  the stale half is worse than no translation.
- Match existing code style; the scraper/publisher/downloader are plain, dependency-light.
- Commit only when asked. Branch off `main` for non-trivial work. The daily server
  job pushes to `main` (as `meps-server-euquota`), so `git pull --rebase origin main`
  before pushing to avoid the race.
- If you change anything under `tools/`, remember the server holds its own clone:
  `git pull` there, or the next run uses the old script.
- Report test results honestly — quote the actual `pytest` line.
- If you change `download.py` behavior, **bump `__version__`** (and add a
  CHANGELOG entry) — otherwise installed exes see the same version and will
  not self-update, and CI republishes an exe nobody picks up.
