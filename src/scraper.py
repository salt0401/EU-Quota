# -*- coding: utf-8 -*-
"""
EU Quota Scraper - Fast HTTP version using requests + BeautifulSoup

Uses direct HTTP requests (no browser needed): the EU TARIC website serves
data as server-rendered HTML, so we can parse it directly without
JavaScript execution.
"""

import re
import time
import random
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import build_quota_url, get_current_quarter_start, EU_QUOTA_FIELDS


class EUQuotaScraper:
    """
    Fast HTTP-based scraper for EU TARIC tariff quota details

    This version is 5-10x faster than the Selenium version because:
    - Direct HTTP requests (no browser overhead)
    - BeautifulSoup parsing (lightweight HTML parsing)
    - Concurrent requests with ThreadPoolExecutor

    Example:
        scraper = EUQuotaScraper()
        data = scraper.fetch_quota('098967', '2026-01-01')
    """

    def __init__(self, max_workers: int = 5, min_delay: float = 0.3, max_delay: float = 0.8, headless: bool = True):
        """
        Initialize the EU Quota scraper

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
        # Keep headless parameter for API compatibility with Selenium version
        self.headless = headless

    def _setup_session(self):
        """Setup requests session with appropriate headers"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        })

    def _close_session(self):
        """Close the requests session"""
        if self.session:
            self.session.close()
            self.session = None

    # Aliases for Selenium API compatibility
    def _setup_driver(self):
        """Alias for _setup_session (Selenium API compatibility)"""
        self._setup_session()

    def _close_driver(self):
        """Alias for _close_session (Selenium API compatibility)"""
        self._close_session()

    def _random_delay(self):
        """Add random delay to avoid detection"""
        time.sleep(random.uniform(self.min_delay, self.max_delay))

    def _parse_value(self, raw_value: str, field_name: str) -> any:
        """
        Parse and clean raw value from the page

        Args:
            raw_value: Raw string value from the page
            field_name: Name of the field for context

        Returns:
            Parsed value (str, float, bool, or None)
        """
        if not raw_value or raw_value.strip() == '':
            return None

        value = raw_value.strip()

        # Handle fields with units (e.g., "469492100 Kilogram")
        numeric_fields = ['Initial amount', 'Amount', 'Balance', 'Transferred Amount',
                         'Total awaiting allocation (indicative)']
        if field_name in numeric_fields:
            # Extract numeric part and unit
            match = re.match(r'^([\d,\.]+)\s*(.*)$', value)
            if match:
                num_str = match.group(1).replace(',', '')
                try:
                    return float(num_str)
                except ValueError:
                    return value
            return 0.0  # Return 0 for empty numeric fields

        # Handle percentage fields
        if field_name == 'Allocated percentage at the last allocation':
            try:
                return float(value)
            except ValueError:
                return value

        # Handle boolean fields
        if field_name == 'Critical':
            return value.lower() == 'yes'

        # Handle date fields
        if 'date' in field_name.lower():
            return value

        return value

    def fetch_quota(self, order_number: str, start_date: str) -> Optional[Dict]:
        """
        Fetch quota details for a single order number

        Args:
            order_number: Quota order number (e.g., '098967')
            start_date: Quarter start date in YYYY-MM-DD format

        Returns:
            dict: Parsed quota data, or None if failed
        """
        url = build_quota_url(order_number, start_date)

        try:
            if self.session is None:
                self._setup_session()

            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(response.text, 'lxml')

            # Find the quota details table
            table = soup.find('table', class_='ecl-table table-result')
            if not table:
                return None

            data = {
                'scrape_timestamp': datetime.now().isoformat(),
                'url': url,
            }

            # Find all table rows
            rows = table.find_all('tr', class_='ecl-table__row')

            for row in rows:
                try:
                    # Get label (first td with class 'label')
                    label_td = row.find('td', class_='label')
                    if not label_td:
                        continue

                    # Collapse all whitespace (incl. NBSP) — TARIC labels can
                    # contain doubled spaces, which would corrupt column names.
                    # The '(indicative)' part sits in its own HTML node, so also
                    # strip the spaces the separator introduces inside parens.
                    label = re.sub(r'\s+', ' ', label_td.get_text(separator=' ', strip=True))
                    label = re.sub(r'\(\s+', '(', label)
                    label = re.sub(r'\s+\)', ')', label)

                    # Get value (second td)
                    tds = row.find_all('td')
                    if len(tds) >= 2:
                        value_td = tds[1]
                        # separator=' ' keeps multi-span cells (e.g. origin +
                        # excluded-country lists) from mashing words together
                        value = re.sub(r'\s+', ' ', value_td.get_text(separator=' ', strip=True))

                        # Parse and store the value
                        parsed_value = self._parse_value(value, label)

                        # Normalize field name for consistent column names
                        field_name = re.sub(r'\s+', '_', label).lower()
                        data[field_name] = parsed_value

                except Exception:
                    continue

            # Extract validity period into start and end dates.
            # TARIC renders the separator with NBSP/newlines, so match the two
            # DD-MM-YYYY dates directly instead of splitting on ' - '.
            if 'validity_period' in data and data['validity_period']:
                try:
                    dates = re.findall(r'\d{2}-\d{2}-\d{4}', str(data['validity_period']))
                    if len(dates) >= 2:
                        data['validity_start'] = dates[0]
                        data['validity_end'] = dates[1]
                except Exception:
                    pass

            return data

        except requests.exceptions.RequestException as e:
            print(f"    Error fetching {order_number}: {e}")
            return None
        except Exception as e:
            print(f"    Error parsing {order_number}: {e}")
            return None

    def _fetch_with_info(self, order_number: str, start_date: str, source_info: dict) -> tuple:
        """Fetch quota with source info (for concurrent execution)"""
        print(f"  Fetching quota {order_number}...")
        result = self.fetch_quota(order_number, start_date)
        self._random_delay()

        if result:
            print(f"    Success: order {order_number}")
            return order_number, {**source_info, **result}
        else:
            print(f"    Failed: order {order_number}")
            source_info['scrape_status'] = 'failed'
            source_info['scrape_timestamp'] = datetime.now().isoformat()
            return order_number, source_info

    def fetch_all_quotas(self, quotas_df: pd.DataFrame,
                         order_col: str = 'Order Number',
                         date_col: str = 'Current Quarter') -> pd.DataFrame:
        """
        Fetch quota details for all order numbers in a DataFrame

        Uses concurrent requests with ThreadPoolExecutor for speed.

        Args:
            quotas_df: DataFrame containing order numbers and start dates
            order_col: Column name for order numbers
            date_col: Column name for start dates

        Returns:
            pd.DataFrame: DataFrame with all scraped quota data
        """
        total = len(quotas_df)
        print(f"\nProcessing {total} quotas (Fast HTTP version)...")
        print(f"Concurrent workers: {self.max_workers}")

        # Prepare tasks
        tasks = []
        for idx, row in quotas_df.iterrows():
            # Format order number - ensure 6 digits with leading zeros
            raw_order = row[order_col]
            if pd.notna(raw_order):
                order_number = str(int(raw_order)).zfill(6)
            else:
                continue

            # Format start date - handle various date formats
            raw_date = row[date_col]
            if pd.notna(raw_date):
                if hasattr(raw_date, 'strftime'):
                    start_date = raw_date.strftime('%Y-%m-%d')
                else:
                    start_date = str(raw_date)[:10]
            else:
                start_date = get_current_quarter_start()  # Default to current quarter

            # Build source info from input
            source_info = {
                'input_order_number': order_number,
                'input_start_date': start_date,
            }

            # Add other columns from input if present
            for col in quotas_df.columns:
                if col not in [order_col, date_col]:
                    source_info[f'input_{col.lower().replace(" ", "_")}'] = row[col]

            tasks.append((order_number, start_date, source_info))

        results = []
        success_count = 0
        fail_count = 0

        try:
            self._setup_session()

            # Use ThreadPoolExecutor for concurrent requests
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submit all tasks
                future_to_order = {
                    executor.submit(self._fetch_with_info, order, date, info): order
                    for order, date, info in tasks
                }

                # Process completed tasks
                for idx, future in enumerate(as_completed(future_to_order), 1):
                    order_number, result = future.result()
                    results.append(result)

                    if result.get('scrape_status') != 'failed':
                        success_count += 1
                    else:
                        fail_count += 1

                    # Progress indicator
                    print(f"[{idx}/{total}] Completed")

        finally:
            self._close_session()

        print(f"\nCompleted: {success_count} successful, {fail_count} failed")

        return pd.DataFrame(results)

    def __enter__(self):
        """Context manager entry"""
        self._setup_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self._close_session()
        return False
