# -*- coding: utf-8 -*-
"""
UK Quota Scraper - Scrapes UK steel tariff quota data from UK Integrated Online Tariff

Source: https://www.trade-tariff.service.gov.uk/quota_search
Data Source: UK Integrated Online Tariff (HMRC)
Data updated: Daily (excluding weekends and bank holidays)
Units: Kilograms (converted to Tonnes for MEPS report)

UK Steel Safeguard Categories (17 total):
- Category 1A: Non-alloy hot-rolled sheet
- Category 1B: Other alloy hot-rolled sheet
- Category 4: Metallic coated sheet
- Category 5: Organic coated sheet
- Category 6: Tin mill products
- Category 7: Quarto plates
- Category 12A: Alloy merchant bars
- Category 12B: Non-alloy merchant bars
- Category 13: Rebar
- Category 16: Wire rod
- Category 17: Angles/shapes/sections
- Category 19: Railway material
- Category 20: Gas pipe
- Category 21: Hollow section
- Category 25A: Large welded tube (1)
- Category 25B: Large welded tube (2)
- Category 26: Other welded tube

Order Number Format: 6 digits starting with "058" (e.g., 058001, 058006)
"""

import re
import time
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List

from .config import UK_BASE_URL


class UKQuotaScraper:
    """
    Selenium-based scraper for UK Integrated Online Tariff quota data

    Example:
        scraper = UKQuotaScraper(headless=True)
        data = scraper.fetch_all_quotas(df, order_col='Order Number')
    """

    def __init__(self, headless: bool = True):
        """
        Initialize UK scraper

        Args:
            headless: Run Chrome in headless mode (default True)
        """
        self.headless = headless
        self.driver = None
        self.base_url = UK_BASE_URL

    def _setup_driver(self):
        """Setup Chrome WebDriver"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager
        except ImportError as e:
            print("Missing dependencies. Please install:")
            print("   pip install selenium webdriver-manager")
            raise e

        options = Options()
        if self.headless:
            options.add_argument('--headless=new')

        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

        # Disable automation detection
        options.add_experimental_option('excludeSwitches', ['enable-automation'])
        options.add_experimental_option('useAutomationExtension', False)

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)

        # Additional anti-detection
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            '''
        })

        return self.driver

    def _close_driver(self):
        """Close WebDriver"""
        if self.driver:
            self.driver.quit()
            self.driver = None

    def _build_url(self, order_number: str) -> str:
        """
        Build URL for quota search

        Args:
            order_number: 6-digit UK quota order number (e.g., '058001')

        Returns:
            str: Full URL for quota search page
        """
        order_number = str(order_number).zfill(6)
        return f"{self.base_url}?order_number={order_number}"

    def _parse_kg_value(self, text: str) -> Optional[float]:
        """
        Parse kilogram value from text like "183,592,000.000 Kilogram (kg)"

        Args:
            text: Raw text containing the kg value

        Returns:
            float: Value in kg, or None if parsing fails
        """
        if not text:
            return None

        # Remove commas and find the number
        match = re.search(r'([\d,]+(?:\.\d+)?)\s*(?:Kilogram|kg)', text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except ValueError:
                pass

        # Try to extract just a number
        match = re.search(r'([\d,]+(?:\.\d+)?)', text)
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except ValueError:
                pass

        return None

    def _parse_date_range(self, text: str) -> tuple:
        """
        Parse date range from text like "1 January 2026 to 31 March 2026"

        Returns:
            tuple: (start_date, end_date) as strings, or (None, None)
        """
        if not text:
            return None, None

        # Pattern: "1 January 2026 to 31 March 2026"
        match = re.search(r'(\d{1,2}\s+\w+\s+\d{4})\s+to\s+(\d{1,2}\s+\w+\s+\d{4})', text)
        if match:
            return match.group(1), match.group(2)

        return None, None

    def fetch_quota(self, order_number: str) -> Optional[Dict]:
        """
        Fetch single quota data from UK website

        The UK tariff search page shows results in a table format:
        - Order number | Commodity codes | Country | Start date | End date | Balance

        The Balance shown is the CURRENT remaining balance (not opening balance).
        Opening balance will be taken from the template quota limit.

        Args:
            order_number: UK quota order number

        Returns:
            dict: Quota data or None if failed
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        url = self._build_url(order_number)
        print(f"  Fetching UK quota {order_number}...")

        try:
            if self.driver is None:
                self._setup_driver()

            self.driver.get(url)
            time.sleep(2)  # Allow page to load

            # Wait for page content
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "main"))
                )
            except Exception:
                print(f"    Warning: Page not loaded for order {order_number}")
                return None

            # Get page text
            page_text = self.driver.find_element(By.TAG_NAME, "body").text

            data = {
                'order_number': order_number,
                'scrape_timestamp': datetime.now().isoformat(),
                'url': url,
            }

            # The UK page shows current balance in table row format
            # Pattern: "165,243,093.260 Kilogram (kg)" at end of the row
            # This is the CURRENT (remaining) balance, NOT opening balance

            # Try to find balance value (last number followed by "Kilogram" in the results)
            # Look for pattern like: "31 March 2026 165,243,093.260 Kilogram (kg)"
            balance_match = re.search(
                r'\d{4}\s+([\d,]+\.?\d*)\s*Kilogram',
                page_text,
                re.IGNORECASE
            )
            if balance_match:
                data['current_balance_kg'] = self._parse_kg_value(balance_match.group(0))
            else:
                # Try alternative: find any kilogram value
                kg_match = re.search(r'([\d,]+\.?\d*)\s*Kilogram\s*\(kg\)', page_text, re.IGNORECASE)
                if kg_match:
                    data['current_balance_kg'] = self._parse_kg_value(kg_match.group(0))
                else:
                    data['current_balance_kg'] = None

            # Opening balance will be set from template, not scraped
            data['opening_balance_kg'] = None

            # Parse Quota Period - look for date range in format
            # "01 January 2026 31 March 2026" (dates separated by space in table)
            period_match = re.search(
                r'(\d{1,2}\s+\w+\s+\d{4})\s+(\d{1,2}\s+\w+\s+\d{4})',
                page_text
            )
            if period_match:
                data['validity_start'] = period_match.group(1)
                data['validity_end'] = period_match.group(2)
                data['validity_period'] = f"{period_match.group(1)} to {period_match.group(2)}"
            else:
                data['validity_start'] = None
                data['validity_end'] = None
                data['validity_period'] = None

            # Parse Last Updated
            updated_match = re.search(r'Last updated[:\s]*(\d{1,2}\s+\w+\s+\d{4})', page_text)
            if updated_match:
                data['last_updated'] = updated_match.group(1)
            else:
                data['last_updated'] = None

            # Status: check if balance is zero or very low
            if data.get('current_balance_kg') is not None:
                if data['current_balance_kg'] <= 0:
                    data['status'] = 'Exhausted'
                elif data['current_balance_kg'] < 1000:  # Less than 1 tonne
                    data['status'] = 'Critical'
                else:
                    data['status'] = 'Open'
            else:
                data['status'] = 'Unknown'

            balance_kg = data.get('current_balance_kg')
            if balance_kg is not None:
                print(f"    Success: order {order_number} - Balance: {balance_kg:,.0f} kg")
            else:
                print(f"    Success: order {order_number} - Balance: N/A (no data found)")
            return data

        except Exception as e:
            print(f"    Error fetching {order_number}: {e}")
            return None

    def fetch_all_quotas(
        self,
        quotas_df: pd.DataFrame,
        order_col: str = 'Order Number',
        category_col: str = 'Quota Category',
        country_col: str = 'Country',
        template_limit_col: str = 'Template Quota Limit',
        delay: float = 1.0
    ) -> pd.DataFrame:
        """
        Fetch all UK quotas from input DataFrame

        Uses caching to avoid scraping the same order number multiple times.
        For countries with * (individual caps within "All others"), uses the
        template quota limit instead of scraped opening balance.

        Args:
            quotas_df: DataFrame with quota order numbers
            order_col: Column name for order numbers
            category_col: Column name for quota category
            country_col: Column name for country
            template_limit_col: Column name for template quota limit
            delay: Delay between requests (seconds)

        Returns:
            pd.DataFrame: Scraped data with calculated metrics
        """
        total = len(quotas_df)
        print(f"\n" + "=" * 60)
        print("UK QUOTA SCRAPER")
        print("=" * 60)
        print(f"Processing {total} UK quota rows...")

        # First, identify unique order numbers to scrape
        unique_orders = quotas_df[order_col].dropna().unique()
        unique_orders = [str(o).zfill(6) for o in unique_orders if str(o) != 'UNKNOWN']
        print(f"Unique order numbers to fetch: {len(unique_orders)}")

        # Cache for scraped data
        scraped_cache = {}
        success_count = 0
        fail_count = 0

        try:
            self._setup_driver()

            # Scrape unique order numbers
            for idx, order_number in enumerate(unique_orders, 1):
                print(f"[{idx}/{len(unique_orders)}]", end=" ")

                quota_data = self.fetch_quota(order_number)

                if quota_data:
                    scraped_cache[order_number] = quota_data
                    success_count += 1
                else:
                    scraped_cache[order_number] = None
                    fail_count += 1

                time.sleep(delay)

        finally:
            self._close_driver()

        print(f"\nFetch completed: {success_count} successful, {fail_count} failed")

        # Now build results for ALL rows using cached data
        print(f"\nBuilding output for {total} rows...")
        results = []

        for idx, row in quotas_df.iterrows():
            raw_order = row[order_col]
            if pd.isna(raw_order) or str(raw_order) == 'UNKNOWN':
                continue

            order_number = str(raw_order).zfill(6)
            cached_data = scraped_cache.get(order_number)

            # Get template quota limit if available (this is our opening balance)
            template_limit = None
            if template_limit_col in quotas_df.columns:
                template_limit = row.get(template_limit_col)
                if pd.notna(template_limit):
                    template_limit = float(template_limit)
                else:
                    template_limit = None

            country = str(row.get(country_col, ''))
            is_individual_cap = country.endswith('*')

            # Build row data
            row_data = {
                'input_order_number': order_number,
                'input_quota_category': row.get(category_col, ''),
                'input_country': country,
                'template_quota_limit': template_limit,
            }

            if cached_data:
                # UK website only shows CURRENT balance, not opening balance
                # Opening balance comes from template quota limit
                scraped_current_kg = cached_data.get('current_balance_kg')

                if template_limit:
                    # Opening balance in kg (template is in tonnes)
                    opening_kg = template_limit * 1000

                    if is_individual_cap:
                        # For "*" countries, they share "All others" order number
                        # Calculate their allocation proportionally based on aggregate
                        # Find the aggregate "All others" row to get proportion
                        if scraped_current_kg is not None:
                            # Get the aggregate opening balance for this order number
                            # Find all rows with same order number to get total template limit
                            same_order_rows = quotas_df[quotas_df[order_col].apply(lambda x: str(x).zfill(6)) == order_number]
                            aggregate_limit = same_order_rows[template_limit_col].sum()
                            if aggregate_limit > 0:
                                aggregate_opening_kg = aggregate_limit * 1000
                                # Calculate aggregate allocated
                                aggregate_allocated = aggregate_opening_kg - scraped_current_kg
                                # Proportion based on this country's share
                                proportion = opening_kg / aggregate_opening_kg
                                row_data['opening_balance_kg'] = opening_kg
                                row_data['allocated_kg'] = aggregate_allocated * proportion
                                row_data['current_balance_kg'] = opening_kg - row_data['allocated_kg']
                            else:
                                row_data['opening_balance_kg'] = opening_kg
                                row_data['allocated_kg'] = 0
                                row_data['current_balance_kg'] = opening_kg
                        else:
                            row_data['opening_balance_kg'] = opening_kg
                            row_data['allocated_kg'] = 0
                            row_data['current_balance_kg'] = opening_kg
                    else:
                        # Regular country - use template limit as opening, scraped as current
                        row_data['opening_balance_kg'] = opening_kg
                        if scraped_current_kg is not None:
                            row_data['current_balance_kg'] = scraped_current_kg
                            row_data['allocated_kg'] = opening_kg - scraped_current_kg
                        else:
                            row_data['current_balance_kg'] = opening_kg
                            row_data['allocated_kg'] = 0
                else:
                    # No template limit - use scraped current balance as opening
                    row_data['opening_balance_kg'] = scraped_current_kg
                    row_data['current_balance_kg'] = scraped_current_kg
                    row_data['allocated_kg'] = 0

                row_data['status'] = cached_data.get('status')
                row_data['validity_period'] = cached_data.get('validity_period')
                row_data['scrape_timestamp'] = cached_data.get('scrape_timestamp')
            else:
                row_data['scrape_status'] = 'failed'
                row_data['scrape_timestamp'] = datetime.now().isoformat()
                # Use template values for failed scrapes
                if template_limit:
                    opening_kg = template_limit * 1000
                    row_data['opening_balance_kg'] = opening_kg
                    row_data['current_balance_kg'] = opening_kg
                    row_data['allocated_kg'] = 0

            results.append(row_data)

        # Create DataFrame and calculate metrics
        df = pd.DataFrame(results)

        if not df.empty and 'opening_balance_kg' in df.columns:
            df = calculate_uk_metrics(df)

        print(f"Output rows: {len(df)}")
        return df


