# EU Quota Scraper - System Architecture

## Program Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INPUT                                      │
│                                                                             │
│   python run.py [--skip-uk] [-i input.xlsx] [-o output.xlsx]                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              run.py                                          │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Convenience wrapper that calls src/main.py                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            src/main.py                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  1. Parse arguments                                                  │    │
│  │  2. Create dated output folder (YYYY-MM-DD)                         │    │
│  │  3. Load input file                                                 │    │
│  │  4. Initialize scraper                                              │    │
│  │  5. Process results                                                 │    │
│  │  6. Generate outputs                                                │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐
│   INPUT FILES     │   │   SRC MODULES     │   │   OUTPUT FILES    │
│                   │   │                   │   │                   │
│ data/input/       │   │ src/              │   │ data/output/      │
│ ├─quota_urls.xlsx │   │ ├─config.py       │   │ └─YYYY-MM-DD/     │
│ └─uk_quota_urls   │   │ ├─scraper.py      │   │   ├─eu_raw.xlsx   │
│                   │   │ ├─uk_scraper.py   │   │   ├─uk_raw.xlsx   │
│                   │   │ ├─data_processor  │   │   └─MEPS.xlsx     │
│                   │   │ ├─excel_generator │   │                   │
│                   │   │ └─utils.py        │   │ data/snapshots/   │
└───────────────────┘   └───────────────────┘   └───────────────────┘
```

## Module Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                run.py                                        │
│                         (Convenience Wrapper)                                │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ imports
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            src/main.py                                       │
│                           (Entry Point)                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ imports
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             src/__init__.py                                  │
│                          (Package Interface)                                 │
└─────────────────────────────────────────────────────────────────────────────┘
         │              │               │               │
         ▼              ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  config.py  │  │ scraper.py  │  │data_process │  │excel_genera │
│             │  │ uk_scraper  │  │   or.py     │  │   tor.py    │
│ - Quarters  │  │             │  │ - Clean     │  │ - Template  │
│ - URLs      │  │ - Selenium  │  │ - Calculate │  │ - Format    │
│ - Dates     │  │ - WebDriver │  │ - MEPS math │  │ - Slicers   │
│             │  │ - Parse     │  │             │  │             │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
         │                               │               │
         └───────────────┬───────────────┘               │
                         ▼                               │
                  ┌─────────────┐                       │
                  │  utils.py   │◄──────────────────────┘
                  │             │
                  │ - Folders   │
                  │ - Dates     │
                  │ - Paths     │
                  └─────────────┘
```

## Data Pipeline

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              DATA PIPELINE                                    │
└──────────────────────────────────────────────────────────────────────────────┘

    INPUT                   SCRAPE                  PROCESS                OUTPUT
      │                       │                       │                      │
      ▼                       ▼                       ▼                      ▼
┌──────────┐           ┌──────────┐           ┌──────────┐           ┌──────────┐
│  Excel   │           │  EU/UK   │           │  Clean   │           │  MEPS    │
│  Input   │──────────▶│  TARIC   │──────────▶│  Data    │──────────▶│  Excel   │
│  File    │           │ Website  │           │          │           │ Template │
└──────────┘           └──────────┘           └──────────┘           └──────────┘
     │                       │                       │                      │
     │                       │                       │                      │
     ▼                       ▼                       ▼                      ▼
