# Changelog

All notable changes to the EU Quota Scraper project will be documented in this file.

## [2.4.0] - 2026-02-18

### Daily Auto-Snapshot for Prophet Forecasting

**New Files:**
- `src/snapshot_scheduler.py` — Core scheduling logic with idempotent daily check
- `daily_snapshot.py` — Entry point for Task Scheduler (runs silently via `pythonw`)
- `setup_scheduler.bat` — One-click Windows Task Scheduler registration (At log on)
- `remove_scheduler.bat` — Clean removal of the scheduled task

**How It Works:**
1. On every Windows login, Task Scheduler runs `pythonw daily_snapshot.py`
2. Checks `data/snapshots/` for `snapshot_YYYYMMDD_*.xlsx` matching today's date
3. If exists: logs "Already scraped today" and exits silently
4. If not: runs full EU + UK scraper pipeline, saves snapshot + log

**Key Functions:**
- `has_today_snapshot()` — Glob-based idempotency check
- `get_snapshot_count()` — Tracks progress toward 30+ days for Prophet training
- `run_daily_snapshot()` — Orchestrates check → scrape → result

**Changes to Existing Files:**
- `src/utils.py` — Added `get_logs_folder()`, included `"logs"` in `ensure_directories()`
- `.gitignore` — Added `data/logs/` exclusion

---

## [2.3.0] - 2026-01-25

### Performance Optimization - 5-10x Faster Scraping

**New Fast HTTP-based Scrapers:**
- Replaced Selenium browser automation with direct HTTP requests
- EU Scraper: Uses `requests` + `BeautifulSoup` for parsing server-rendered HTML
- UK Scraper: Uses official JSON API (`https://www.trade-tariff.service.gov.uk/uk/api/quotas/search`)

**Concurrent Processing:**
- Added `ThreadPoolExecutor` with 5 concurrent workers
- EU scraping: ~15 min → ~2-3 min (5-7x faster)
- UK scraping: ~5 min → ~30 sec (10x faster)

**Detection Avoidance:**
- Random delays between requests (EU: 0.3-0.8s, UK: 0.2-0.5s)
- Browser-like User-Agent headers
- Session reuse for connection efficiency

**Backup Files Created:**
- `src/scraper_selenium.py` - Original Selenium-based EU scraper
- `src/uk_scraper_selenium.py` - Original Selenium-based UK scraper
- Use these if any issues arise with the fast scrapers

**New Dependencies:**
- `requests>=2.28.0` - HTTP library
- `beautifulsoup4>=4.12.0` - HTML parsing
- `lxml>=4.9.0` - Fast XML/HTML parser

**EXE Compatibility:**
- New scrapers are fully compatible with PyInstaller packaging
- No browser drivers required - simpler distribution
- End users don't need Chrome installed

**Distribution Structure Changed:**
- EXE now builds to `dist/EU_Quota_Scraper/` subfolder
- Easier to zip and distribute - just zip the `EU_Quota_Scraper` folder
- Recipients unzip and see a clearly named folder

---

## [2.2.0] - 2026-01-25

### Project Reorganization

**Folder Structure Changes:**
- Moved `main.py` to `src/main.py`
- Moved `build_exe.py` to `build/build_exe.py`
- Moved `scripts/` to `dev/scripts/`
- Moved `backup_analysis/` to `dev/analysis/`
- Renamed `execution folder` to `dist_old_exe` (preserved old build)
- Created `run.py` as convenience entry point in project root

**New Folder Purpose:**
| Folder | Purpose |
|--------|---------|
| `src/` | Core application code - focus here for feature changes |
| `build/` | EXE packaging scripts - focus here for distribution settings |
| `dev/` | Development and debugging tools |
| `dist/` | Generated EXE distribution output |

### UK Quota Updates for 2026 Q1

**Invalid Order Numbers Replaced:**
- `058003` (Category 1B - All others) → `058110`, `058111`, `058112`
  - Old single quota of 579,165 tonnes split into 3 sub-quotas totaling ~533,590 tonnes
