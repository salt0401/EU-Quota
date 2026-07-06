# -*- coding: utf-8 -*-
"""
EU Quota Data Processor
Cleans, transforms, and calculates derived metrics from scraped quota data

IMPORTANT: Calculations follow MEPS template formulas:
- Quota Limit = amount + transferred_amount
- Balance Remaining = balance - awaiting_allocation
"""

import re
import pandas as pd
from datetime import datetime, date
from typing import Optional, Tuple

from .config import (
    parse_validity_period,
    format_period_display,
    detect_quarter_from_validity
)
from .utils import parse_date_string


def clean_quota_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and standardize quota data

    Args:
        df: Raw scraped DataFrame

    Returns:
        pd.DataFrame: Cleaned DataFrame with standardized column names
    """
    df = df.copy()

    # Standardize column names (lowercase, underscores). Collapse repeated
    # underscores and strip underscores inside parentheses: TARIC labels carry
    # doubled spaces / separate nodes (e.g. "Total awaiting allocation
    # (indicative)"), which otherwise produces variants like
    # 'total_awaiting_allocation__(indicative)' or '..._(_indicative_)' and
    # silently misses the rename below — zeroing awaiting_allocation in the
    # MEPS Balance Remaining formula.
    def _std(col):
        c = re.sub(r'_+', '_', str(col).lower().replace(' ', '_'))
        c = re.sub(r'\(_+', '(', c)
        c = re.sub(r'_+\)', ')', c)
        return c

    df.columns = [_std(col) for col in df.columns]

    # Convert numeric columns, ensuring 0 for empty values
    numeric_cols = [
        'initial_amount', 'amount', 'balance', 'transferred_amount',
        'total_awaiting_allocation_(indicative)',
        'allocated_percentage_at_the_last_allocation'
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Rename long column names for convenience
    rename_map = {
        'total_awaiting_allocation_(indicative)': 'awaiting_allocation',
        'allocated_percentage_at_the_last_allocation': 'allocation_pct',
    }

    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    return df


def calculate_quota_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate derived quota metrics using MEPS formulas

    MEPS Template Formulas:
    - quota_limit = amount + transferred_amount
    - balance_remaining = balance - awaiting_allocation
    - quota_allocated = quota_limit - balance_remaining

    Args:
        df: DataFrame with scraped quota data

    Returns:
        pd.DataFrame: Enhanced DataFrame with derived metrics
    """
    df = df.copy()

    # Ensure numeric columns exist with default 0
    for col in ['amount', 'transferred_amount', 'balance', 'awaiting_allocation', 'initial_amount']:
        if col not in df.columns:
            df[col] = 0
        else:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # MEPS Formula 1: Quota Limit = amount + transferred_amount
    df['quota_limit'] = df['amount'] + df['transferred_amount']

    # MEPS Formula 2: Balance Remaining = balance - awaiting_allocation
    df['balance_remaining'] = df['balance'] - df['awaiting_allocation']
    # Ensure balance_remaining is not negative
    df['balance_remaining'] = df['balance_remaining'].clip(lower=0)

    # Calculate quota allocated (what has been used)
    df['quota_allocated'] = df['quota_limit'] - df['balance_remaining']

    # Calculate percentages (avoid division by zero)
    df['pct_allocated'] = 0.0
    df['pct_remaining'] = 0.0

    mask = df['quota_limit'] > 0
    df.loc[mask, 'pct_allocated'] = (
        df.loc[mask, 'quota_allocated'] / df.loc[mask, 'quota_limit'] * 100
    ).round(2)
    df.loc[mask, 'pct_remaining'] = (
        df.loc[mask, 'balance_remaining'] / df.loc[mask, 'quota_limit'] * 100
    ).round(2)

    # Calculate days remaining in quarter
    today = date.today()

    if 'validity_end' in df.columns:
        def calc_days_remaining(end_date_str):
            if pd.isna(end_date_str):
                return None
            end_date = parse_date_string(str(end_date_str))
            if end_date:
                delta = end_date - today
                return max(0, delta.days)
            return None

        df['days_remaining'] = df['validity_end'].apply(calc_days_remaining)

    # Calculate daily burn rate
    if 'validity_start' in df.columns:
        def calc_burn_rate(row):
            start_str = row.get('validity_start')
            if pd.isna(start_str):
                return None

            start_date = parse_date_string(str(start_str))
            allocated = row.get('quota_allocated', 0)

            if start_date and allocated and allocated > 0:
                days_elapsed = (today - start_date).days
                if days_elapsed > 0:
                    return round(allocated / days_elapsed, 2)
            return None

        df['daily_burn_rate'] = df.apply(calc_burn_rate, axis=1)

        # Estimate days until exhaustion at current rate
        def calc_exhaustion_days(row):
            remaining = row.get('balance_remaining', 0)
            burn_rate = row.get('daily_burn_rate')

            if remaining and burn_rate and burn_rate > 0:
                return round(remaining / burn_rate, 0)
            return None

        df['est_days_to_exhaustion'] = df.apply(calc_exhaustion_days, axis=1)

    return df


