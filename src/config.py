# -*- coding: utf-8 -*-
"""
EU Quota Scraper Configuration
Contains constants, URL patterns, and utility functions for quarter management
"""

from datetime import datetime, date
from typing import Tuple, Optional

# Base URL for EU TARIC quota details page
EU_BASE_URL = "https://ec.europa.eu/taxation_customs/dds2/taric/quota_tariff_details.jsp"

# UK quota base URL (for future implementation)
UK_BASE_URL = "https://www.trade-tariff.service.gov.uk/quota_search"

# Default language
LANGUAGE = "en"

# Fields to extract from EU quota details page
EU_QUOTA_FIELDS = [
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

# Quarter definitions
QUARTER_INFO = {
    1: {"months": (1, 2, 3), "start": (1, 1), "end": (3, 31), "label": "Q1 (Jan-Mar)"},
    2: {"months": (4, 5, 6), "start": (4, 1), "end": (6, 30), "label": "Q2 (Apr-Jun)"},
    3: {"months": (7, 8, 9), "start": (7, 1), "end": (9, 30), "label": "Q3 (Jul-Sep)"},
    4: {"months": (10, 11, 12), "start": (10, 1), "end": (12, 31), "label": "Q4 (Oct-Dec)"},
}

# Month names for display
MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
}


def get_current_quarter(reference_date: Optional[date] = None) -> int:
    """
    Get the current quarter number (1-4)

    Args:
        reference_date: Optional date to use instead of today

    Returns:
        int: Quarter number (1=Jan-Mar, 2=Apr-Jun, 3=Jul-Sep, 4=Oct-Dec)
    """
    if reference_date is None:
        reference_date = date.today()

    month = reference_date.month
    return (month - 1) // 3 + 1


def get_current_quarter_start(reference_date: Optional[date] = None) -> str:
    """
    Get the start date for the current quarter

    Args:
        reference_date: Optional date to use instead of today

    Returns:
        str: Date in YYYY-MM-DD format
    """
    if reference_date is None:
        reference_date = date.today()

    quarter = get_current_quarter(reference_date)
    month, day = QUARTER_INFO[quarter]["start"]

    return f"{reference_date.year}-{month:02d}-{day:02d}"


def get_quarter_dates(reference_date: Optional[date] = None) -> Tuple[str, str]:
    """
    Get both start and end dates for the current quarter

    Args:
        reference_date: Optional date to use instead of today

    Returns:
        Tuple[str, str]: (start_date, end_date) in YYYY-MM-DD format
    """
    if reference_date is None:
        reference_date = date.today()

    quarter = get_current_quarter(reference_date)
    start_month, start_day = QUARTER_INFO[quarter]["start"]
    end_month, end_day = QUARTER_INFO[quarter]["end"]

    start_date = f"{reference_date.year}-{start_month:02d}-{start_day:02d}"
    end_date = f"{reference_date.year}-{end_month:02d}-{end_day:02d}"

    return start_date, end_date


def get_quarter_label(reference_date: Optional[date] = None) -> str:
    """
    Get a human-readable quarter label

    Args:
        reference_date: Optional date to use instead of today

    Returns:
        str: Label like "Q4 2025 (Oct-Dec)"
    """
    if reference_date is None:
        reference_date = date.today()

    quarter = get_current_quarter(reference_date)
    return f"Q{quarter} {reference_date.year} ({QUARTER_INFO[quarter]['label'].split('(')[1]}"


def parse_validity_period(validity_str: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse validity period string into start and end dates

    Args:
        validity_str: String like "01-01-2026  -  31-03-2026"

    Returns:
        Tuple[str, str]: (start_date, end_date) in DD-MM-YYYY format, or (None, None)
    """
    if not validity_str or ' - ' not in validity_str:
        return None, None

    try:
        parts = validity_str.split(' - ')
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    except Exception:
        pass

    return None, None


def format_period_display(start_str: str, end_str: str) -> str:
    """
    Format period dates for display

    Args:
        start_str: Start date in DD-MM-YYYY format
        end_str: End date in DD-MM-YYYY format

    Returns:
        str: Formatted string like "01-Oct-2025 to 31-Dec-2025"
    """
    try:
        # Parse dates
        start_parts = start_str.split('-')
        end_parts = end_str.split('-')

        start_day = int(start_parts[0])
        start_month = int(start_parts[1])
        start_year = int(start_parts[2])

        end_day = int(end_parts[0])
        end_month = int(end_parts[1])
        end_year = int(end_parts[2])

        start_formatted = f"{start_day:02d}-{MONTH_NAMES[start_month]}-{start_year}"
        end_formatted = f"{end_day:02d}-{MONTH_NAMES[end_month]}-{end_year}"

        return f"{start_formatted} to {end_formatted}"
    except Exception:
        return f"{start_str} to {end_str}"


def build_quota_url(order_number: str, start_date: str, region: str = "eu") -> str:
    """
    Build the URL for a specific quota details page

    Args:
        order_number: Quota order number (e.g., '098967')
        start_date: Quarter start date in YYYY-MM-DD format
        region: 'eu' or 'uk' (uk not yet implemented)

    Returns:
        str: Full URL to quota details page
    """
    if region.lower() == "eu":
        return f"{EU_BASE_URL}?Lang={LANGUAGE}&StartDate={start_date}&Code={order_number}"
    else:
        # UK implementation placeholder
        raise NotImplementedError("UK quota scraping not yet implemented")


def detect_quarter_from_validity(validity_start: str) -> Tuple[int, int]:
    """
    Detect which quarter a validity period belongs to

    Args:
        validity_start: Start date in DD-MM-YYYY format

    Returns:
        Tuple[int, int]: (quarter_number, year)
    """
    try:
        parts = validity_start.split('-')
        day = int(parts[0])
        month = int(parts[1])
        year = int(parts[2])

        quarter = (month - 1) // 3 + 1
        return quarter, year
    except Exception:
        # Default to current quarter
        today = date.today()
        return get_current_quarter(today), today.year
