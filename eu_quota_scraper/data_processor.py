# -*- coding: utf-8 -*-
"""
EU Quota Data Processor
Cleans, transforms, and calculates derived metrics from scraped quota data

Author: Data Intern @ MEPS International
"""

import pandas as pd
from datetime import datetime, date
from typing import Optional


def parse_date(date_str: str, format_hint: str = 'dd-mm-yyyy') -> Optional[date]:
    """
    Parse date string to date object
    
    Args:
        date_str: Date string to parse
        format_hint: Expected format (dd-mm-yyyy or yyyy-mm-dd)
        
    Returns:
        date object or None if parsing fails
    """
    if not date_str or pd.isna(date_str):
        return None
    
    date_str = str(date_str).strip()
    
    # Try common formats
    formats = [
        '%d-%m-%Y',  # 12-01-2026
        '%Y-%m-%d',  # 2026-01-12
        '%d/%m/%Y',  # 12/01/2026
        '%Y/%m/%d',  # 2026/01/12
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    
    return None


def calculate_quota_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate derived quota metrics
    
    Adds the following columns:
    - quota_used: initial_amount - balance
    - quota_used_pct: (quota_used / initial_amount) * 100
    - quota_remaining_pct: (balance / initial_amount) * 100
    - days_remaining_in_quarter: validity_end - today
    
    Args:
        df: DataFrame with scraped quota data
        
    Returns:
        pd.DataFrame: Enhanced DataFrame with derived metrics
    """
    df = df.copy()
    
    # Calculate quota used
    if 'initial_amount' in df.columns and 'balance' in df.columns:
        df['quota_used'] = df['initial_amount'] - df['balance']
        
        # Calculate percentages
        df['quota_used_pct'] = (df['quota_used'] / df['initial_amount'] * 100).round(2)
        df['quota_remaining_pct'] = (df['balance'] / df['initial_amount'] * 100).round(2)
    
    # Calculate days remaining in quarter
    today = date.today()
    
    if 'validity_end' in df.columns:
        def calc_days_remaining(end_date_str):
            end_date = parse_date(end_date_str)
            if end_date:
                delta = end_date - today
                return max(0, delta.days)
            return None
        
        df['days_remaining_in_quarter'] = df['validity_end'].apply(calc_days_remaining)
    
    # Calculate daily burn rate (if we have allocation history)
    if 'quota_used' in df.columns and 'validity_start' in df.columns:
        def calc_burn_rate(row):
            start_date = parse_date(row.get('validity_start'))
            quota_used = row.get('quota_used')
            
            if start_date and quota_used and quota_used > 0:
                days_elapsed = (today - start_date).days
                if days_elapsed > 0:
                    return round(quota_used / days_elapsed, 2)
            return None
        
        df['daily_burn_rate'] = df.apply(calc_burn_rate, axis=1)
        
        # Estimate days until exhaustion at current rate
        def calc_days_until_exhaustion(row):
            balance = row.get('balance')
            burn_rate = row.get('daily_burn_rate')
            
            if balance and burn_rate and burn_rate > 0:
                return round(balance / burn_rate, 0)
            return None
        
        df['est_days_until_exhaustion'] = df.apply(calc_days_until_exhaustion, axis=1)
    
    return df


def clean_quota_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and standardize quota data
    
    Args:
        df: Raw scraped DataFrame
        
    Returns:
        pd.DataFrame: Cleaned DataFrame
    """
    df = df.copy()
    
    # Standardize column names
    df.columns = [col.lower().replace(' ', '_') for col in df.columns]
    
    # Convert numeric columns
    numeric_cols = ['initial_amount', 'amount', 'balance', 'transferred_amount',
                    'total_awaiting_allocation_(indicative)', 'allocated_percentage_at_the_last_allocation']
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Rename long column names for convenience
    rename_map = {
        'total_awaiting_allocation_(indicative)': 'awaiting_allocation',
        'allocated_percentage_at_the_last_allocation': 'allocation_pct',
    }
    
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    
    return df


def prepare_customer_report(df: pd.DataFrame, 
                           columns: Optional[list] = None) -> pd.DataFrame:
    """
    Prepare DataFrame for customer-facing report
    
    Selects and orders columns to match expected output format
    
    Args:
        df: Processed DataFrame
        columns: Optional list of columns to include
        
    Returns:
        pd.DataFrame: Customer-ready DataFrame
    """
    if columns is None:
        # Default columns for customer report
        columns = [
            'input_quota_category',
            'origin',
            'input_order_number',
            'initial_amount',
            'quota_used',
            'quota_used_pct',
            'balance',
            'quota_remaining_pct',
            'critical',
            'last_allocation_date',
            'days_remaining_in_quarter',
            'est_days_until_exhaustion',
        ]
    
    # Only include columns that exist
    available_cols = [c for c in columns if c in df.columns]
    
    result = df[available_cols].copy()
    
    # Format column headers for display
    display_names = {
        'input_quota_category': 'Product Category',
        'origin': 'Origin',
        'input_order_number': 'Order Number',
        'initial_amount': 'Initial Quota (kg)',
        'quota_used': 'Quota Used (kg)',
        'quota_used_pct': 'Used (%)',
        'balance': 'Remaining (kg)',
        'quota_remaining_pct': 'Remaining (%)',
        'critical': 'Critical',
        'last_allocation_date': 'Last Allocation',
        'days_remaining_in_quarter': 'Days Left in Quarter',
        'est_days_until_exhaustion': 'Est. Days to Exhaustion',
    }
    
    result = result.rename(columns={k: v for k, v in display_names.items() if k in result.columns})
    
    return result
