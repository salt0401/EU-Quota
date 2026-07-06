# -*- coding: utf-8 -*-
"""
UK Quota Scraper - Fast HTTP version using UK Trade Tariff API

Uses direct API calls (no browser needed).

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


def normalize_order_number(raw) -> str:
    """
    Normalize an order number to a 6-digit zero-padded string.

    Defends against pandas dtype drift in the input workbook: one blank cell
    in the Order Number column flips the dtype to float64, and a naive
    str(58600.0).zfill(6) would produce '58600.0' — silently breaking every
    API query. Handles int, float, and string ('058600') inputs.
    """
    return str(int(float(raw))).zfill(6)


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
            order_number: UK quota order number (e.g., '058600')

        Returns:
            dict: Quota data or None if failed
        """
        order_number = normalize_order_number(order_number)
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
        unique_orders = [normalize_order_number(o) for o in unique_orders if str(o) != 'UNKNOWN']
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

            order_number = normalize_order_number(raw_order)
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

            if cached_data and cached_data.get('status') == 'No Data':
                # API answered 200 but knows nothing about this order number:
                # there are no real figures, so treat it like a failed scrape
                # rather than silently rendering template values as live data.
                row_data['scrape_status'] = 'failed'
                row_data['status'] = 'No Data'
                row_data['scrape_timestamp'] = cached_data.get('scrape_timestamp')
                if template_limit:
                    opening_kg = template_limit * 1000
                    row_data['opening_balance_kg'] = opening_kg
                    row_data['current_balance_kg'] = opening_kg
                    row_data['allocated_kg'] = 0
            elif cached_data:
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


# UK Quota Order Numbers Reference — steel trade measure effective 1 July 2026
# (replaced the steel safeguard, whose 058001+ order numbers expired 30 June 2026).
# Source: DBT "UK's steel trade measure from 1 July 2026", Tables 3 & 4
# https://www.gov.uk/government/publications/uks-steel-trade-measure-from-1-july-2026/uks-steel-trade-measure-from-1-july-2026
# Category 1 also has a separate authorised-use quota whose order number is
# published only on the UK Integrated Online Tariff (not in Table 4).
UK_QUOTA_ORDER_NUMBERS = {
    # Category 1 - non-alloy and other alloy hot-rolled sheets and strips
    '1_European_Union': '058600',
    '1_India': '058601',
    '1_South_Korea': '058602',
    '1_Residual': '058603',
    # Category 1 authorised-use quota (Table 1 of the DBT notice; order
    # numbers published only on the UK Integrated Online Tariff, verified
    # live 2026-07-06; 058672 returns no data)
    '1_Authorised_Use_European_Union': '058673',
    '1_Authorised_Use_India': '058674',
    '1_Authorised_Use_Residual': '058675',
    # Category 4 - metallic coated sheets
    '4_European_Union': '058604',
    '4_India': '058605',
    '4_South_Korea': '058606',
    '4_Vietnam': '058607',
    '4_Residual': '058608',
    # Category 5 - organic coated sheets
    '5_European_Union': '058609',
    '5_South_Korea': '058610',
    '5_Residual': '058611',
    # Category 6 - tin mill products
    '6_European_Union': '058612',
    '6_Japan': '058613',
    '6_South_Korea': '058614',
    '6_Residual': '058615',
    # Category 7 - non-alloy and other alloy quarto plates
    '7_European_Union': '058616',
    '7_South_Korea': '058617',
    '7_United_States_of_America': '058618',
    '7_Residual': '058619',
    # Category 12A - alloy merchant bars and light sections
    '12A_European_Union': '058620',
    '12A_Residual': '058621',
    # Category 12B - non-alloy merchant bars and light sections
    '12B_European_Union': '058622',
    '12B_Turkey': '058623',
    '12B_Residual': '058624',
    # Category 13 - rebars
    '13_European_Union': '058625',
    '13_Turkey': '058626',
    '13_Residual': '058627',
    # Category 14 - stainless bars and light sections
    '14_European_Union': '058628',
    '14_United_States_of_America': '058629',
    '14_Residual': '058630',
    # Category 15 - stainless wire rod
    '15_European_Union': '058631',
    '15_South_Korea': '058632',
    '15_Residual': '058633',
    # Category 16 - non-alloy and other alloy wire rod
    '16_European_Union': '058634',
    '16_Residual': '058635',
    # Category 17 - angles, shapes, and sections of iron or non-alloy steel
    '17_European_Union': '058636',
    '17_South_Korea': '058637',
    '17_United_States_of_America': '058638',
    '17_Residual': '058639',
    # Category 19 - railway material
    '19_European_Union': '058640',
    '19_Residual': '058641',
    # Category 20 - gas pipes
    '20_European_Union': '058642',
    '20_India': '058643',
    '20_Turkey': '058644',
    '20_Residual': '058645',
    # Category 21 - hollow sections
    '21_European_Union': '058646',
    '21_Turkey': '058647',
    '21_Residual': '058648',
    # Category 25A - large welded tubes (1)
    '25A_European_Union': '058649',
    '25A_Japan': '058650',
    '25A_South_Korea': '058651',
    '25A_United_States_of_America': '058652',
    '25A_Residual': '058653',
    # Category 25B - large welded tubes (2)
    '25B_European_Union': '058654',
    '25B_Japan': '058655',
    '25B_South_Korea': '058656',
    '25B_Turkey': '058657',
    '25B_Residual': '058658',
    # Category 26 - other welded tubes
    '26_European_Union': '058659',
    '26_Switzerland': '058660',
    '26_Turkey': '058661',
    '26_United_Arab_Emirates': '058662',
    '26_United_States_of_America': '058663',
    '26_Residual': '058664',
    # Category 27 - non-alloy and other alloy cold finished bars
    '27_European_Union': '058665',
    '27_Turkey': '058666',
    '27_Residual': '058667',
    # Category 28 - non-alloy wire
    '28_European_Union': '058668',
    '28_Japan': '058669',
    '28_United_States_of_America': '058670',
    '28_Residual': '058671',
}