def extract_period_info(df: pd.DataFrame) -> Tuple[str, str, int, int]:
    """
    Extract quota period information from scraped data

    Args:
        df: DataFrame with validity_period or validity_start/validity_end

    Returns:
        Tuple: (period_display, latest_data_date, quarter, year)
    """
    period_display = ""
    latest_data = date.today().strftime("%d-%b-%Y")
    quarter = 1
    year = date.today().year

    # Use the most common validity window across quotas (not just the first
    # row): under the post-July-2026 regime individual quotas can carry
    # different windows, and the banner should reflect the dominant one.
    if 'validity_start' in df.columns and 'validity_end' in df.columns:
        valid = df[df['validity_start'].notna() & df['validity_end'].notna()]
        if len(valid) > 0:
            pairs = valid['validity_start'].astype(str) + '|' + valid['validity_end'].astype(str)
            start, end = pairs.mode().iloc[0].split('|', 1)
            period_display = format_period_display(start, end)
            quarter, year = detect_quarter_from_validity(start)

    # Get latest scrape timestamp
    if 'scrape_timestamp' in df.columns:
        timestamps = df['scrape_timestamp'].dropna()
        if len(timestamps) > 0:
            try:
                latest_ts = max(timestamps)
                if isinstance(latest_ts, str):
                    dt = datetime.fromisoformat(latest_ts)
                    latest_data = dt.strftime("%d-%b-%Y")
            except Exception:
                pass

    return period_display, latest_data, quarter, year


def prepare_customer_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepare DataFrame for customer-facing MEPS report

    Selects and renames columns to match MEPS template format

    Args:
        df: Processed DataFrame with all metrics

    Returns:
        pd.DataFrame: Customer-ready DataFrame with proper column names
    """
    df = df.copy()

    # Exclude rows whose scrape failed: they carry no real figures and would
    # render as misleading 0-tonne / 0%-allocated rows in the customer sheet.
    # They remain in the raw-data output, and main.py reports the failures.
    if 'scrape_status' in df.columns:
        failed = df['scrape_status'] == 'failed'
        if failed.any():
            print(f"  Warning: excluding {int(failed.sum())} failed quota(s) "
                  f"from the customer report: "
                  f"{sorted(df.loc[failed, 'input_order_number'].astype(str))}")
            df = df[~failed]

    # Country display: prefer the curated input name (matches the regulation's
    # Annex I allocation labels, e.g. 'Türkiye', 'FTA Quota – CSQ'). The raw
    # TARIC origin text is unnormalized ('Korea, Republic of (South Korea)',
    # 'ERGA OMNES' with excluded-country lists appended) and stays available
    # in the raw-data output for verification.
    if 'input_country' in df.columns:
        df['_display_country'] = df['input_country']
        if 'origin' in df.columns:
            missing = df['_display_country'].isna() | (df['_display_country'].astype(str).str.strip() == '')
            df.loc[missing, '_display_country'] = df.loc[missing, 'origin']
    elif 'origin' in df.columns:
        df['_display_country'] = df['origin']

    # Column mapping: internal_name -> display_name
    column_mapping = {
        'input_quota_category': 'Quota Category',
        '_display_country': 'Country',
        'quota_limit': 'Quota Limit (Tonnes)',
        'quota_allocated': 'Quota Allocated (Tonnes)',
        'pct_allocated': '% Quota Allocated',
        'balance_remaining': 'Balance Remaining (Tonnes)',
        'pct_remaining': '% Balance Remaining',
    }

    # Select columns that exist
    available_cols = [c for c in column_mapping.keys() if c in df.columns]

    result = df[available_cols].copy()

    # Convert kg to tonnes (divide by 1000)
    tonnage_cols = ['quota_limit', 'quota_allocated', 'balance_remaining']
    for col in tonnage_cols:
        if col in result.columns:
            result[col] = (result[col] / 1000).round(2)

    # Percentages as 0-1 fractions for Excel '0%' formatting. The internal
    # metrics are on a 0-100 scale; converting here (not in the generator)
    # removes the value>1 guess that misrendered quotas below 1% allocated
    # as huge percentages — the common case right after a quarter opens.
    pct_cols = ['pct_allocated', 'pct_remaining']
    for col in pct_cols:
        if col in result.columns:
            result[col] = (result[col] / 100).round(4)

    # Rename columns for display
    result = result.rename(columns={k: v for k, v in column_mapping.items() if k in result.columns})

    return result


def get_quota_summary(df: pd.DataFrame) -> dict:
    """
    Generate summary statistics for the quota data

    Args:
        df: Processed DataFrame

    Returns:
        dict: Summary statistics
    """
    summary = {
        'total_quotas': len(df),
        'high_usage_count': 0,
        'critical_count': 0,
        'exhausted_count': 0,
    }

    if 'pct_allocated' in df.columns:
        summary['high_usage_count'] = len(df[df['pct_allocated'] > 75])

    if 'critical' in df.columns:
        summary['critical_count'] = df['critical'].sum()

    if 'pct_allocated' in df.columns:
        summary['exhausted_count'] = len(df[df['pct_allocated'] >= 100])

    return summary
