# EU Quota Project - Data Flow Analysis

## Overview

This document describes how data flows from input sources through the scraping system to the final customer-facing MEPS Excel report.

> **July 2026 regime migration:** The old EU/UK steel safeguard ended on 30 June 2026.
> From 1 July 2026 the pipeline tracks the replacement measures — EU: Regulation (EU)
> 2026/1384 + Implementing Regulation (EU) 2026/1457 (283 quotas, order numbers
> 099491–099955, 50% out-of-quota duty); UK: DBT's steel trade measure under the
> Taxation (Cross-Border Trade) Act 2018 (75 quotas, order numbers 058600–058671
> plus authorised-use 058673–058675, 50% out-of-quota duty). The flow below is
> unchanged in shape; the input workbooks carry the new order numbers, and the
> pre-July-2026 safeguard inputs and template are archived in `data/input/archive/`
> and `templates/archive/`.

---

## 1. INPUT DATA

### File: `data/input/quota_urls.xlsx`

| Column | Description | Example |
|--------|-------------|---------|
| Order Number | EU quota order number | 099801 |
| Quota Category | Steel product category | Non Alloy and Other Alloy Hot Rolled Sheets and Strips - 1.A |
| Country | Annex I allocation name | Türkiye, India, Korea, Republic of |
| Current Quarter | Quarter start date | 2026-07-01 |
| URL | Link to EU TARIC page | https://ec.europa.eu/taxation_customs/dds2/taric/... |

**Total quotas tracked:** 283 EU quotas

A companion file `data/input/uk_quota_urls.xlsx` (75 UK quotas, order numbers
058600–058675) has the same layout plus a `Template Quota Limit` column holding the
current quarter's tonnage. Pre-July-2026 safeguard inputs are archived in
`data/input/archive/`.

---

## 2. WEB SCRAPING (EU TARIC Database)

### Source URL Pattern
```
https://ec.europa.eu/taxation_customs/dds2/taric/quota_tariff_details.jsp
  ?Lang=en
  &StartDate={YYYY-MM-DD}
  &Code={order_number}
```

### Fields Extracted from Website

| Field | Type | Description |
|-------|------|-------------|
| order_number | string | Quota identifier |
| validity_period | string | "01-07-2026 - 30-09-2026" |
| origin | string | Country/region of origin |
| initial_amount | float | Initial quota amount (kg) |
| amount | float | Current quota amount (kg) |
| balance | float | Remaining balance (kg) |
| transferred_amount | float | Rolled over from previous quarter |
| exhaustion_date | date | When quota was exhausted (if applicable) |
| critical | boolean | Whether quota is critical |
| last_import_date | date | Last import recorded |
| last_allocation_date | date | Last allocation made |
| awaiting_allocation | float | Pending allocation amount |
| blocking_period | string | Any blocking periods |
| suspension_period | string | Any suspension periods |
| allocation_pct | float | Last allocation percentage |
| associated_taric_code | string | HS tariff codes (multi-line) |

### Derived Fields (Calculated by `data_processor.py`)

| Field | Formula | Description |
|-------|---------|-------------|
| validity_start | regex-matched DD-MM-YYYY dates in validity_period | Quarter start |
| validity_end | regex-matched DD-MM-YYYY dates in validity_period | Quarter end |
| quota_limit | amount + transferred_amount | MEPS Quota Limit |
| balance_remaining | balance - awaiting_allocation (floored at 0) | MEPS Balance Remaining |
| quota_allocated | quota_limit - balance_remaining | Tonnage used |
| pct_allocated | (quota_allocated / quota_limit) * 100 | Usage percentage (internal 0-100 scale) |
| pct_remaining | (balance_remaining / quota_limit) * 100 | Remaining percentage (internal 0-100 scale) |
| days_remaining | validity_end - today | Days until quarter ends |
| daily_burn_rate | quota_allocated / days_elapsed | Daily usage rate |
| est_days_to_exhaustion | balance_remaining / daily_burn_rate | Estimated exhaustion |

Validity dates are extracted by regex (the two `DD-MM-YYYY` dates are matched
directly), so the parser tolerates whatever separator TARIC renders between them
(spaces, NBSP, newlines).

