# EU Quota Scraper

Automated collection of EU steel tariff quota data from the European Commission's TARIC database.

## Overview

This tool scrapes quota usage data from the EU TARIC system to track steel import quotas. When quotas are exhausted, a **25% tariff** applies to additional imports.

### Key Features

- **Automated data collection** from EU TARIC quota pages
- **Calculated metrics**: % used, % remaining, daily burn rate, estimated exhaustion date
- **Excel output** formatted for customer reports and Power BI integration
- **Handles 189 quotas** across multiple steel products and origin countries

## Quick Start

```powershell
# Using the numberscrapping project virtual environment
& "c:/Users/lyen/Downloads/numberscrapping project/.venv/Scripts/python.exe" "c:/Users/lyen/Downloads/EU Quota/main.py"
```

Or if running from within the EU Quota folder with dependencies installed:
```bash
python main.py           # Interactive mode
python main.py --auto    # Automatic mode (for scheduling)
```

## Output Files

Files are saved to `data/output/` (created automatically):

| File | Description |
|------|-------------|
| `eu_quota_report_YYYYMMDD.xlsx` | Full scraped data |
| `eu_quota_report_YYYYMMDD_customer.xlsx` | Customer-ready summary |

Snapshots saved to `data/snapshots/` for historical tracking.

### Customer Report Columns

| Column | Description |
|--------|-------------|
| Product Category | Steel product type |
| Origin | Country of origin |
| Order Number | 6-digit EU quota identifier |
| Initial Quota (kg) | Total quota volume |
| Quota Used (kg) | Amount consumed |
| Used (%) | Usage percentage |
| Remaining (kg) | Balance remaining |
| Remaining (%) | Balance percentage |
| Critical | Quota exhaustion warning flag |
| Days Left in Quarter | Days until quarter ends |
| Est. Days to Exhaustion | Projected days until quota runs out |

## Project Structure

```
EU Quota/
├── eu_quota_scraper/
│   ├── __init__.py
│   ├── config.py           # URL patterns, quarter dates
│   ├── scraper.py          # Selenium-based web scraper
│   ├── data_processor.py   # Metric calculations
│   └── exporter.py         # Excel export
├── main.py                 # Entry point
├── requirements.txt
├── README.md
├── README_繁體中文.md       # Chinese documentation
└── EU Quota URL's.xlsx     # Input: quota list to track
```

## Technical Notes

- **Order Number Format**: Automatically pads to 6 digits with leading zeros (e.g., `98967` → `098967`)
- **Quarterly Periods**: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec)
- **Rate Limiting**: 1 second delay between requests
- **Expected Runtime**: ~15-20 minutes for all 189 quotas

## Scheduling Daily Updates (Windows)

1. Open Task Scheduler → Create Basic Task
2. Name: "EU Quota Scraper"
3. Trigger: Daily at preferred time
4. Action: Start a program
   - Program: `c:\Users\lyen\Downloads\numberscrapping project\.venv\Scripts\python.exe`
   - Arguments: `c:\Users\lyen\Downloads\EU Quota\main.py --auto`

## Data Source

[EU TARIC Quota Database](https://ec.europa.eu/taxation_customs/dds2/taric/quota_consultation.jsp)
