# -*- coding: utf-8 -*-
"""
EU Quota Scraper Package
Automated collection and reporting of EU steel tariff quota data
"""

from .config import (
    get_current_quarter,
    get_current_quarter_start,
    get_quarter_dates,
    get_quarter_label,
    build_quota_url
)
from .scraper import EUQuotaScraper
from .uk_scraper import UKQuotaScraper  # Skeleton - not yet implemented
from .data_processor import (
    calculate_quota_metrics,
    clean_quota_data,
    prepare_customer_data
)
from .excel_generator import generate_meps_report
from .utils import get_output_folder, ensure_directories

__version__ = "2.0.0"
__all__ = [
    "EUQuotaScraper",
    "UKQuotaScraper",  # Skeleton - not yet implemented
    "get_current_quarter",
    "get_current_quarter_start",
    "get_quarter_dates",
    "get_quarter_label",
    "build_quota_url",
    "calculate_quota_metrics",
    "clean_quota_data",
    "prepare_customer_data",
    "generate_meps_report",
    "get_output_folder",
    "ensure_directories"
]
