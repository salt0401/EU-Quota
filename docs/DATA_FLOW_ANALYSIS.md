# EU Quota Project - Data Flow Analysis

## Overview

This document describes how data flows from input sources through the scraping system to the final customer-facing MEPS Excel report.

---

## 1. INPUT DATA

### File: `data/input/quota_urls.xlsx`

| Column | Description | Example |
|--------|-------------|---------|
| Order Number | EU quota order number | 098967 |
| Quota Category | Steel product category | Non Alloy and Other Alloy Hot Rolled Sheets and Strips - 1a |
| Country | Origin country | Türkiye, India, Korea, Republic of |
| Current Quarter | Quarter start date | 2026-01-01 |
| URL | Link to EU TARIC page | https://ec.europa.eu/taxation_customs/dds2/taric/... |

**Total quotas tracked:** ~189 EU quotas

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
| validity_period | string | "01-01-2026 - 31-03-2026" |
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
| validity_start | parsed from validity_period | Quarter start |
| validity_end | parsed from validity_period | Quarter end |
| quota_used | initial_amount - balance | Tonnage used |
| quota_used_pct | (quota_used / initial_amount) * 100 | Usage percentage |
| quota_remaining_pct | (balance / initial_amount) * 100 | Remaining percentage |
| days_remaining_in_quarter | validity_end - today | Days until quarter ends |
| daily_burn_rate | quota_used / days_elapsed | Daily usage rate |
| est_days_until_exhaustion | balance / daily_burn_rate | Estimated exhaustion |

---

## 3. OUTPUT FILES

### 3.1 Raw Scraping Output
**File:** `data/output/eu_quota_report_YYYYMMDD.xlsx`

Contains all scraped fields plus input data and calculated metrics.

### 3.2 Customer Report
**File:** `data/output/eu_quota_report_YYYYMMDD_customer.xlsx`

Simplified view with selected columns for customer delivery.

### 3.3 Historical Snapshot
**File:** `data/snapshots/snapshot_YYYYMMDD_HHMMSS.xlsx`

Timestamped snapshot for trend analysis.

---

## 4. CUSTOMER TEMPLATE (MEPS Format)

### File: `templates/meps_customer_template.xlsx`

### Sheet Structure

```
Sheet 1: Instructions
├── Title: "MEPS Quota Update - December 2025"
├── Overview of EU and UK safeguard systems
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
| Country | origin | Direct mapping |
| Quota Limit (Tonnes) | **amount + transferred_amount** | Calculated |
| Quota Allocated (Tonnes) | quota_used (initial_amount - balance) | Calculated |
| % Quota Allocated | quota_used_pct | Calculated |
| Balance Remaining (Tonnes) | **balance - awaiting_allocation** | Calculated |
| % Balance Remaining | 100 - quota_used_pct | Calculated |

---

## 5. CRITICAL DATA MAPPING

### From `detail_reference.png`:

```
SCRAPED DATA → CUSTOMER REPORT

amount + transferred_amount = Quota Limit
balance - awaiting_allocation = Balance Remaining

(Left side = source data, Right side = published information)
```

### Current Issue
The existing `data_processor.py` calculates differently than the MEPS template expects:

| Current Code | MEPS Template Expects |
|--------------|----------------------|
| `initial_amount - balance` → quota_used | Same |
| `balance` → remaining | `balance - awaiting_allocation` |
| Not calculated | `amount + transferred_amount` → Quota Limit |

**This mapping needs to be fixed in the rebuild.**

---

## 6. INTERACTIVE ELEMENTS IN MEPS TEMPLATE

### Slicers (Interactive Filters)
- **Country Slicer**: 2-column layout, filter by country
- **Quota Category Slicer**: Filter by product category
- Multiple selection supported (Ctrl+click)
- Clear filter buttons included

### Excel Tables
- `EU_Quotas4`: European Union data (rows 15-204)
- `UK_Quotas`: United Kingdom data (rows 15-86)
- Features: Auto-filter headers, row stripes, header styling

### Sheet Protection
- Instructions sheet is protected (read-only)
- Data sheets allow sorting/filtering

### Formulas
- Instructions sheet pulls dates from data sheets:
  - `'European Union'!A2` → Current quota period
  - `'European Union'!A3` → Latest available data

### Hyperlinks
- Links to EU TARIC consultation page
- Links to UK Integrated Online Tariff

---

## 7. AUTOMATED vs MANUAL CONTENT

### Automated (From Scraping)
- All quota data values
- Percentage calculations
- Order numbers and categories
- Country/origin information
- Balance and allocation figures

### Manual (Analyst Input Required)
- "Current quota period: 01-Oct-2025 to 30-Dec-2025"
- "Latest available data: 12-Dec-2025"
- Explanatory notes about policy changes
- Special annotations (e.g., Russian slab quota changes)
- **UK data** (requires separate scraper - different source)

---

## 8. DATA REFRESH WORKFLOW

```
1. Update input file with any new quotas
         ↓
2. Run scraper (main.py)
         ↓
3. Raw data saved to output/
         ↓
4. Snapshot saved to snapshots/
         ↓
5. [MANUAL] Copy data to MEPS template
         ↓
6. [MANUAL] Update period dates
         ↓
7. [MANUAL] Add analyst notes
         ↓
8. Deliver to customer
```

---

## 9. KEY OBSERVATIONS FOR REBUILD

1. **Calculation Mismatch**: Current processor uses `initial_amount`, but MEPS template uses `amount + transferred_amount` for Quota Limit

2. **Missing Field**: Need to calculate `balance - awaiting_allocation` for Balance Remaining

3. **UK Data Gap**: No scraper exists for UK quotas (different data source)

4. **Manual Steps**: Template requires manual updates for dates and analyst notes

5. **Slicer Dependency**: Interactive features rely on Excel table structure

6. **Units**: All values stored in kg but displayed as Tonnes (divide by 1000)