┌──────────┐           ┌──────────┐           ┌──────────┐           ┌──────────┐
│ • Order  │           │ • amount │           │ MEPS     │           │ • Slicers│
│   Number │           │ • balance│           │ Formulas:│           │ • Tables │
│ • Quota  │           │ • trans- │           │          │           │ • Format │
│   Cat.   │           │   ferred │           │ Limit =  │           │ • Filter │
│ • Country│           │ • await- │           │ amt+tran │           │          │
│ • Quarter│           │   ing    │           │          │           │          │
│          │           │ • dates  │           │ Balance =│           │          │
│          │           │          │           │ bal-wait │           │          │
└──────────┘           └──────────┘           └──────────┘           └──────────┘
```

## File Structure

```
EU Quota/
│
├── run.py                         ◄── Convenience entry point (run this)
│
├── src/                           ◄── MAIN PIPELINE — scraping + reporting
│   ├── __init__.py                    Package exports
│   ├── main.py                        Main entry point
│   ├── config.py                      Configuration, URLs, quarters
│   ├── scraper.py                     EU fast HTTP scraper
│   ├── uk_scraper.py                  UK API scraper
│   ├── data_processor.py              Data cleaning & MEPS calculations
│   ├── excel_generator.py             Excel template generation
│   ├── snapshot_scheduler.py          Daily snapshot idempotent check
│   └── utils.py                       File/folder utilities
│
├── beta/                          ◄── EXPERIMENTAL — isolated from src/
│   ├── README.md                      Usage & status docs
│   ├── requirements.txt               Prophet + scipy (Phase 2+)
│   ├── forecasting/                   Quota depletion prediction
│   │   ├── __init__.py                Public API exports
│   │   ├── data_loader.py            Snapshot loading & Prophet prep
│   │   ├── preprocessor.py           Feature engineering (skeleton)
│   │   └── simple_models.py          Baseline models (skeleton)
│   └── tests/
│       └── test_forecasting_data_loader.py
│
├── dist/                          ◄── Distribution output (EXE)
│
├── data/
│   ├── input/                     ◄── Input files
│   │   ├── quota_urls.xlsx            EU order numbers to scrape
│   │   └── uk_quota_urls.xlsx         UK order numbers to scrape
│   │
│   ├── output/                    ◄── Output by date
│   │   └── YYYY-MM-DD/
│   │       ├── eu_quota_raw_*.xlsx
│   │       ├── uk_quota_raw_*.xlsx
│   │       └── MEPS_Quota_Update_*.xlsx
│   │
│   └── snapshots/                 ◄── Historical data (auto-collected daily)
│       └── snapshot_YYYYMMDD_HHMMSS.xlsx
│
├── templates/                     ◄── Reference templates
│   ├── meps_customer_template.xlsx    (with slicers)
│   └── detail_reference.png
│
├── docs/                          ◄── Documentation
│   ├── ARCHITECTURE.md                (this file)
│   ├── TODO.md
│   ├── INSTRUCTIONS.md
│   ├── INSTRUCTIONS_繁體中文.md
│   └── DATA_FLOW_ANALYSIS.md
│
├── tests/                         ◄── Main pipeline unit tests
│   ├── test_config.py
│   ├── test_data_processor.py
│   ├── test_utils.py
│   ├── test_scraper.py
│   └── test_uk_scraper.py
│
├── requirements.txt                   Core dependencies only
├── README.md
└── README_繁體中文.md
```

## Key Components

### 1. Scraper (scraper.py, uk_scraper.py)
```
┌─────────────────────────────────────────┐
│     EUQuotaScraper / UKQuotaScraper     │
├─────────────────────────────────────────┤
│ • fetch_quota()     Single order       │
│ • fetch_all_quotas() Batch (5 workers) │
│ • _parse_value()    Clean raw data     │
│ • Fast HTTP / API   No browser needed  │
└─────────────────────────────────────────┘
```

### 2. Data Processor (data_processor.py)
```
┌─────────────────────────────────────────┐
│          MEPS Calculations              │
├─────────────────────────────────────────┤
│                                         │
│  Quota Limit = amount + transferred     │
│                                         │
│  Balance Remaining = balance - awaiting │
│                                         │
│  % Allocated = allocated / limit × 100  │
│                                         │
└─────────────────────────────────────────┘
```

### 3. Excel Generator (excel_generator.py)
```
┌─────────────────────────────────────────┐
│         Template Strategy               │
├─────────────────────────────────────────┤
│                                         │
│  1. Copy meps_customer_template.xlsx    │
│  2. Open with openpyxl                  │
│  3. Update dates in A2, A3              │
│  4. Clear existing data rows            │
│  5. Insert new data                     │
│  6. Save → Slicers preserved!           │
│                                         │
└─────────────────────────────────────────┘
```

## Execution Flow

```
START
  │
  ▼
┌─────────────────┐
│ Parse CLI args  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Create folders  │──────▶ data/output/YYYY-MM-DD/
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Load input xlsx │◀────── data/input/quota_urls.xlsx
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Init scraper    │
│ (Fast HTTP)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐         ┌─────────────────┐
│ FOR each quota  │────────▶│ Fetch from      │
│ (189+ orders)   │         │ EU TARIC site   │
└────────┬────────┘         └─────────────────┘
         │ (1 sec delay)
         ▼
┌─────────────────┐
│ UK Scraping     │◀────── data/input/uk_quota_urls.xlsx
│ (if enabled)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Clean data      │
│ Calculate       │──────▶ MEPS formulas
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Copy template   │◀────── templates/meps_customer_template.xlsx
│ Update data     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Save outputs    │──────▶ data/output/YYYY-MM-DD/
└────────┬────────┘         ├── eu_quota_raw_*.xlsx
         │                  ├── uk_quota_raw_*.xlsx
         ▼                  └── MEPS_Quota_Update_*.xlsx
       END
```

## Module Boundary: src/ vs beta/

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     src/ — MAIN PIPELINE (production)                        │
│                                                                             │
│   run.py → src/main.py → scraper → data_processor → excel_generator        │
│                                                                             │
│   Input: data/input/quota_urls.xlsx                                         │
│   Output: data/output/YYYY-MM-DD/MEPS_Quota_Update_*.xlsx                  │
│                                                                             │
│   Dependencies: requirements.txt                                            │
└─────────────────────────────────────────────────────────────────────────────┘
         │ snapshot_*.xlsx (written daily)
         │
         ▼
┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
│                     beta/ — EXPERIMENTAL (isolated)                          │
│                                                                             │
│   from beta.forecasting import load_all_snapshots                           │
│                                                                             │
│   Reads: data/snapshots/snapshot_*.xlsx  (read-only)                        │
│   Dependencies: beta/requirements.txt                                       │
│                                                                             │
│   - Lives in separate top-level directory                                   │
│   - Zero imports from/to src/                                               │
│   - Cannot affect main pipeline in any way                                  │
└ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

The only shared touchpoint is `data/snapshots/` — the main pipeline writes snapshots,
the beta forecasting module reads them. No code dependency exists between the two.

## Folder Purpose Summary

| Folder | Purpose | When to Focus |
|--------|---------|---------------|
| `src/` | Core scraping + reporting pipeline | Adding features, fixing bugs |
| `beta/` | Experimental features (forecasting) | Isolated experimentation |
| `dist/` | Generated EXE output | Distribution |
| `data/` | Runtime data (I/O) | Managing input/output files |
| `templates/` | Excel templates | Template changes |
| `docs/` | Documentation | Updating docs |
| `tests/` | Main pipeline unit tests | Testing core logic |

---

*Architecture Document v2.3 - February 2026*
