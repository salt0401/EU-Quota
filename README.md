# EU Quota Scraper v2.10

Automated collection of EU and UK steel tariff quota data from the European Commission's TARIC database and the UK Integrated Online Tariff.

## Overview

This tool scrapes quota usage data from the EU TARIC system to track steel import quotas. When quotas are exhausted, a **50% tariff** applies to additional imports (Regulation (EU) 2026/1384, effective 1 July 2026). UK quotas are tracked from the UK Integrated Online Tariff under the UK's steel trade measure (also effective 1 July 2026, also with a 50% out-of-quota duty).

### Key Features

- **Automated data collection** from EU TARIC quota pages
- **MEPS-formatted Excel reports** with interactive slicers and filters
- **Interactive slicers** for Quota Category and Country filtering
- **MEPS logo and branding** preserved in output
- **Automatic date detection** for quota periods
- **Dated output folders** (YYYY-MM-DD) for historical tracking
- **Unattended daily run** on the MEPS company server, publishing back to GitHub
- **283 EU quotas** and **75 UK quotas** tracked across multiple steel products and origin countries (new regimes effective 1 July 2026)

### Calculations (MEPS Formula)

```
Quota Limit = amount + transferred_amount
Balance Remaining = balance - awaiting_allocation
```

## Automated Daily Updates (MEPS company server)

Since August 2026 the scraping runs automatically every morning on the **MEPS
company server**, scheduled task **MEPS EU Quota Daily Update** at 06:40
local — nobody needs to run the scraper by hand. It ran on
GitHub Actions from July 2026 until the move; see
[docs/SERVER_DEPLOYMENT.md](docs/SERVER_DEPLOYMENT.md).

**Nothing changed for colleagues.** The output goes to the same repository and
the same `latest-data` release, so every installed `MEPS_Quota_Downloader.exe`
keeps working untouched.

1. The server scrapes all EU + UK quotas and generates the report
   (`tools/server-daily-task.ps1` → `run.py --publish`).
2. The results are published in two places:
   - committed to `data/published/`: `quota_history_<YEAR>.csv` (one row per
     quota per day, one file per calendar year — the analysis dataset) and
     `metadata.json` (run summary + file manifest)
   - uploaded to the rolling **latest-data** release:
     `MEPS_Quota_Update_latest.xlsx` (latest customer report) and
     `Quota_History_<YEAR>.xlsx` (the history as a formatted workbook, one per
     year) — kept out
     of git so daily workbook blobs don't grow the repository
3. Colleagues run **`MEPS_Quota_Downloader.exe`** (a single small file, built
   from `download.py`), which fetches those files over public raw URLs.
   The repository must stay **public** — that way no token or login is needed.

Because the history grows daily, day-over-day quota movements can be analysed
directly from `quota_history_<YEAR>.csv` / `Quota_History_<YEAR>.xlsx`
(one file per year — this is a long-lived project).

**Manual trigger** (on the server):

```powershell
powershell -ExecutionPolicy Bypass -File C:\DataScienceProject\EUQuota\tools\server-daily-task.ps1 -Push
```

Drop `-Push` to scrape without publishing anything — the safe way to test.

**Monitoring.** Nothing on the server notices a scheduled task that never fires,
so `.github/workflows/data-freshness-watchdog.yml` runs *on GitHub* every
morning and opens an issue if the published data is not current.

**Emergency fallback.** The old GitHub Actions job still exists with its
schedule disabled: Actions → "Daily quota update" → Run workflow. Only use it
when the server task is confirmed not running — two hosts publishing the same
day race on push.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run scraper
python run.py              # Interactive mode (both EU and UK)
python run.py --skip-uk    # Scrape EU only
python run.py --publish    # Scrape + update data/published/ (what the daily server run does)

