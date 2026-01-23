# EU Quota Scraper - System Architecture

## Program Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              USER INPUT                                      │
│                                                                             │
│   python main.py [--auto] [-i input.xlsx] [-o output.xlsx]                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              main.py                                         │
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
│ └─quota_urls.xlsx │   │ ├─config.py       │   │ └─YYYY-MM-DD/     │
│                   │   │ ├─scraper.py      │   │   ├─raw.xlsx      │
│                   │   │ ├─data_processor  │   │   └─MEPS.xlsx     │
│                   │   │ ├─excel_generator │   │                   │
│                   │   │ └─utils.py        │   │ data/snapshots/   │
└───────────────────┘   └───────────────────┘   └───────────────────┘
```

## Module Dependencies

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                main.py                                       │
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
│             │  │             │  │   or.py     │  │   tor.py    │
│ - Quarters  │  │ - Selenium  │  │ - Clean     │  │ - Template  │
│ - URLs      │  │ - WebDriver │  │ - Calculate │  │ - Format    │
│ - Dates     │  │ - Parse     │  │ - MEPS math │  │ - Slicers   │
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
│  Excel   │           │   EU     │           │  Clean   │           │  MEPS    │
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
├── main.py                    ◄── Entry point (run this)
│
├── src/                       ◄── Source code modules
│   ├── __init__.py               Package exports
│   ├── config.py                 Configuration, URLs, quarters
│   ├── scraper.py                Selenium web scraper
│   ├── data_processor.py         Data cleaning & MEPS calculations
│   ├── excel_generator.py        Excel template generation
│   └── utils.py                  File/folder utilities
│
├── data/
│   ├── input/                 ◄── Input files
│   │   └── quota_urls.xlsx       Order numbers to scrape
│   │
│   ├── output/                ◄── Output by date
│   │   └── YYYY-MM-DD/           Dated folders
│   │       ├── eu_quota_raw_*.xlsx
│   │       └── MEPS_EU_Quota_Update_*.xlsx
│   │
│   └── snapshots/             ◄── Historical data
│       └── snapshot_*.xlsx
│
├── templates/                 ◄── Reference templates
│   ├── meps_customer_template.xlsx  (with slicers)
│   └── detail_reference.png
│
├── docs/                      ◄── Documentation
│   ├── INSTRUCTIONS.md
│   ├── INSTRUCTIONS_繁體中文.md
│   ├── DATA_FLOW_ANALYSIS.md
│   ├── TODO.md
│   └── ARCHITECTURE.md        (this file)
│
├── scripts/                   ◄── Development tools
│
├── requirements.txt
└── README.md
```

## Key Components

### 1. Scraper (scraper.py)
```
┌─────────────────────────────────────────┐
│           EUQuotaScraper                │
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
│ (189 orders)    │         │ EU TARIC site   │
└────────┬────────┘         └─────────────────┘
         │ (1 sec delay)
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
         │                  └── MEPS_EU_Quota_Update_*.xlsx
         ▼
       END
```

---

*Architecture Document v2.0 - January 2026*
