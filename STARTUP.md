# STARTUP — read this first (agent onboarding)

This file orients a fresh Claude Code session (or a developer) picking up this
repo on a new machine. Follow the steps in order; each has a check that proves
it worked before you move on.

---

## 1. What this project is (30-second orientation)

A pipeline that tracks **EU and UK steel import tariff-quota usage** and produces
a customer Excel report for MEPS. As of July 2026 it runs in two halves:

- **Scraper half** (`src/`, `run.py`) — scrapes 283 EU quotas from the EU TARIC
  site and 75 UK quotas from the UK Trade Tariff API, then builds the MEPS report.
- **Automation half** — GitHub Actions runs the scraper every day at 05:30 UTC and
  publishes results; colleagues run a tiny downloader exe to fetch them. Nobody
  runs the scraper by hand anymore.

The repository is **public** on purpose — the downloader fetches data anonymously,
so it must stay public. Do not make it private.

Deeper detail lives in `README.md`, `docs/ARCHITECTURE.md`,
`docs/DATA_FLOW_ANALYSIS.md`, and the operations runbook
`docs/DAILY_UPDATE_RUNBOOK.md`. Read those before changing behavior.

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
PYTHONUTF8=1 python run.py --publish    # also update data/published/ (what the daily CI job does)
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

### Full scraper exe — optional local fallback

```bash
pip install -r requirements.txt pyinstaller
python build/build_exe.py
# -> dist/EU_Quota_Scraper/EU_Quota_Scraper.exe  (folder bundle)
```

**Gotchas already baked into `build/build_exe.py`** (don't remove): it force-removes
OneDrive-locked temp dirs, and passes `--collect-submodules numpy` because
numpy >= 2.4 splits C-extension helpers into submodules PyInstaller's hook misses
(without it the frozen exe crashes at startup with `No module named
'numpy._core._exceptions'`).

**Check:** run the built exe once. `dist/MEPS_Quota_Downloader.exe --dest /tmp/x --no-pause`
should print the published data date and download 3 files. The scraper exe should
finish a live run with 0 failed quotas.

---

## 5. Verify before you claim anything works

```bash
PYTHONUTF8=1 python -m pytest tests/ -q
```

**Check:** `199 passed` (this is the current baseline — if fewer, something regressed).
Run this before AND after any code change.

---

## 6. How the daily automation fits together

```
GitHub Actions (.github/workflows/daily-quota-update.yml, 05:30 UTC, free on public repo)
  run.py --publish
    -> data/published/quota_history_<YEAR>.csv + metadata.json  (committed to
       git; one history file per calendar year)
    -> MEPS_Quota_Update_latest.xlsx + Quota_History_<YEAR>.xlsx (uploaded to the
                                                            'latest-data' release,
                                                            NOT committed — keeps git small)
Colleague: MEPS_Quota_Downloader.exe (download.py, self-updating)
    -> fetches csv/metadata from raw.githubusercontent.com and workbooks from the release
    -> on startup, checks downloader_version.txt on the release and replaces
       itself when CI has published a newer build

Second workflow (.github/workflows/build-downloader.yml): on any download.py
change on main, a Windows runner tests/builds/smoke-runs the exe and uploads it
+ downloader_version.txt to the same release -> installed copies self-update.
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
| `data/input/` (the quota lists) + template | `data/output/`, `data/snapshots/`, `data/logs/` |
| `data/published/quota_history_<YEAR>.csv` + `metadata.json` | `data/published/*.xlsx` (they're release assets) |
| all docs, tests, `requirements*.txt` | `__pycache__/`, `.venv/`, `*.spec` |

Reference extractions from the regulations are in `data/0702NewData/`.

---

## 8. Open questions & future improvements

They do NOT live in this file — this file is onboarding only. See
`FUTURE_IMPROVEMENTS.md` (repo root) for the tracked list with status and
decisions. Colleague-facing questions (e.g. the UK authorised-use quotas)
are flagged in `PROJECT_STATUS.html`; operational procedures (quarter turn,
January-2027 regulation renewal) are in `docs/DAILY_UPDATE_RUNBOOK.md`.

---

## 9. Working conventions in this repo

- Match existing code style; the scraper/publisher/downloader are plain, dependency-light.
- Commit only when asked. Branch off `main` for non-trivial work. The daily bot pushes
  to `main`, so `git pull --rebase origin main` before pushing to avoid the race.
- Report test results honestly — quote the actual `pytest` line.
- If you change `download.py` behavior, **bump `__version__`** (and add a
  CHANGELOG entry) — otherwise installed exes see the same version and will
  not self-update, and CI republishes an exe nobody picks up.
