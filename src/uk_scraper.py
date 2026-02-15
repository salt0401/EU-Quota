# -*- coding: utf-8 -*-
"""
UK Quota Scraper - Fast HTTP version using UK Trade Tariff API

This is the FAST version using direct API calls (no browser needed).
For the backup Selenium version, see uk_scraper_selenium.py

API Endpoint: https://www.trade-tariff.service.gov.uk/uk/api/quotas/search
Data updated: Daily (excluding weekends and bank holidays)
Units: Kilograms (converted to Tonnes for MEPS report)
"""

import re
import time
import random
import requests
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import UK_BASE_URL


class UKQuotaScraper:
    """
    Fast HTTP-based scraper for UK quota data using official JSON API

    This version is 10-20x faster than the Selenium version because:
    - Direct HTTP requests (no browser overhead)
    - JSON API response (no HTML parsing needed)
    - Concurrent requests with ThreadPoolExecutor

    Example:
        scraper = UKQuotaScraper()
        data = scraper.fetch_all_quotas(df, order_col='Order Number')
    """

    # UK Trade Tariff JSON API endpoint
    API_BASE_URL = "https://www.trade-tariff.service.gov.uk/uk/api/quotas/search"

    def __init__(self, max_workers: int = 5, min_delay: float = 0.2, max_delay: float = 0.5, headless: bool = True):
        """
        Initialize UK scraper

        Args:
            max_workers: Maximum concurrent requests (default 5)
            min_delay: Minimum delay between requests in seconds
            max_delay: Maximum delay between requests in seconds
            headless: Ignored (kept for API compatibility with Selenium version)
        """
        self.max_workers = max_workers
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.session = None
        self.base_url = UK_BASE_URL
        self.headless = headless

    def _setup_session(self):
        """Setup requests session with appropriate headers"""
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/vnd.hmrc.2.0+json',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def _close_session(self):
        """Close the requests session"""
        if self.session:
            self.session.close()
            self.session = None

    def _random_delay(self):
        """Add random delay to avoid detection"""
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def fetch_quota(self, order_number: str) -> Optional[Dict]:
        """
        Fetch single quota data from UK JSON API

        Args:
            order_number: UK quota order number (e.g., '058001')

        Returns:
            dict: Quota data or None if failed
        """
        order_number = str(order_number).zfill(6)
        url = f"{self.API_BASE_URL}?order_number={order_number}"

        try:
            if self.session is None:
                self._setup_session()

            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            json_data = response.json()

            # Parse the JSON response
            data = {
                'order_number': order_number,
                'scrape_timestamp': datetime.now().isoformat(),
                'url': url,
            }

            # Extract quota definition from response
            if 'data' in json_data and len(json_data['data']) > 0:
                quota_def = json_data['data'][0]
                attrs = quota_def.get('attributes', {})

                # Current balance (remaining)
                balance_str = attrs.get('balance')
                if balance_str:
                    data['current_balance_kg'] = float(balance_str)
                else:
                    data['current_balance_kg'] = None

                # Initial/Opening balance
                initial_str = attrs.get('initial_volume')
                if initial_str:
                    data['opening_balance_kg'] = float(initial_str)
                else:
                    data['opening_balance_kg'] = None

                # Validity period
                start_date = attrs.get('validity_start_date', '')
                end_date = attrs.get('validity_end_date', '')

                if start_date:
                    # Parse ISO date to readable format
                    try:
                        dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                        data['validity_start'] = dt.strftime('%d %B %Y')
                    except:
                        data['validity_start'] = start_date[:10]

                if end_date:
                    try:
                        dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                        data['validity_end'] = dt.strftime('%d %B %Y')
                    except:
                        data['validity_end'] = end_date[:10]

                if data.get('validity_start') and data.get('validity_end'):
                    data['validity_period'] = f"{data['validity_start']} to {data['validity_end']}"

                # Status
                data['status'] = attrs.get('status', 'Unknown')

                # Last allocation date
                last_alloc = attrs.get('last_allocation_date')
                if last_alloc:
                    try:
                        dt = datetime.fromisoformat(last_alloc.replace('Z', '+00:00'))
                        data['last_allocation_date'] = dt.strftime('%d-%m-%Y')
                    except:
                        data['last_allocation_date'] = last_alloc

                return data
            else:
                # No data found for this order number
                data['status'] = 'No Data'
                data['current_balance_kg'] = None
                return data

        except requests.exceptions.RequestException as e:
            print(f"    Error fetching {order_number}: {e}")
            return None
        except Exception as e:
            print(f"    Error parsing {order_number}: {e}")
            return None

    def _fetch_with_delay(self, order_number: str) -> tuple:
        """Fetch quota with delay (for concurrent execution)"""
        result = self.fetch_quota(order_number)
        self._random_delay()
        return order_number, result

    def fetch_all_quotas(
        self,
        quotas_df: pd.DataFrame,
        order_col: str = 'Order Number',
        category_col: str = 'Quota Category',
        country_col: str = 'Country',
        template_limit_col: str = 'Template Quota Limit',
        delay: float = 0.3  # Kept for API compatibility, uses min/max_delay internally
    ) -> pd.DataFrame:
        """
        Fetch all UK quotas from input DataFrame using concurrent requests

        Args:
            quotas_df: DataFrame with quota order numbers
            order_col: Column name for order numbers
            category_col: Column name for quota category
            country_col: Column name for country
            template_limit_col: Column name for template quota limit
            delay: Base delay (for API compatibility)

        Returns:
            pd.DataFrame: Scraped data with calculated metrics
        """
        total = len(quotas_df)
        print(f"\n" + "=" * 60)
        print("UK QUOTA SCRAPER (Fast API Version)")
        print("=" * 60)
        print(f"Processing {total} UK quota rows...")

        # Identify unique order numbers to scrape
        unique_orders = quotas_df[order_col].dropna().unique()
        unique_orders = [str(o).zfill(6) for o in unique_orders if str(o) != 'UNKNOWN']
        print(f"Unique order numbers to fetch: {len(unique_orders)}")
        print(f"Concurrent workers: {self.max_workers}")

        # Cache for scraped data
        scraped_cache = {}
        success_count = 0
        fail_count = 0

        try:
            self._setup_session()

            # Use ThreadPoolExecutor for concurrent requests
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_order = {
                    executor.submit(self._fetch_with_delay, order): order
                    for order in unique_orders
                }

                # Process completed tasks
                for idx, future in enumerate(as_completed(future_to_order), 1):
                    order_number, quota_data = future.result()

                    if quota_data:
                        scraped_cache[order_number] = quota_data
                        balance = quota_data.get('current_balance_kg')
                        if balance is not None:
                            print(f"[{idx}/{len(unique_orders)}] {order_number}: {balance:,.0f} kg")
                        else:
                            print(f"[{idx}/{len(unique_orders)}] {order_number}: No data")
                        success_count += 1
                    else:
                        scraped_cache[order_number] = None
                        print(f"[{idx}/{len(unique_orders)}] {order_number}: FAILED")
                        fail_count += 1

        finally:
            self._close_session()

        print(f"\nFetch completed: {success_count} successful, {fail_count} failed")

        # Build results for ALL rows using cached data
        print(f"\nBuilding output for {total} rows...")
        results = []

        for idx, row in quotas_df.iterrows():
            raw_order = row[order_col]
            if pd.isna(raw_order) or str(raw_order) == 'UNKNOWN':
                continue

            order_number = str(raw_order).zfill(6)
            cached_data = scraped_cache.get(order_number)

            # Get template quota limit if available
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
                # Use API data
                scraped_opening_kg = cached_data.get('opening_balance_kg')
                scraped_current_kg = cached_data.get('current_balance_kg')

                if template_limit:
                    # Use template limit as opening balance (in kg)
                    opening_kg = template_limit * 1000

                    if is_individual_cap:
                        # For "*" countries, calculate proportionally
                        if scraped_current_kg is not None and scraped_opening_kg:
                            # Use scraped opening balance for proportion calculation
                            pct_remaining = scraped_current_kg / scraped_opening_kg if scraped_opening_kg > 0 else 1
                            row_data['opening_balance_kg'] = opening_kg
                            row_data['current_balance_kg'] = opening_kg * pct_remaining
                            row_data['allocated_kg'] = opening_kg - row_data['current_balance_kg']
                        else:
                            row_data['opening_balance_kg'] = opening_kg
                            row_data['current_balance_kg'] = opening_kg
                            row_data['allocated_kg'] = 0
                    else:
                        # Regular quota - use scraped current balance
                        row_data['opening_balance_kg'] = opening_kg
                        if scraped_current_kg is not None:
                            row_data['current_balance_kg'] = scraped_current_kg
                            row_data['allocated_kg'] = opening_kg - scraped_current_kg
                        else:
                            row_data['current_balance_kg'] = opening_kg
                            row_data['allocated_kg'] = 0
                else:
                    # No template - use scraped values directly
                    row_data['opening_balance_kg'] = scraped_opening_kg or scraped_current_kg
                    row_data['current_balance_kg'] = scraped_current_kg
                    row_data['allocated_kg'] = (scraped_opening_kg or 0) - (scraped_current_kg or 0)

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


# UK Quota Order Numbers Reference (Updated for 2026 Q1)
# Source: UK Trade Remedies Notices and UK Integrated Online Tariff
UK_QUOTA_ORDER_NUMBERS = {
    # Category 1A - Non-alloy hot-rolled sheet
    '1A_EU': '058001',
    '1A_Turkey': '058967',
    '1A_Taiwan': '058085',
    '1A_All_others': '058002',
    # Category 1B - Other alloy hot-rolled sheet (UPDATED 2026 Q1)
    # Old 058003 replaced with 3 sub-quotas
    '1B_All_others_1': '058110',
    '1B_All_others_2': '058111',
    '1B_All_others_3': '058112',
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
    # Category 13 - Rebar (UPDATED 2026 Q1)
    # Old 058019 replaced with 058020, new individual country quotas added
    '13_EU': '058018',
    '13_Turkey': '058866',
    '13_All_others': '058020',  # Changed from 058019
    '13_Egypt': '058131',       # NEW individual country
    '13_Vietnam': '058136',     # NEW individual country
    '13_Algeria': '058130',     # NEW individual country
    '13_New_Zealand': '058133', # NEW individual country
    '13_Norway': '058134',      # NEW individual country
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
