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

> **Superseded (1 July 2026):** The order numbers and category list below describe
> the old UK steel safeguard, which expired 30 June 2026. The current UK steel
> trade measure uses order numbers `058600`-`058671` (20 categories, Table 4 of
> the DBT notice) plus Category-1 authorised-use quotas `058673`/`058674`/`058675`
> — 75 quotas total. See `data/0702NewData/uk_quota_findings.md` and
> `UK_QUOTA_ORDER_NUMBERS` in `src/uk_scraper.py`. Section kept as a historical
> record of the completed work.

### Research Completed (Jan 2026)

**UK Data Source Verified:**
- Website: UK Integrated Online Tariff (HMRC)
- URL: `https://www.trade-tariff.service.gov.uk/quota_search?order_number={ORDER_NUMBER}`
- Data updated: Daily (excluding weekends and bank holidays)
- Units: **Kilograms** (must convert to Tonnes for MEPS report)
- Order numbers: 6 digits starting with "058" (e.g., 058001, 058006 — old safeguard; now 058600+)

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
- [x] `dev/scripts/update_uk_input.py` - Script to regenerate UK input file *(removed in v2.5.0; update the input workbook manually)*

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

## Priority 5: Prophet Time-Series Forecasting [EXPERIMENTAL]

> Forecasting lives in `beta/forecasting/` — a completely separate top-level
> directory with zero imports from/to `src/`. Changes in beta/ cannot break
> the main scraping + MEPS report pipeline.

### Phase 1: Data Loader (Completed — Feb 2026)

- [x] `beta/forecasting/data_loader.py` — 5 public functions
  - `load_all_snapshots()` — glob + merge + deduplicate snapshots
  - `get_quota_time_series()` — extract per-quota `{ds, y}` for Prophet
  - `get_all_quota_ids()` — list unique quota identifiers
  - `get_snapshot_summary()` — count, date range, `prophet_ready` flag
  - `prepare_prophet_df()` — add `cap`/`floor` for logistic growth
- [x] `beta/forecasting/__init__.py` — public API exports
- [x] `beta/tests/test_forecasting_data_loader.py` — 30 unit tests passing
- [x] `beta/requirements.txt` — separated from core requirements

### Phase 2: Preprocessing + Baseline Models (Pending)

- [ ] Accumulate 30+ daily snapshots **from the new regime** (restarted at the
      1 July 2026 regime boundary — 1/30 new-regime days as of 2026-07-06)
- [ ] `preprocessor.py` — rolling features, seasonality flags, outlier detection
- [ ] `simple_models.py` — naive, moving average, linear trend baselines
- [ ] **Regime boundary guard**: models must never train across 1 July 2026.
      The old safeguard (189 EU quotas) ended 30 June 2026; the new regime
      (283 EU quotas, different order numbers and volumes) started 1 July 2026.
      Pre-July and post-July series are different quota populations — filter
      snapshots to a single regime before fitting.

### Phase 3: Prophet Models (Pending)

- [ ] Build Prophet model for quota depletion forecasting
- [ ] Generate "days to exhaustion" predictions per quota
- [ ] Cross-validation and accuracy evaluation
- [ ] Add forecasting visualizations

### Current Snapshot Status

| Item | Value |
|------|-------|
| Snapshot days collected | 4 (3 old regime + 1 new regime) |
| Date range | 2026-01-24 → 2026-07-06 |
| Unique quotas | 472 (189 old regime + 283 new regime — do not mix) |
| Prophet ready | No (need 30+ new-regime days) |
| Est. ready date | ~early Aug 2026 |

## Priority 6: New-Regime Maintenance (Open)

The EU/UK quota systems changed on 1 July 2026 (EU: Regulation (EU) 2026/1384 +
Implementing Regulation (EU) 2026/1457; UK: steel trade measure under the
Taxation (Cross-Border Trade) Act 2018). Recurring/upcoming tasks:

- [ ] **1 Oct 2026 quarter turn**: update the `Current Quarter` column in
      `data/input/quota_urls.xlsx` and `data/input/uk_quota_urls.xlsx` to
      `2026-10-01`, and update the UK `Template Quota Limit` column to the
      Oct-Dec tonnages (`q2_oct_dec_t` in `data/0702NewData/uk_quotas.csv`).
      Repeat each quarter (`q3_jan_mar_t` on 1 Jan, `q4_apr_jun_t` on 1 Apr).
- [ ] **Jan 2027**: Implementing Regulation (EU) 2026/1457 defines the EU quotas
      only for 1 Jul - 31 Dec 2026; renewal expected January 2027. Check the new
      IR and update `data/input/quota_urls.xlsx` if order numbers/volumes change.
- [ ] Update `UK_QUOTA_ORDER_NUMBERS` in `src/uk_scraper.py` **only** if HMRC
      changes order numbers (they are not expected to rotate quarterly under the
      new measure).
- [ ] `beta/` forecasting: enforce the 1 July 2026 regime boundary before any
      Phase 2/3 training (see Priority 5).

## Notes

- EU scraping: ~1-2 minutes for 283 quotas (fast HTTP)
- UK scraping: ~30 seconds for 75 quotas (API)
- Combined runtime: ~2-3 minutes
- **Main pipeline focus**: Correct data + correct format in `meps_customer_template.xlsx`
- **Forecasting**: Experimental, completely independent of main pipeline

---
*Last updated: 06-Jul-2026*
