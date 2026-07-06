# Changelog

All notable changes to the EU Quota Scraper project will be documented in this file.

## [2.6.0] - 2026-07-06

### July 2026 Regime Migration — New EU/UK Quota Systems

The EU steel safeguard expired 30 June 2026. From 1 July 2026 the pipeline
tracks the EU's new quota system (Regulation (EU) 2026/1384 + Commission
Implementing Regulation (EU) 2026/1457) and the UK's steel trade measure
(implemented under the Taxation (Cross-Border Trade) Act 2018). Both systems
apply a **50% out-of-quota duty** and allocate quarterly on a
first-come-first-served basis.

**New Input Workbooks:**
- `data/input/quota_urls.xlsx` — 283 EU quotas: 30 product category codes
  (1.A/1.B … 28; codes 11 and 23 do not exist), order numbers in the
  `099491`–`099955` range, covering country-specific quotas (MFN + FTA parts
  under one order number), `FTA Quota - CSQ`, `Other countries`, and
  `FTA Quota - Other countries` residuals
- `data/input/uk_quota_urls.xlsx` — 75 UK quotas: Table 4 order numbers
  `058600`–`058671` (20 categories) plus Category-1 authorised-use quotas
  `058673`/`058674`/`058675` (published only on the UK Integrated Online Tariff)
- Old safeguard inputs archived in `data/input/archive/`
- Reference data extracted from the regulations lives in `data/0702NewData/`

**Scraper Parsing Fixes:**
- EU: validity-period parsing now matches the two DD-MM-YYYY dates directly,
  tolerating NBSP/newline separators on the new TARIC pages (`src/config.py`)
- EU: `Total awaiting allocation (indicative)` field captured correctly
- EU: origin strings stripped of stray whitespace
- Percentages written on the 0–1 scale so the template's Excel percent
  formatting displays correctly (was double-scaled)
- Failed scrapes are excluded from the customer report with a console warning
  (both EU and UK); the rows remain in the raw-data outputs

**UK Order Numbers:**
- `UK_QUOTA_ORDER_NUMBERS` in `src/uk_scraper.py` replaced with the new-regime
  dictionary (`058600`–`058675`; `058672` returns no data — the authorised-use
  quotas were verified live on the UK Integrated Online Tariff on 2026-07-06)

**Template Refresh (`templates/meps_customer_template.xlsx`):**
- 25% → 50% out-of-quota duty in the explanatory text
- Notes updated for the new EU/UK regimes
- Stale filter removed; cached values on the Instructions sheet refreshed
- Old safeguard template archived in `templates/archive/`

**Restored:**
- `build/build_exe.py` (removed in v2.5.0) restored; EXE rebuilt for the new
  regime

**Verification:**
- 163 tests passing
- Two full production runs: 283 EU + 75 UK quotas scraped, 0 failures ✓

---

## [2.5.0] - 2026-02-18

### Project Reorganization — Forecasting Isolation & Cleanup

Major structural reorganization to isolate experimental forecasting code from
the production pipeline and remove all unused files.

**Design Principle:**
The main pipeline (`src/` → scraping + MEPS Excel dashboard) must never be
affected by experimental forecasting work. All forecasting code now lives in
`beta/`, a completely separate top-level directory with zero imports from/to
`src/`.

**New Directory: `beta/`**

| File | Purpose |
|------|---------|
| `beta/__init__.py` | Package marker |
| `beta/README.md` | Status, usage, test instructions |
| `beta/requirements.txt` | Prophet + scipy (Phase 2+ only) |
| `beta/forecasting/__init__.py` | Public API exports |
| `beta/forecasting/data_loader.py` | Snapshot loading, Prophet-format prep (5 functions) |
| `beta/forecasting/preprocessor.py` | Phase 2 skeleton (feature engineering) |
| `beta/forecasting/simple_models.py` | Phase 2 skeleton (baseline models) |
| `beta/tests/__init__.py` | Test package marker |
| `beta/tests/test_forecasting_data_loader.py` | 30 unit tests |