---

## 3. OUTPUT FILES

### 3.1 Raw Scraping Output
**Files:** `data/output/YYYY-MM-DD/eu_quota_raw_YYYYMMDD.xlsx` and `uk_quota_raw_YYYYMMDD.xlsx`

Contains all scraped fields plus input data and calculated metrics. Rows whose
scrape failed remain here, flagged `scrape_status = failed`.

### 3.2 Customer Report
**File:** `data/output/YYYY-MM-DD/MEPS_Quota_Update_YYYYMMDD.xlsx`

Simplified view with selected columns for customer delivery, generated
automatically from the MEPS template (EU and UK sheets). Failed scrapes are
excluded from this report, with a console warning listing the affected order
numbers.

### 3.3 Historical Snapshot
**File:** `data/snapshots/snapshot_YYYYMMDD_HHMMSS.xlsx`

Timestamped snapshot for trend analysis.

---

## 4. CUSTOMER TEMPLATE (MEPS Format)

### File: `templates/meps_customer_template.xlsx`

### Sheet Structure

```
Sheet 1: Instructions
├── Title: "MEPS Quota Update - <Month Year>" (auto-updated at generation)
├── Overview of the EU and UK quota systems
├── Notes on source data
└── Instructions for using slicers/filters

Sheet 2: European Union
├── Header info (quota period, last update date)
├── Explanatory notes about policy changes
├── Interactive Slicers (Country, Quota Category)
└── Data Table (EU_Quotas4)

Sheet 3: United Kingdom
├── Same structure as EU sheet
└── Data Table (UK_Quotas)
```

### Table Columns in Customer Template

| Column | Source | Calculation |
|--------|--------|-------------|
| Quota Category | input_quota_category | Direct mapping |
| Country | input Country column (Annex I allocation names; falls back to scraped origin) | Direct mapping |
| Quota Limit (Tonnes) | **amount + transferred_amount** | Calculated |
| Quota Allocated (Tonnes) | quota_allocated (quota_limit - balance_remaining) | Calculated |
| % Quota Allocated | pct_allocated | 0-1 fraction, Excel '0%' format |
| Balance Remaining (Tonnes) | **balance - awaiting_allocation** | Calculated |
| % Balance Remaining | pct_remaining (balance_remaining / quota_limit) | 0-1 fraction, Excel '0%' format |

Percentages are converted from the internal 0-100 scale to 0-1 fractions in
`prepare_customer_data` and written as-is for Excel's `'0%'` number format.

---

## 5. CRITICAL DATA MAPPING

### From `detail_reference.png`:

```
SCRAPED DATA → CUSTOMER REPORT

amount + transferred_amount = Quota Limit
balance - awaiting_allocation = Balance Remaining

(Left side = source data, Right side = published information)
```

### Status: implemented
`data_processor.py` implements the MEPS formulas directly:

| MEPS Column | Code |
|-------------|------|
| Quota Limit | `quota_limit = amount + transferred_amount` |
| Balance Remaining | `balance_remaining = balance - awaiting_allocation` (floored at 0) |
| Quota Allocated | `quota_allocated = quota_limit - balance_remaining` |

---

## 6. INTERACTIVE ELEMENTS IN MEPS TEMPLATE

### Slicers (Interactive Filters)
- **Country Slicer**: 2-column layout, filter by country
- **Quota Category Slicer**: Filter by product category
- Multiple selection supported (Ctrl+click)
- Clear filter buttons included

### Excel Tables
- `EU_Quotas4`: European Union data (header row 15; table ref resized at generation to the row count — 283 EU rows → A15:G298)
- `UK_Quotas`: United Kingdom data (header row 15; 75 UK rows → A15:G90)
- Features: Auto-filter headers, row stripes, header styling

### Sheet Protection
- Instructions sheet is protected (read-only)
- Data sheets allow sorting/filtering

### Formulas
- Instructions sheet pulls dates from data sheets:
  - `'European Union'!A2` → Current quota period
  - `'European Union'!A3` → Latest available data
