# EU Quota Scraper v2.6

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
- **Daily auto-snapshot** on Windows login (Task Scheduler) with idempotent skip
- **283 EU quotas** and **75 UK quotas** tracked across multiple steel products and origin countries (new regimes effective 1 July 2026)

### Calculations (MEPS Formula)

```
Quota Limit = amount + transferred_amount
Balance Remaining = balance - awaiting_allocation
```

## Automated Daily Updates (GitHub Actions)

Since July 2026 the scraping runs automatically every morning (05:30 UTC) on
GitHub Actions — nobody needs to run the scraper by hand:

1. A GitHub-hosted runner scrapes all EU + UK quotas and generates the report
   (`.github/workflows/daily-quota-update.yml`).
2. The results are committed to `data/published/`:
   - `MEPS_Quota_Update_latest.xlsx` — latest customer report
   - `quota_history.csv` — one row per quota per day (the analysis dataset)
   - `Quota_History.xlsx` — the same history as a formatted workbook
   - `metadata.json` — timestamp and run summary
3. Colleagues run **`MEPS_Quota_Downloader.exe`** (a single small file, built
   from `download.py`), which fetches those files over public raw URLs.
   The repository must stay **public** — that way no token or login is needed.

Manual trigger: GitHub → Actions → "Daily quota update" → Run workflow.
Because the history grows daily, day-over-day quota movements can be analysed
directly from `quota_history.csv` / `Quota_History.xlsx`.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run scraper
python run.py              # Interactive mode (both EU and UK)
python run.py --skip-uk    # Scrape EU only
python run.py --publish    # Scrape + update data/published/ (what the daily CI run does)

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

Snapshots saved to `data/snapshots/` for historical analysis.

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
│   ├── snapshot_scheduler.py      # Daily auto-snapshot logic
│   └── utils.py                   # File/folder utilities
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
│   ├── 0702NewData/               # Reference data for the July 2026 regimes
│   ├── output/                    # Output by date
│   │   └── YYYY-MM-DD/            # Dated folders
│   ├── snapshots/                 # Historical snapshots
│   └── logs/                      # Daily auto-snapshot logs
│
├── templates/                     # TEMPLATES - Excel templates
│   ├── meps_customer_template.xlsx  # MEPS template with slicers
│   └── archive/                   # Old safeguard template (pre-July 2026)
│
├── docs/                          # DOCS - Documentation
│   ├── ARCHITECTURE.md            # System architecture
│   ├── INSTRUCTIONS.md            # English instructions
│   ├── INSTRUCTIONS_繁體中文.md    # Traditional Chinese instructions
│   └── TODO.md                    # Feature roadmap
│
├── beta/                          # EXPERIMENTAL - Forecasting (isolated from src/)
│   ├── forecasting/               # Prophet data loader + Phase 2 skeletons
│   └── tests/                     # Beta-only unit tests
│
├── tests/                         # Main pipeline unit tests
│
├── run.py                         # Convenience entry point
├── daily_snapshot.py              # Auto-snapshot entry point (Task Scheduler)
├── setup_scheduler.bat            # Register Windows Task Scheduler job
├── remove_scheduler.bat           # Remove the scheduled task
├── requirements.txt               # Dependencies
├── README.md                      # This file
└── README_繁體中文.md              # Chinese README
```

## Building EXE Distribution

Two executables can be built:

```bash
python build/build_downloader_exe.py   # MEPS_Quota_Downloader.exe (what colleagues use)
python build/build_exe.py              # EU_Quota_Scraper.exe (full local scraper, optional)
```

**To distribute the downloader (recommended):** send colleagues the single
file `dist/MEPS_Quota_Downloader.exe`. Double-clicking it downloads the
latest published data into `data/output/YYYY-MM-DD/` next to the EXE —
no scraping happens on their machine, so it finishes in seconds.

**The full scraper bundle** (`dist/EU_Quota_Scraper/`) is only needed if
someone must scrape locally, e.g. while GitHub is unreachable.

## Technical Notes

- **Order Number Format**: Automatically pads to 6 digits (e.g., `99801` → `099801`; EU order numbers are `0994xx`-`0999xx`, UK order numbers are `0586xx`)
- **Quarterly Periods**: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec); note the UK quota year runs 1 July - 30 June
- **Rate Limiting**: Random delays (EU: 0.3-0.8s, UK: 0.2-0.5s)
- **Expected Runtime**: ~2-3 minutes for all quotas (EU + UK)
- **Concurrent Workers**: 5 parallel requests for faster scraping

## Daily Auto-Snapshot (Windows)

Automatically collects a snapshot every time you log into Windows. Idempotent — skips if today's snapshot already exists.

```bash
# One-time setup (right-click → Run as Administrator)
setup_scheduler.bat

# Manual test
python daily_snapshot.py        # First run: full scrape (~2-3 min)
python daily_snapshot.py        # Second run: "Already scraped today", instant skip

# Remove scheduled task
remove_scheduler.bat
```

Logs saved to `data/logs/daily_YYYYMMDD.log`. After 30+ daily snapshots, the dataset is ready for Prophet time-series forecasting.

## Documentation

- [English Instructions](docs/INSTRUCTIONS.md)
- [繁體中文說明](docs/INSTRUCTIONS_繁體中文.md)
- [System Architecture](docs/ARCHITECTURE.md)

## Data Sources

- [EU TARIC Quota Database](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp)
- [UK Integrated Online Tariff](https://www.trade-tariff.service.gov.uk/quota_search)

---

*Version 2.6 - July 2026 (new EU/UK quota regimes effective 1 July 2026)*
