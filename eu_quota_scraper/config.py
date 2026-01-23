# -*- coding: utf-8 -*-
"""
EU Quota Scraper Configuration
Contains constants, URL patterns, and utility functions for quarter management

Author: Data Intern @ MEPS International
"""

from datetime import datetime, date

# Base URL for quota details page
BASE_URL = "https://ec.europa.eu/taxation_customs/dds2/taric/quota_tariff_details.jsp"

# Default language
LANGUAGE = "en"

# Fields to extract from quota details page
QUOTA_FIELDS = [
    'Order number',
    'Validity period',
    'Origin',
    'Initial amount',
    'Amount',
    'Balance',
    'Transferred Amount',
    'Exhaustion date',
    'Critical',
    'Last import date',
    'Last allocation date',
    'Total awaiting allocation (indicative)',
    'Blocking period',
    'Suspension period',
    'Allocated percentage at the last allocation'
]

# Special quotas with annual (not quarterly) management
# Add order numbers here that use annual periods
ANNUAL_QUOTAS = {
    # "order_number": "YYYY-MM-DD"  # Start date for annual quota
    # Example: Russian Slab quota - to be confirmed with user
}

# Quarterly start dates
QUARTER_START_MONTHS = {
    1: (1, 1),   # Q1: January 1
    2: (4, 1),   # Q2: April 1
    3: (7, 1),   # Q3: July 1
    4: (10, 1),  # Q4: October 1
}


def get_current_quarter() -> int:
    """
    Get the current quarter number (1-4)
    
    Returns:
        int: Quarter number (1=Jan-Mar, 2=Apr-Jun, 3=Jul-Sep, 4=Oct-Dec)
    """
    month = datetime.now().month
    return (month - 1) // 3 + 1


def get_current_quarter_start(reference_date: date = None) -> str:
    """
    Get the start date for the current quarter
    
    Args:
        reference_date: Optional date to use instead of today
        
    Returns:
        str: Date in YYYY-MM-DD format
    """
    if reference_date is None:
        reference_date = date.today()
    
    quarter = (reference_date.month - 1) // 3 + 1
    month, day = QUARTER_START_MONTHS[quarter]
    
    return f"{reference_date.year}-{month:02d}-{day:02d}"


def get_quarter_end(start_date_str: str) -> str:
    """
    Get the end date for a quarter given its start date
    
    Args:
        start_date_str: Quarter start date in YYYY-MM-DD format
        
    Returns:
        str: Quarter end date in YYYY-MM-DD format
    """
    year, month, _ = map(int, start_date_str.split('-'))
    
    # Calculate end month (3 months later, last day)
    if month == 1:
        return f"{year}-03-31"
    elif month == 4:
        return f"{year}-06-30"
    elif month == 7:
        return f"{year}-09-30"
    elif month == 10:
        return f"{year}-12-31"
    else:
        # For non-standard start dates (annual quotas)
        # Default to 12 months later
        end_year = year + 1
        end_month = month - 1 if month > 1 else 12
        if end_month in [4, 6, 9, 11]:
            end_day = 30
        elif end_month == 2:
            end_day = 28
        else:
            end_day = 31
        return f"{end_year}-{end_month:02d}-{end_day:02d}"


def build_quota_url(order_number: str, start_date: str) -> str:
    """
    Build the URL for a specific quota details page
    
    Args:
        order_number: Quota order number (e.g., '098967')
        start_date: Quarter start date in YYYY-MM-DD format
        
    Returns:
        str: Full URL to quota details page
    """
    return f"{BASE_URL}?Lang={LANGUAGE}&StartDate={start_date}&Code={order_number}"


def get_quota_start_date(order_number: str, reference_date: date = None) -> str:
    """
    Get the appropriate start date for a quota
    
    Handles both quarterly and annual quotas
    
    Args:
        order_number: Quota order number
        reference_date: Optional reference date (defaults to today)
        
    Returns:
        str: Start date in YYYY-MM-DD format
    """
    # Check if this is an annual quota with custom start date
    if order_number in ANNUAL_QUOTAS:
        return ANNUAL_QUOTAS[order_number]
    
    # Otherwise use current quarter start
    return get_current_quarter_start(reference_date)
