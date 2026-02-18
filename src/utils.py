# -*- coding: utf-8 -*-
"""
EU Quota Scraper Utilities
Helper functions for file management and date handling
"""

import os
from datetime import datetime, date
from typing import Optional


def get_project_root() -> str:
    """Get the project root directory (works both as script and as PyInstaller exe)"""
    import sys
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running as script
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_output_folder(scrape_date: Optional[date] = None) -> str:
    """
    Get the output folder path for a specific scraping date

    Creates folder structure: data/output/YYYY-MM-DD/

    Args:
        scrape_date: Date for the folder name (defaults to today)

    Returns:
        str: Full path to the output folder
    """
    if scrape_date is None:
        scrape_date = date.today()

    date_str = scrape_date.strftime("%Y-%m-%d")
    root = get_project_root()
    return os.path.join(root, "data", "output", date_str)


def get_snapshot_folder() -> str:
    """Get the snapshots folder path"""
    root = get_project_root()
    return os.path.join(root, "data", "snapshots")


def get_input_folder() -> str:
    """Get the input folder path"""
    root = get_project_root()
    return os.path.join(root, "data", "input")


def get_logs_folder() -> str:
    """Get the logs folder path"""
    root = get_project_root()
    return os.path.join(root, "data", "logs")


def get_templates_folder() -> str:
    """Get the templates folder path"""
    root = get_project_root()
    return os.path.join(root, "templates")


def ensure_directories(scrape_date: Optional[date] = None) -> dict:
    """
    Ensure all required directories exist

    Args:
        scrape_date: Date for the output folder

    Returns:
        dict: Paths to all directories
    """
    paths = {
        "output": get_output_folder(scrape_date),
        "snapshots": get_snapshot_folder(),
        "input": get_input_folder(),
        "templates": get_templates_folder(),
        "logs": get_logs_folder(),
    }

    for name, path in paths.items():
        os.makedirs(path, exist_ok=True)

    return paths


def generate_output_filename(prefix: str, scrape_date: Optional[date] = None,
                            extension: str = "xlsx") -> str:
    """
    Generate a standardized output filename

    Args:
        prefix: File prefix (e.g., "eu_quota_report")
        scrape_date: Date for the filename
        extension: File extension

    Returns:
        str: Filename like "eu_quota_report_20260123.xlsx"
    """
    if scrape_date is None:
        scrape_date = date.today()

    date_str = scrape_date.strftime("%Y%m%d")
    return f"{prefix}_{date_str}.{extension}"


def format_date_display(date_obj: date) -> str:
    """
    Format a date for display

    Args:
        date_obj: Date object

    Returns:
        str: Formatted string like "23-Jan-2026"
    """
    months = {
        1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
    }
    return f"{date_obj.day:02d}-{months[date_obj.month]}-{date_obj.year}"


def parse_date_string(date_str: str) -> Optional[date]:
    """
    Parse various date string formats to date object

    Supported formats:
    - DD-MM-YYYY
    - YYYY-MM-DD
    - DD/MM/YYYY
    - YYYY/MM/DD

    Args:
        date_str: Date string to parse

    Returns:
        date object or None if parsing fails
    """
    if not date_str:
        return None

    date_str = str(date_str).strip()

    formats = [
        '%d-%m-%Y',
        '%Y-%m-%d',
        '%d/%m/%Y',
        '%Y/%m/%d',
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue

    return None


def get_latest_output_folder() -> Optional[str]:
    """
    Get the most recent output folder

    Returns:
        str: Path to latest output folder, or None if no folders exist
    """
    root = get_project_root()
    output_base = os.path.join(root, "data", "output")

    if not os.path.exists(output_base):
        return None

    folders = []
    for name in os.listdir(output_base):
        folder_path = os.path.join(output_base, name)
        if os.path.isdir(folder_path):
            # Check if folder name matches YYYY-MM-DD format
            try:
                datetime.strptime(name, "%Y-%m-%d")
                folders.append((name, folder_path))
            except ValueError:
                continue

    if not folders:
        return None

    # Sort by date string (works because YYYY-MM-DD is sortable)
    folders.sort(key=lambda x: x[0], reverse=True)
    return folders[0][1]