def convert_kg_to_tonnes(kg_value: float) -> float:
    """Convert kilograms to tonnes"""
    if pd.isna(kg_value) or kg_value is None:
        return 0.0
    return kg_value / 1000


def calculate_uk_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate MEPS metrics from UK raw data

    Args:
        df: DataFrame with UK quota data

    Returns:
        pd.DataFrame with calculated metrics
    """
    df = df.copy()

    # Convert kg to tonnes
    df['quota_limit_tonnes'] = df['opening_balance_kg'].apply(convert_kg_to_tonnes)
    df['balance_remaining_tonnes'] = df['current_balance_kg'].apply(convert_kg_to_tonnes)
    df['quota_allocated_tonnes'] = df['quota_limit_tonnes'] - df['balance_remaining_tonnes']

    # Calculate percentages
    df['pct_allocated'] = df.apply(
        lambda r: r['quota_allocated_tonnes'] / r['quota_limit_tonnes']
        if pd.notna(r['quota_limit_tonnes']) and r['quota_limit_tonnes'] > 0 else 0,
        axis=1
    )
    df['pct_remaining'] = df.apply(
        lambda r: r['balance_remaining_tonnes'] / r['quota_limit_tonnes']
        if pd.notna(r['quota_limit_tonnes']) and r['quota_limit_tonnes'] > 0 else 0,
        axis=1
    )

    return df


# UK Quota Order Numbers Reference (from Trade Remedies Notice 2025/12)
UK_QUOTA_ORDER_NUMBERS = {
    # Category 1A - Non-alloy hot-rolled sheet
    '1A_EU': '058001',
    '1A_Turkey': '058967',
    '1A_Taiwan': '058085',
    '1A_All_others': '058002',
    # Category 1B - Other alloy hot-rolled sheet
    '1B_All_others': '058003',
    # Category 4 - Metallic coated sheet
    '4_EU': '058006',
    '4_Taiwan': '058088',
    '4_India': '058106',
    '4_All_others': '058007',
    # Category 5 - Organic coated sheet
    '5_EU': '058010',
    '5_South_Korea': '058827',
    '5_All_others': '058011',
    # Category 6 - Tin mill products
    '6_EU': '058012',
    '6_China': '058831',
    '6_Taiwan': '058098',
    '6_South_Korea': '058097',
    '6_All_others': '058013',
    # Category 7 - Quarto plates
    '7_EU': '058014',
    '7_All_others': '058015',
    # Category 12A - Alloy merchant bars
    '12A_EU': '058100',
    '12A_All_others': '058102',
    # Category 12B - Non-alloy merchant bars
    '12B_EU': '058103',
    '12B_Turkey': '058104',
    '12B_All_others': '058105',
    # Category 13 - Rebar
    '13_EU': '058018',
    '13_Turkey': '058866',
    '13_All_others': '058019',
    # Category 16 - Wire rod
    '16_EU': '058026',
    '16_All_others': '058027',
    # Category 17 - Angles/shapes/sections
    '17_EU': '058028',
    '17_All_others': '058029',
    # Category 19 - Railway material
    '19_EU': '058030',
    '19_All_others': '058031',
    # Category 20 - Gas pipe
    '20_EU': '058032',
    '20_Turkey': '058911',
    '20_India': '058912',
    '20_All_others': '058033',
    # Category 21 - Hollow section
    '21_EU': '058034',
    '21_Turkey': '058916',
    '21_All_others': '058035',
    # Category 25A - Large welded tube (1)
    '25A_EU': '058091',
    '25A_South_Korea': '058095',
    '25A_Japan': '058108',
    '25A_All_others': '058036',
    # Category 25B - Large welded tube (2)
    '25B_EU': '058037',
    '25B_South_Korea': '058974',
    '25B_Japan': '058109',
    '25B_All_others': '058038',
    # Category 26 - Other welded tube
    '26_EU': '058039',
    '26_UAE': '058948',
    '26_Turkey': '058947',
    '26_China': '058949',
    '26_All_others': '058041',
}