- `058019` (Category 13 - Rebars All others) → `058020`

**New Individual Country Quotas for Rebars:**
| Order Number | Country | Quota Limit (tonnes) |
|--------------|---------|---------------------|
| 058130 | Algeria* | 4,703 |
| 058131 | Egypt* | 3,195 |
| 058133 | New Zealand* | 4,703 |
| 058134 | Norway* | 4,703 |
| 058136 | Vietnam* | 4,703 |

**Files Updated:**
- `data/input/uk_quota_urls.xlsx` - Recreated with EU-matching format
- `src/uk_scraper.py` - Updated `UK_QUOTA_ORDER_NUMBERS` dictionary
- `dev/scripts/update_uk_input.py` - Created script for regenerating UK input file

**Files Deleted:**
- `data/input/uk_quota_urls_backup_20260125_040052.xlsx` - Outdated backup

### Documentation Updates

- Updated `README.md` and `README_繁體中文.md` with new project structure
- Updated `docs/ARCHITECTURE.md` with new folder layout and diagrams
- Updated `docs/INSTRUCTIONS.md` and `docs/INSTRUCTIONS_繁體中文.md`
- Updated `docs/TODO.md` - Marked UK support as completed
- Created `CHANGELOG.md` (this file)

### Input File Format Standardization

**UK input file now matches EU format:**
- Row 1: Base URL in column B
- Row 5: Headers with Excel Table
- Formula-based URL generation using `=CONCATENATE($B$1,TEXT(...))`
- Table named "Table2" for structured references

**UK Input Columns:**
| Column | Description |
|--------|-------------|
| Order Number | 6-digit UK quota order number |
| Quota Category | Steel product category |
| Country | Origin country (* indicates individual cap) |
| Current Quarter | Quarter start date (YYYY-MM-DD) |
| Template Quota Limit | Opening balance in tonnes |
| URL | Auto-generated from formula |

---

## [2.1.0] - 2026-01-23

### Added
- Interactive slicers for Quota Category and Country filtering
- UK scraper skeleton with order numbers reference
- String-based XML manipulation to preserve Excel slicers
- EXE build script using PyInstaller

### Fixed
- Slicer preservation when updating template
- MEPS formula calculations

---

## [2.0.0] - 2026-01-15

### Added
- EU TARIC quota scraper using Selenium
- MEPS-formatted Excel report generation
- Dated output folders (YYYY-MM-DD)
- Automatic quarter detection
- Template-based Excel generation preserving styling

### Features
- 189 EU quotas tracked
- MEPS logo and branding preserved
- Historical snapshots saved

---

## Version Numbering

- **Major version (X.0.0)**: Breaking changes or major feature additions
- **Minor version (0.X.0)**: New features, non-breaking changes
- **Patch version (0.0.X)**: Bug fixes, documentation updates

---

## How to Update UK Order Numbers

When UK quota order numbers change (typically at quarter boundaries):

1. Check validity of current order numbers:
   ```bash
   # Visit: https://www.trade-tariff.service.gov.uk/quota_search?order_number=058XXX
   ```

2. Update the `uk_quotas` list in `dev/scripts/update_uk_input.py`

3. Regenerate the input file:
   ```bash
   python dev/scripts/update_uk_input.py
   ```

4. Update `UK_QUOTA_ORDER_NUMBERS` in `src/uk_scraper.py`

5. Test the scraper:
   ```bash
   python run.py
   ```

---

## Data Sources

- **EU**: [TARIC Quota Database](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp)
- **UK**: [UK Integrated Online Tariff](https://www.trade-tariff.service.gov.uk/quota_search)
- **UK Trade Notices**: [GOV.UK Trade Remedies Notices](https://www.gov.uk/government/publications/trade-remedies-notices-tariff-rate-quotas-on-steel-goods)
