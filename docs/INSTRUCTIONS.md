# EU Quota Scraper - User Instructions

## Overview

This tool automatically collects EU steel tariff quota data from the European Commission's TARIC database and generates formatted Excel reports for customer delivery.

## Project Structure

```
EU Quota/
├── src/                        # Source code modules
│   ├── config.py              # Configuration and quarter utilities
│   ├── scraper.py             # Web scraper using Selenium
│   ├── data_processor.py      # Data cleaning and calculations
│   ├── excel_generator.py     # MEPS report generator
│   └── utils.py               # File/folder utilities
├── data/
│   ├── input/                 # Input files
│   │   └── quota_urls.xlsx    # List of quotas to scrape
│   ├── output/                # Output files by date
│   │   └── YYYY-MM-DD/        # Dated folders
│   │       ├── eu_quota_raw_*.xlsx
│   │       └── MEPS_EU_Quota_Update_*.xlsx
│   └── snapshots/             # Historical snapshots
├── templates/                 # Reference templates
├── docs/                      # Documentation
├── scripts/                   # Development scripts
└── main.py                    # Main entry point
```

## Installation

1. Install Python 3.8+ if not already installed

2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Chrome browser must be installed (for Selenium)

## Usage

### Interactive Mode
```bash
python main.py
```
The program will prompt for confirmation before starting.

### Automatic Mode (for scheduling)
```bash
python main.py --auto
```
Runs without prompts - ideal for Windows Task Scheduler.

### Custom Input/Output
```bash
python main.py -i custom_quotas.xlsx -o custom_report.xlsx
```

## Input File Format

The input file (`data/input/quota_urls.xlsx`) must contain:

| Column | Required | Description |
|--------|----------|-------------|
| Order Number | Yes | 6-digit quota order number |
| Quota Category | No | Product category name |
| Country | No | Origin country |
| Current Quarter | No | Quarter start date (YYYY-MM-DD) |

## Output Files

Each run creates a dated folder in `data/output/YYYY-MM-DD/`:

1. **eu_quota_raw_YYYYMMDD.xlsx**
   - Complete scraped data with all fields
   - For internal analysis

2. **MEPS_EU_Quota_Update_YYYYMMDD.xlsx**
   - Formatted customer report
   - Contains Instructions sheet and data table
   - Ready for delivery

## Data Calculations

The system uses these formulas (matching MEPS template):

| Field | Formula |
|-------|---------|
| Quota Limit | amount + transferred_amount |
| Balance Remaining | balance - awaiting_allocation |
| Quota Allocated | Quota Limit - Balance Remaining |
| % Allocated | (Quota Allocated / Quota Limit) x 100 |

## Automated Fields

These fields are automatically detected from scraped data:

- **Current quota period**: Extracted from validity_period field
- **Latest available data**: Uses scraping date

## Manual Steps

After running the scraper:

1. Review the generated MEPS report
2. Add any policy change notes if needed
3. Verify data accuracy
4. Deliver to customer

## Scheduling (Future)

For automatic daily scraping, use Windows Task Scheduler:

1. Create a new task
2. Set trigger (e.g., daily at 6:00 AM)
3. Action: Start a program
   - Program: `python`
   - Arguments: `main.py --auto`
   - Start in: `C:\path\to\EU Quota`

## Troubleshooting

### Chrome driver issues
The program automatically downloads the correct Chrome driver. If issues occur:
```bash
pip install --upgrade webdriver-manager
```

### Missing data
Check if:
- Order number format is correct (6 digits)
- Quarter start date is valid
- EU TARIC website is accessible

### Slow performance
- Normal runtime: ~15-20 minutes for 189 quotas
- 1-second delay between requests to avoid rate limiting

## Support

For issues or questions:
- Check the logs in `data/output/` folder
- Review error messages in console output
- Contact the development team

---

*Version 2.0 - January 2026*
