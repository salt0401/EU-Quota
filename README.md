# EU Quota Scraper v2.4

Automated collection of EU steel tariff quota data from the European Commission's TARIC database.

## Overview

This tool scrapes quota usage data from the EU TARIC system to track steel import quotas. When quotas are exhausted, a **25% tariff** applies to additional imports.

### Key Features

- **Automated data collection** from EU TARIC quota pages
- **MEPS-formatted Excel reports** with interactive slicers and filters
- **Interactive slicers** for Quota Category and Country filtering
- **MEPS logo and branding** preserved in output
- **Automatic date detection** for quota periods
- **Dated output folders** (YYYY-MM-DD) for historical tracking
- **Daily auto-snapshot** on Windows login (Task Scheduler) with idempotent skip
- **189 EU quotas** tracked across multiple steel products and origin countries

### Calculations (MEPS Formula)

```
Quota Limit = amount + transferred_amount
Balance Remaining = balance - awaiting_allocation
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run scraper
python run.py              # Interactive mode (both EU and UK)
python run.py --skip-uk    # Scrape EU only
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
│   ├── scraper_selenium.py        # EU Selenium scraper (backup)
│   ├── uk_scraper.py              # UK API scraper (fast)
│   ├── uk_scraper_selenium.py     # UK Selenium scraper (backup)
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
│   │   ├── quota_urls.xlsx        # EU quota list to track
│   │   └── uk_quota_urls.xlsx     # UK quota list to track
│   ├── output/                    # Output by date
│   │   └── YYYY-MM-DD/            # Dated folders
│   ├── snapshots/                 # Historical snapshots
│   └── logs/                      # Daily auto-snapshot logs
│
├── templates/                     # TEMPLATES - Excel templates
│   └── meps_customer_template.xlsx  # MEPS template with slicers
│
├── docs/                          # DOCS - Documentation
│   ├── ARCHITECTURE.md            # System architecture
│   ├── INSTRUCTIONS.md            # English instructions
│   ├── INSTRUCTIONS_繁體中文.md    # Traditional Chinese instructions
│   └── TODO.md                    # Feature roadmap
│
├── dev/                           # DEV TOOLS - Development utilities
│   ├── scripts/                   # Utility scripts
│   └── analysis/                  # Analysis and debugging tools
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

To create a standalone EXE package for distribution:

```bash
python build/build_exe.py
```

The distribution package will be created in `dist/EU_Quota_Scraper/` folder.

**To distribute:**
1. Run the build script
2. Zip the `EU_Quota_Scraper` folder inside `dist/`
3. Send the zip file to users
4. Users unzip and double-click `EU_Quota_Scraper.exe`

## Technical Notes

- **Order Number Format**: Automatically pads to 6 digits (e.g., `98967` → `098967`)
- **Quarterly Periods**: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec)
- **Rate Limiting**: Random delays (EU: 0.3-0.8s, UK: 0.2-0.5s)
- **Expected Runtime**: ~1-2 minutes for all quotas (EU + UK)
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

## Data Source

[EU TARIC Quota Database](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp)

---

*Version 2.4 - February 2026 (Daily auto-snapshot with Windows Task Scheduler)*
