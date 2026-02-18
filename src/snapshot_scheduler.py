# -*- coding: utf-8 -*-
"""
Snapshot Scheduler - Daily auto-snapshot logic
Checks if today's snapshot exists and orchestrates the scrape if not.
"""

import glob
import os
from datetime import date

from src.utils import get_snapshot_folder, ensure_directories


def has_today_snapshot(snapshot_folder: str = None) -> bool:
    """
    Check if a snapshot for today already exists.

    Looks for files matching snapshot_YYYYMMDD_*.xlsx in the snapshot folder.

    Args:
        snapshot_folder: Path to snapshots directory (defaults to project snapshots folder)

    Returns:
        True if today's snapshot exists
    """
    if snapshot_folder is None:
        snapshot_folder = get_snapshot_folder()

    today_str = date.today().strftime("%Y%m%d")
    pattern = os.path.join(snapshot_folder, f"snapshot_{today_str}_*.xlsx")
    matches = glob.glob(pattern)
    return len(matches) > 0


def get_snapshot_count(snapshot_folder: str = None) -> int:
    """
    Count total snapshots collected so far.

    Useful for checking if we have enough data (30+ days) for Prophet training.

    Args:
        snapshot_folder: Path to snapshots directory

    Returns:
        Number of snapshot files found
    """
    if snapshot_folder is None:
        snapshot_folder = get_snapshot_folder()

    pattern = os.path.join(snapshot_folder, "snapshot_*.xlsx")
    return len(glob.glob(pattern))


def run_daily_snapshot(skip_uk: bool = False) -> dict:
    """
    Orchestrate the daily snapshot: check if already done, run scraper if not.

    Args:
        skip_uk: Skip UK scraping if True

    Returns:
        dict with keys:
            - 'status': 'skipped' | 'completed' | 'failed'
            - 'message': human-readable result
            - 'snapshot_count': total snapshots after this run
    """
    ensure_directories()
    snapshot_folder = get_snapshot_folder()

    if has_today_snapshot(snapshot_folder):
        count = get_snapshot_count(snapshot_folder)
        return {
            "status": "skipped",
            "message": f"Already scraped today. Total snapshots: {count}",
            "snapshot_count": count,
        }

    # Import here to avoid circular imports and heavy module loading when skipping
    from src.main import run_scraper

    try:
        result = run_scraper(skip_uk=skip_uk)

        if result is not None:
            count = get_snapshot_count(snapshot_folder)
            return {
                "status": "completed",
                "message": f"Scrape completed. Total snapshots: {count}",
                "snapshot_count": count,
            }
        else:
            return {
                "status": "failed",
                "message": "Scraper returned no data",
                "snapshot_count": get_snapshot_count(snapshot_folder),
            }
    except Exception as e:
        return {
            "status": "failed",
            "message": f"Scraper error: {e}",
            "snapshot_count": get_snapshot_count(snapshot_folder),
        }
