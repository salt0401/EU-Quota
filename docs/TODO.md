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

## Priority 3: UK Support (In Progress - Skeleton Ready)

### Research Completed (Jan 2026)

**UK Data Source Verified:**
- Website: UK Integrated Online Tariff (HMRC)
- URL: `https://www.trade-tariff.service.gov.uk/quota_search?order_number={ORDER_NUMBER}`
- Data updated: Daily (excluding weekends and bank holidays)
- Units: **Kilograms** (must convert to Tonnes for MEPS report)
- Order numbers: 6 digits starting with "058" (e.g., 058001, 058006)

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

### Files Created/Updated

- [x] `src/uk_scraper.py` - Skeleton class with order numbers reference
- [x] `src/config.py` - UK_BASE_URL and UK_QUOTA_FIELDS added
- [x] `src/__init__.py` - UKQuotaScraper exported
- [ ] `data/input/uk_quota_urls.xlsx` - **PENDING: Need from user**

### Remaining Tasks

1. **Get UK input file** (`uk_quota_urls.xlsx`)
   - Same format as EU: Order Number, Quota Category, Country

2. **Implement UK scraper fetch logic**
   - Parse HTML from quota_search results
   - Extract: Opening Balance, Current Balance, Status, etc.
   - Convert kg to tonnes

3. **Update excel_generator.py**
   - Modify `_update_uk_sheet_xml()` to write actual UK data
   - Update table2.xml for UK data range

4. **Testing Checklist**
   - [x] Verify UK URL structure
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
*Last updated: 23-Jan-2026*
*Slicer fix: String-based XML manipulation in excel_generator.py to preserve namespace prefixes*