**Files Moved (src/ → beta/):**
- `src/forecasting/__init__.py` → `beta/forecasting/__init__.py`
- `src/forecasting/data_loader.py` → `beta/forecasting/data_loader.py`
- `src/forecasting/preprocessor.py` → `beta/forecasting/preprocessor.py`
- `src/forecasting/simple_models.py` → `beta/forecasting/simple_models.py`
- `tests/test_forecasting_data_loader.py` → `beta/tests/test_forecasting_data_loader.py`
- `requirements-forecasting.txt` → `beta/requirements.txt`

**Key Code Change in data_loader.py:**
Replaced `from ..utils import get_snapshot_folder` (dependency on `src/`) with
a self-contained `_get_snapshot_folder()` that resolves the path independently:
```python
def _get_snapshot_folder() -> str:
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(project_root, "data", "snapshots")
```

**Files Deleted (no longer needed):**

| File / Directory | Reason |
|------------------|--------|
| `dev/` (entire directory) | Analysis scripts, comparison outputs — development-only |
| `build/build_exe.py` | EXE build script — `dist/` already contains the built EXE |
| `src/scraper_selenium.py` | Old Selenium EU scraper — replaced by fast HTTP in v2.3.0 |
| `src/uk_scraper_selenium.py` | Old Selenium UK scraper — replaced by API scraper in v2.3.0 |
| `src/forecasting/` | Moved to `beta/forecasting/` |

**Changes to Existing Files:**
- `src/__init__.py` — Removed all forecasting imports; kept version at `2.4.0`
- `src/utils.py` — Removed `get_forecasting_folder()` and its call in `ensure_directories()`
- `requirements.txt` — Removed `prophet` and `scipy` (now in `beta/requirements.txt`)
- `.gitignore` — Removed `build/` entries (directory deleted)
- `docs/ARCHITECTURE.md` — Updated to v2.3: new file tree, module boundary diagram, beta/ section
- `docs/TODO.md` — Updated all forecasting paths from `src/` to `beta/`, added snapshot status table

**Module Boundary:**
```
src/  (production)  ──writes──▶  data/snapshots/  ◀──reads──  beta/  (experimental)
```
The only shared touchpoint is `data/snapshots/`. No code dependency exists.

**Verification:**
- Main pipeline: `python run.py` — 189 EU + 73 UK quotas scraped, MEPS report generated ✓
- Main tests: 143 passed (19 pre-existing Selenium-era failures in test_scraper.py) ✓
- Beta tests: 30/30 passed ✓
- Cross-import: `import src` has no forecasting references, `from beta.forecasting import ...` works independently ✓

---

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
- `src/scraper_selenium.py` - Original Selenium-based EU scraper *(removed in v2.5.0)*
- `src/uk_scraper_selenium.py` - Original Selenium-based UK scraper *(removed in v2.5.0)*

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

## Quarterly Input Maintenance (from 1 July 2026)

Under the UK steel trade measure, order numbers (`058600`–`058675`) are not
expected to rotate at quarter boundaries. At each quarter turn:

1. Update the `Current Quarter` column in `data/input/quota_urls.xlsx` and
   `data/input/uk_quota_urls.xlsx` to the new quarter start date

2. Update the UK `Template Quota Limit` column to that quarter's tonnage
   (columns `q1_jul_sep_t`–`q4_apr_jun_t` in `data/0702NewData/uk_quotas.csv`)

3. Update `UK_QUOTA_ORDER_NUMBERS` in `src/uk_scraper.py` **only** if HMRC
   changes order numbers:
   ```bash
   # Verify at: https://www.trade-tariff.service.gov.uk/quota_search?order_number=058XXX
   ```

4. Test the scraper:
   ```bash
   python run.py
   ```

> **Note:** The `dev/scripts/update_uk_input.py` helper was removed in v2.5.0.
> Update the input Excel file manually or recreate a helper script as needed.

---

## Data Sources

- **EU**: [TARIC Quota Database](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp)
- **UK**: [UK Integrated Online Tariff](https://www.trade-tariff.service.gov.uk/quota_search)
- **UK Trade Notice**: [UK's steel trade measure from 1 July 2026 (DBT)](https://www.gov.uk/government/publications/uks-steel-trade-measure-from-1-july-2026/uks-steel-trade-measure-from-1-july-2026)
