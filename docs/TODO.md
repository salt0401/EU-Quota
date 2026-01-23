# EU Quota Scraper - TODO List

## Priority 1: Completed
- [x] Fix MEPS calculation formulas
- [x] Create dated output folders (YYYY-MM-DD)
- [x] Auto-detect quota period dates
- [x] Generate basic MEPS report

## Priority 2: In Progress
- [ ] Make EU output 100% match MEPS template
  - [ ] Add slicers for Country and Quota Category
  - [ ] Match exact column widths and formatting
  - [ ] Match header styles and colors
  - [ ] Add explanatory text sections

## Priority 3: UK Support (Future)

### When UK URLs are available:

1. **Get UK Data Source**
   - UK quotas use different system: UK Integrated Online Tariff (HMRC)
   - Base URL: https://www.trade-tariff.service.gov.uk/
   - Need input file with UK order numbers

2. **Files to Modify**
   - `src/config.py`: Add UK_BASE_URL (already has placeholder)
   - `src/scraper.py`: Create `UKQuotaScraper` class
   - `src/excel_generator.py`: Add UK sheet generation
   - `data/input/`: Add `uk_quota_urls.xlsx`

3. **UK Scraper Implementation Steps**
   ```python
   # In src/scraper.py, add:
   class UKQuotaScraper:
       def __init__(self, headless=True):
           # Similar to EUQuotaScraper
           pass

       def fetch_quota(self, order_number, start_date):
           # UK-specific page parsing
           pass
   ```

4. **Expected UK Data Fields**
   - Order Number
   - Quota Category (17 categories vs EU's 29)
   - Country (EU, Turkey, All others)
   - Quota Limit, Allocated, Balance

5. **Testing Checklist for UK**
   - [ ] Verify UK URL structure
   - [ ] Test single quota fetch
   - [ ] Test batch processing
   - [ ] Verify data mapping to template

## Priority 4: Auto-Scheduling (After UK Success)

### Windows Task Scheduler Setup

1. **Create Batch File** (`run_scraper.bat`)
   ```batch
   @echo off
   cd /d "C:\Users\lyen\Downloads\EU Quota"
   python main.py --auto >> logs\scraper_%date:~-4,4%%date:~-10,2%%date:~-7,2%.log 2>&1
   ```

2. **Task Scheduler Configuration**
   - Name: "EU Quota Daily Scraper"
   - Trigger: Daily at 6:00 AM (or preferred time)
   - Action: Run `run_scraper.bat`
   - Settings: Run whether user is logged on or not

3. **Files to Create**
   - `scripts/run_scraper.bat` - Windows batch launcher
   - `scripts/run_scraper.sh` - Linux/Mac launcher (optional)

4. **Error Handling**
   - Add email notification on failure
   - Log rotation for old log files
   - Retry logic for network failures

5. **Monitoring**
   - Check `data/output/` for new dated folders
   - Review `logs/` for error messages

## Notes

- EU scraping: ~15-20 minutes for 189 quotas
- UK scraping: TBD (depends on number of quotas)
- Combined runtime estimate: ~25-30 minutes

---
*Last updated: January 2026*
