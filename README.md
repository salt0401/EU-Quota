# EU Quota Scraper v2.0

Automated collection of EU steel tariff quota data from the European Commission's TARIC database.

## Overview

This tool scrapes quota usage data from the EU TARIC system to track steel import quotas. When quotas are exhausted, a **25% tariff** applies to additional imports.

### Key Features

- **Automated data collection** from EU TARIC quota pages
- **MEPS-formatted Excel reports** with tables and filters
- **Automatic date detection** for quota periods
- **Dated output folders** (YYYY-MM-DD) for historical tracking
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
python main.py           # Interactive mode
python main.py --auto    # Automatic mode (for scheduling)
```

## Output Files

Files are organized by date in `data/output/YYYY-MM-DD/`:

| File | Description |
|------|-------------|
| `eu_quota_raw_YYYYMMDD.xlsx` | Complete scraped data |
| `MEPS_EU_Quota_Update_YYYYMMDD.xlsx` | Customer-ready report |

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
├── src/                           # Core source code
│   ├── config.py                  # Configuration & quarter utilities
│   ├── scraper.py                 # Selenium web scraper
│   ├── data_processor.py          # Data calculations (MEPS formulas)
│   ├── excel_generator.py         # MEPS report generator
│   └── utils.py                   # File/folder utilities
├── data/
│   ├── input/                     # Input files
│   │   └── quota_urls.xlsx        # Quota list to track
│   ├── output/                    # Output by date
│   │   └── YYYY-MM-DD/            # Dated folders
│   └── snapshots/                 # Historical snapshots
├── templates/                     # Reference templates
├── docs/                          # Documentation
│   ├── INSTRUCTIONS.md            # English
│   └── INSTRUCTIONS_繁體中文.md    # Traditional Chinese
├── main.py                        # Entry point
├── requirements.txt               # Dependencies
└── README.md
```

## Technical Notes

- **Order Number Format**: Automatically pads to 6 digits (e.g., `98967` → `098967`)
- **Quarterly Periods**: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec)
- **Rate Limiting**: 1 second delay between requests
- **Expected Runtime**: ~15-20 minutes for 189 quotas

## Scheduling Daily Updates (Windows)

1. Open Task Scheduler → Create Basic Task
2. Name: "EU Quota Scraper"
3. Trigger: Daily at preferred time
4. Action: Start a program
   - Program: `python`
   - Arguments: `main.py --auto`
   - Start in: `C:\path\to\EU Quota`

## Documentation

- [English Instructions](docs/INSTRUCTIONS.md)
- [繁體中文說明](docs/INSTRUCTIONS_繁體中文.md)
- [Data Flow Analysis](docs/DATA_FLOW_ANALYSIS.md)

## Data Source

[EU TARIC Quota Database](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp)

---

*Version 2.0 - January 2026*
