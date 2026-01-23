# -*- coding: utf-8 -*-
"""
EU Quota Scraper - Core Scraping Module
Selenium-based scraper for EU TARIC quota details

Author: Data Intern @ MEPS International
"""

import re
import time
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, List

from .config import build_quota_url, QUOTA_FIELDS


class EUQuotaScraper:
    """
    Selenium-based scraper for EU TARIC tariff quota details
    
    Uses browser automation to navigate to quota pages and extract
    data from the table structure.
    
    Example:
        scraper = EUQuotaScraper()
        data = scraper.fetch_quota('098967', '2026-01-01')
        print(data)
    """
    
    def __init__(self, headless: bool = True):
        """
        Initialize the EU Quota scraper
        
        Args:
            headless: Run browser in headless mode (no visible window)
        """
        self.headless = headless
        self.driver = None
    
    def _setup_driver(self):
        """
        Set up Selenium WebDriver with Chrome
        
        Uses webdriver-manager to automatically handle ChromeDriver installation
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.chrome.options import Options
            from webdriver_manager.chrome import ChromeDriverManager
        except ImportError as e:
            print("❌ Missing dependencies. Please install:")
            print("   pip install selenium webdriver-manager")
            raise e
        
        options = Options()
        if self.headless:
            options.add_argument('--headless=new')
        
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
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
        """Close the browser driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
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
        if field_name in ['Initial amount', 'Amount', 'Balance', 'Transferred Amount', 'Total awaiting allocation (indicative)']:
            # Extract numeric part and unit
            match = re.match(r'^([\d,\.]+)\s*(.*)$', value)
            if match:
                num_str = match.group(1).replace(',', '')
                try:
                    return float(num_str)
                except ValueError:
                    return value
            return None
        
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
            # Keep as string for now - will be parsed in data processor
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
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        
        url = build_quota_url(order_number, start_date)
        print(f"🔄 Fetching quota {order_number}...")
        
        try:
            if self.driver is None:
                self._setup_driver()
            
            self.driver.get(url)
            time.sleep(2)  # Allow page to load
            
            # Wait for the table to be present
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table.ecl-table.table-result"))
                )
            except Exception:
                print(f"   ⚠️ Table not found for order {order_number}")
                return None
            
            # Find all table rows
            rows = self.driver.find_elements(By.CSS_SELECTOR, "table.ecl-table.table-result tr.ecl-table__row")
            
            data = {
                'scrape_timestamp': datetime.now().isoformat(),
                'url': url,
            }
            
            for row in rows:
                try:
                    # Get label (first td with class 'label')
                    label_elem = row.find_element(By.CSS_SELECTOR, "td.label")
                    label = label_elem.text.strip()
                    
                    # Get value (second td)
                    value_elems = row.find_elements(By.CSS_SELECTOR, "td")
                    if len(value_elems) >= 2:
                        value_elem = value_elems[1]
                        value = value_elem.text.strip()
                        
                        # Parse and store the value
                        parsed_value = self._parse_value(value, label)
                        
                        # Normalize field name for consistent column names
                        field_name = label.replace(' ', '_').lower()
                        data[field_name] = parsed_value
                        
                except Exception:
                    continue
            
            # Extract validity period into start and end dates
            if 'validity_period' in data and data['validity_period']:
                try:
                    period = data['validity_period']
                    if ' - ' in period:
                        start, end = period.split(' - ')
                        data['validity_start'] = start.strip()
                        data['validity_end'] = end.strip()
                except Exception:
                    pass
            
            print(f"   ✅ Successfully scraped order {order_number}")
            return data
            
        except Exception as e:
            print(f"   ❌ Error fetching {order_number}: {e}")
            return None
    
    def fetch_all_quotas(self, quotas_df: pd.DataFrame, 
                         order_col: str = 'Order Number',
                         date_col: str = 'Current Quarter Start Date') -> pd.DataFrame:
        """
        Fetch quota details for all order numbers in a DataFrame
        
        Args:
            quotas_df: DataFrame containing order numbers and start dates
            order_col: Column name for order numbers
            date_col: Column name for start dates
            
        Returns:
            pd.DataFrame: DataFrame with all scraped quota data
        """
        print(f"\n📊 Processing {len(quotas_df)} quotas...")
        
        results = []
        
        try:
            self._setup_driver()
            
            for idx, row in quotas_df.iterrows():
                # Format order number - ensure 6 digits with leading zeros
                raw_order = row[order_col]
                if pd.notna(raw_order):
                    order_number = str(int(raw_order)).zfill(6)
                else:
                    continue  # Skip rows with no order number
                
                # Format start date - handle various date formats
                raw_date = row[date_col]
                if pd.notna(raw_date):
                    if hasattr(raw_date, 'strftime'):
                        start_date = raw_date.strftime('%Y-%m-%d')
                    else:
                        start_date = str(raw_date)[:10]
                else:
                    start_date = '2026-01-01'  # Default to Q1 2026
                
                # Add source info from input
                source_info = {
                    'input_order_number': order_number,
                    'input_start_date': start_date,
                }
                
                # Add other columns from input if present
                for col in quotas_df.columns:
                    if col not in [order_col, date_col]:
                        source_info[f'input_{col.lower().replace(" ", "_")}'] = row[col]
                
                # Fetch quota data
                quota_data = self.fetch_quota(order_number, start_date)
                
                if quota_data:
                    # Merge source info with scraped data
                    combined = {**source_info, **quota_data}
                    results.append(combined)
                else:
                    # Still record the attempt with error status
                    source_info['scrape_status'] = 'failed'
                    source_info['scrape_timestamp'] = datetime.now().isoformat()
                    results.append(source_info)
                
                # Small delay between requests to be respectful
                time.sleep(1)
            
        finally:
            self._close_driver()
        
        print(f"\n✅ Completed: {len([r for r in results if 'order_number' in r])}/{len(quotas_df)} successful")
        
        return pd.DataFrame(results)
    
    def __enter__(self):
        """Context manager entry"""
        self._setup_driver()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self._close_driver()
        return False