- The formulas' cached values (stored in sheet1.xml) are patched at generation
  time, so previewers that don't recalculate on load (LibreOffice, pandas) still
  show the fresh dates; `fullCalcOnLoad` is also set for Excel

### Hyperlinks
- Links to EU TARIC consultation page
- Links to UK Integrated Online Tariff

---

## 7. AUTOMATED vs MANUAL CONTENT

### Automated (From Scraping)
- All quota data values
- Percentage calculations
- Order numbers and categories
- Country information (from the input file's Annex I allocation names)
- Balance and allocation figures
- "Current quota period" / "Latest available data" banners (extracted from
  scraped validity periods and scrape timestamps)
- **UK data** (`src/uk_scraper.py`, UK Trade Tariff JSON API)

### Manual (Analyst Input Required)
- Explanatory notes about policy changes
- Special annotations
- Quarterly input maintenance: at each quarter turn, update the "Current Quarter"
  column in both input workbooks and the UK "Template Quota Limit" column to that
  quarter's tonnage

---

## 8. DATA REFRESH WORKFLOW

```
1. Update input files with any new quotas
         ↓
2. Run scraper (run.py / src/main.py)
         ↓
3. Raw data saved to output/
         ↓
4. Snapshot saved to snapshots/
         ↓
5. MEPS report generated from template
   (data, tables, and period dates auto-filled)
         ↓
6. [MANUAL] Review; add analyst notes if needed
         ↓
7. Deliver to customer
```

---

## 9. KEY OBSERVATIONS FOR REBUILD

1. **Calculation Mismatch** *(resolved)*: `data_processor.py` now uses `amount + transferred_amount` for Quota Limit

2. **Missing Field** *(resolved)*: `balance - awaiting_allocation` is calculated for Balance Remaining (floored at 0)

3. **UK Data Gap** *(resolved)*: `src/uk_scraper.py` scrapes UK quotas via the UK Trade Tariff JSON API

4. **Manual Steps** *(mostly resolved)*: Dates are auto-filled at generation; analyst notes remain manual

5. **Slicer Dependency**: Interactive features rely on Excel table structure

6. **Units**: All values stored in kg but displayed as Tonnes (divide by 1000)

## 10. PUBLISHED DATA & DISTRIBUTION (July 2026)

The daily GitHub Actions run (`run.py --publish`) adds a final stage after
report generation (`src/publisher.py`):

| Output | Location | Purpose |
|--------|----------|---------|
| `quota_history_<YEAR>.csv` | `data/published/` (git) | One row per quota per day, one file per calendar year: date, region, order_number, category, country, tonnes, percentages, awaiting allocation (EU), quota window (validity start/end), status (UK), scrape_status. The analysis dataset. |
| `metadata.json` | `data/published/` (git) | Timestamp, data date, quota period, row/failure counts - the downloader's freshness check. |
| `MEPS_Quota_Update_latest.xlsx` | `latest-data` release asset | Latest customer report (overwritten daily; kept out of git). |
| `Quota_History_<YEAR>.xlsx` | `latest-data` release asset | The year's history CSV as a formatted workbook (EU/UK sheets, autofilter); past years stay frozen on the release. |

History updates are idempotent per (date, region): a re-run replaces that
date's rows for the regions it scraped and preserves the rest. Publish gates
refuse mostly-failed scrapes, expired EU quota windows, and UK-less datasets.

The `latest-data` release also carries the downloader itself —
`MEPS_Quota_Downloader.exe` and `downloader_version.txt` — published not by the
daily run but by a separate workflow (`.github/workflows/build-downloader.yml`)
that rebuilds the EXE whenever `download.py` changes.

Distribution: `MEPS_Quota_Downloader.exe` (from `download.py`, standard
library only) fetches all four files anonymously and saves them under
`data/output/YYYY-MM-DD/` beside the EXE, warning when the published data
looks stale or incomplete. On startup it self-updates: it reads
`downloader_version.txt` from the release and, if a newer build exists, swaps
in the new EXE (effective on the next run), so a machine only needs the EXE
once and future improvements arrive automatically. See
`docs/DAILY_UPDATE_RUNBOOK.md`.