# Download the latest published data (what colleagues' EXE does)
python download.py
```

## Output Files

Files are organized by date in `data/output/YYYY-MM-DD/`:

| File | Description |
|------|-------------|
| `eu_quota_raw_YYYYMMDD.xlsx` | Complete scraped data |
| `uk_quota_raw_YYYYMMDD.xlsx` | UK quota data |
| `MEPS_Quota_Update_YYYYMMDD.xlsx` | Customer-ready report |

The permanent historical record is `data/published/quota_history_<YEAR>.csv` —
one row per quota per day, appended by every run and committed to git.

### Customer Report Columns

| Column | Description |
|--------|-------------|
| Quota Category | Steel product type |
| Country | Country of origin |
| Quota Limit (Tonnes) | Total available quota |
| Quota Allocated (Tonnes) | Amount used |
| % Quota Allocated | Usage percentage |
| Balance Remaining (Tonnes) | Remaining quota |
| % Balance Remaining | Remaining percentage |

## Project Structure

```
EU Quota/
├── src/                           # MAIN PROJECT - Core source code
│   ├── __init__.py                # Package exports
│   ├── main.py                    # Main entry point
│   ├── config.py                  # Configuration & quarter utilities
│   ├── scraper.py                 # EU HTTP scraper (fast)
│   ├── uk_scraper.py              # UK API scraper (fast)
│   ├── data_processor.py          # Data calculations (MEPS formulas)
│   ├── excel_generator.py         # MEPS report generator (preserves slicers)
│   ├── publisher.py               # Writes data/published/ (history + metadata)
│   └── utils.py                   # File/folder utilities
│
├── tools/                         # SERVER OPS - company-server deployment only
│   ├── server-daily-task.ps1      # Task Scheduler entry point (see docs/SERVER_DEPLOYMENT.md)
│   ├── publish_release_assets.py  # Uploads workbooks to the GitHub release
│   └── git-askpass.cmd            # Feeds the push token to git without exposing it
│
├── build/                         # BUILD EXE - Packaging scripts
│   └── build_exe.py               # PyInstaller build script
│
├── dist/                          # Distribution output
│   └── EU_Quota_Scraper/          # Ready-to-zip folder for distribution
│
├── data/                          # DATA - Runtime data
│   ├── input/                     # Input files
│   │   ├── quota_urls.xlsx        # EU quota list to track (283 quotas)
│   │   ├── uk_quota_urls.xlsx     # UK quota list to track (75 quotas)
│   │   └── archive/               # Old safeguard inputs (pre-July 2026)
│   ├── reference/                 # Source material, not runtime inputs
│   │   └── regime-2026-07/        # Extracts from the July 2026 regulations
│   ├── output/                    # Output by date
│   │   └── YYYY-MM-DD/            # Dated folders
│   ├── published/                 # What the downloader fetches (history + metadata)
│   └── logs/                      # Daily server-run logs
│
├── templates/                     # TEMPLATES - Excel templates
│   ├── meps_customer_template.xlsx  # MEPS template with slicers
│   └── archive/                   # Old safeguard template (pre-July 2026)
│
├── docs/                          # DOCS - Documentation
│   ├── ARCHITECTURE.md            # System architecture
│   ├── INSTRUCTIONS.md            # English instructions
│   └── TODO.md                    # Feature roadmap
│
├── beta/                          # EXPERIMENTAL - Forecasting (isolated from src/)
│   ├── forecasting/               # Prophet data loader + Phase 2 skeletons
│   └── tests/                     # Beta-only unit tests
│
├── tests/                         # Main pipeline unit tests
│
├── run.py                         # Convenience entry point
├── download.py                    # Colleague-facing downloader (stdlib only)
├── requirements.txt               # Dependencies (local dev, incl. Selenium fallback)
├── requirements-ci.txt            # Pinned deps for the daily unattended run
└── README.md                      # This file
```

## Building EXE Distribution

Two executables can be built:

```bash
python build/build_downloader_exe.py   # MEPS_Quota_Downloader.exe (what colleagues use)
python build/build_exe.py              # EU_Quota_Scraper.exe (full local scraper, optional)
```

**To distribute the downloader (recommended):** colleagues grab the single
file once from the [latest-data release](https://github.com/salt0401/EU-Quota/releases/tag/latest-data)
(or you send it to them). Double-clicking it downloads the latest published
data into `data/output/YYYY-MM-DD/` next to the EXE — no scraping happens on
their machine, so it finishes in seconds. The exe **self-updates**: on startup
it checks `downloader_version.txt` on the release and replaces itself when CI
has published a newer build (`.github/workflows/build-downloader.yml` rebuilds
it on every `download.py` change), so distribution is one-time.

**The full scraper bundle** (`dist/EU_Quota_Scraper/`) is only needed if
someone must scrape locally, e.g. while GitHub is unreachable.

## Technical Notes

- **Order Number Format**: Automatically pads to 6 digits (e.g., `99801` → `099801`; EU order numbers are `0994xx`-`0999xx`, UK order numbers are `0586xx`)
- **Quarterly Periods**: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec); note the UK quota year runs 1 July - 30 June
- **Rate Limiting**: Random delays (EU: 0.3-0.8s, UK: 0.2-0.5s)
- **Expected Runtime**: ~2-3 minutes for all quotas (EU + UK)
- **Concurrent Workers**: 5 parallel requests for faster scraping

## Documentation

- [Server deployment & runbook](docs/SERVER_DEPLOYMENT.md) — how the daily run works on the company server
- [Daily update runbook](docs/DAILY_UPDATE_RUNBOOK.md) — triage when a run fails
- [English Instructions](docs/INSTRUCTIONS.md)
- [System Architecture](docs/ARCHITECTURE.md)

> **Removed in v2.10.0:** the login-triggered auto-snapshot (`daily_snapshot.py`,
> `src/snapshot_scheduler.py`, `setup_scheduler.bat`, `remove_scheduler.bat`).
> It predated the automated daily publish and collected snapshots only when
> somebody signed into Windows — which never happens on an unattended server.
> The per-day history in `data/published/quota_history_<YEAR>.csv` supersedes it
> and is strictly more complete.

## Data Sources

- [EU TARIC Quota Database](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp)
- [UK Integrated Online Tariff](https://www.trade-tariff.service.gov.uk/quota_search)

---

*Version 2.10 - August 2026 (daily run on the MEPS company server; EU/UK quota regimes effective 1 July 2026)*
