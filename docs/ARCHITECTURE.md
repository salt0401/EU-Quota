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
├── src/                           ◄── MAIN PROJECT - Core source code
│   ├── __init__.py                    Package exports
│   ├── main.py                        Main entry point
│   ├── config.py                      Configuration, URLs, quarters
│   ├── scraper.py                     EU Selenium web scraper
│   ├── uk_scraper.py                  UK Selenium web scraper
│   ├── data_processor.py              Data cleaning & MEPS calculations
│   ├── excel_generator.py             Excel template generation
│   └── utils.py                       File/folder utilities
│
├── build/                         ◄── BUILD EXE - Packaging scripts
│   └── build_exe.py                   PyInstaller build script
│
├── dist/                          ◄── Distribution output (generated EXE)
│
├── data/
│   ├── input/                     ◄── Input files
│   │   ├── quota_urls.xlsx            EU order numbers to scrape
│   │   └── uk_quota_urls.xlsx         UK order numbers to scrape
│   │
│   ├── output/                    ◄── Output by date
│   │   └── YYYY-MM-DD/                Dated folders
│   │       ├── eu_quota_raw_*.xlsx
│   │       ├── uk_quota_raw_*.xlsx
│   │       └── MEPS_Quota_Update_*.xlsx
│   │
│   └── snapshots/                 ◄── Historical data
│       └── snapshot_*.xlsx
│
├── templates/                     ◄── Reference templates
│   ├── meps_customer_template.xlsx    (with slicers)
│   └── detail_reference.png
│
├── docs/                          ◄── Documentation
│   ├── INSTRUCTIONS.md
│   ├── INSTRUCTIONS_繁體中文.md
│   ├── DATA_FLOW_ANALYSIS.md
│   ├── TODO.md
│   └── ARCHITECTURE.md                (this file)
│
├── dev/                           ◄── Development tools
│   ├── scripts/                       Utility scripts
│   └── analysis/                      Analysis and debugging tools
│
├── requirements.txt
├── README.md
└── README_繁體中文.md
```

## Key Components

### 1. Scraper (scraper.py, uk_scraper.py)
```
┌─────────────────────────────────────────┐
│     EUQuotaScraper / UKQuotaScraper     │
├─────────────────────────────────────────┤
│ • _setup_driver()   Chrome/Selenium    │
│ • fetch_quota()     Single order       │
│ • fetch_all_quotas() Batch process     │
│ • _parse_value()    Clean raw data     │
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
│ Init Selenium   │
│ (Chrome)        │
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

## Folder Purpose Summary

| Folder | Purpose | When to Focus |
|--------|---------|---------------|
| `src/` | Core application logic | Adding features, fixing bugs |
| `build/` | EXE packaging scripts | Adjusting distribution settings |
| `dist/` | Generated EXE output | Distribution |
| `data/` | Runtime data (I/O) | Managing input/output files |
| `templates/` | Excel templates | Template changes |
| `docs/` | Documentation | Updating docs |
| `dev/` | Development tools | Debugging, analysis |

---

*Architecture Document v2.1 - January 2026*
