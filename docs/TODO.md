# EU Quota Scraper - TODO List

## Priority 1: Completed
- [x] Fix MEPS calculation formulas
- [x] Create dated output folders (YYYY-MM-DD)
- [x] Auto-detect quota period dates
- [x] Generate basic MEPS report

## Priority 2: Completed
- [x] Make EU output 100% match MEPS template
  - [x] Add slicers for Country and Quota Category (Fixed: Jan 2026 - using string-based XML manipulation)
  - [x] Match exact column widths and formatting
  - [x] Match header styles and colors
  - [x] Add explanatory text sections
  - [x] Preserve MEPS logo image

## Priority 3: UK Support (Completed)

### Research Completed (Jan 2026)

**UK Data Source Verified:**
- Website: UK Integrated Online Tariff (HMRC)
- URL: `https://www.trade-tariff.service.gov.uk/quota_search?order_number={ORDER_NUMBER}`
- Data updated: Daily (excluding weekends and bank holidays)
- Units: **Kilograms** (must convert to Tonnes for MEPS report)
- Order numbers: 6 digits starting with "058" (e.g., 058001, 058006)

**UK Categories (17 total):**
| Category | Name |
|----------|------|
| 1A | Non-alloy hot-rolled sheet |
| 1B | Other alloy hot-rolled sheet |
| 4 | Metallic coated sheet |
| 5 | Organic coated sheet |
| 6 | Tin mill products |
| 7 | Quarto plates |
| 12A | Alloy merchant bars |
| 12B | Non-alloy merchant bars |
| 13 | Rebar |
| 16 | Wire rod |
| 17 | Angles/shapes/sections |
| 19 | Railway material |
| 20 | Gas pipe |
| 21 | Hollow section |
| 25A | Large welded tube (1) |
| 25B | Large welded tube (2) |
| 26 | Other welded tube |

### 2026 Q1 Order Number Updates (Jan 2026)

**Invalid order numbers replaced:**
- `058003` (Category 1B) → `058110`, `058111`, `058112` (3 sub-quotas)
- `058019` (Rebars All others) → `058020`

**New individual country quotas for Rebars:**
- `058130` - Algeria*
- `058131` - Egypt*
- `058133` - New Zealand*
- `058134` - Norway*
- `058136` - Vietnam*

### Files Created/Updated

- [x] `src/uk_scraper.py` - Full implementation with order numbers reference (updated 2026-01-25)
- [x] `src/config.py` - UK_BASE_URL and UK_QUOTA_FIELDS added
- [x] `src/__init__.py` - UKQuotaScraper exported
- [x] `data/input/uk_quota_urls.xlsx` - Created with EU-matching format (updated 2026-01-25)
- [x] `dev/scripts/update_uk_input.py` - Script to regenerate UK input file

### Completed Tasks

- [x] UK input file created matching EU format exactly
- [x] UK scraper implementation complete
- [x] Excel generator handles UK data
- [x] All order numbers validated against UK website
- [x] Template quota limits fetched from live data

## Priority 4: Auto-Scheduling (Completed)

- [x] `daily_snapshot.py` — Entry point with file logging
- [x] `src/snapshot_scheduler.py` — Idempotent check + orchestration
- [x] `setup_scheduler.bat` — Task Scheduler registration (At log on, `pythonw`)
- [x] `remove_scheduler.bat` — Clean task removal
- [x] `src/utils.py` — Added `get_logs_folder()`, logs in `ensure_directories()`
- [x] Tested: first run scrapes, second run skips, logs written to `data/logs/`

## Priority 5: Prophet Time-Series Forecasting (Next)

- [ ] Accumulate 30+ daily snapshots (in progress — auto-collecting)
- [ ] Build Prophet model for quota depletion forecasting
- [ ] Generate depletion date predictions per quota
- [ ] Add forecasting visualizations

## Notes

- EU scraping: ~1-2 minutes for 189 quotas (fast HTTP)
- UK scraping: ~30 seconds for 73 quotas (API)
- Combined runtime: ~2-3 minutes

---
*Last updated: 18-Feb-2026*
