#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Daily Snapshot - Entry point for automated daily scraping.

Designed to be run by Windows Task Scheduler on login.
Checks if today's snapshot exists; if not, runs the full scraper pipeline
and logs the result.

Usage:
    python daily_snapshot.py          # Run with console output
    pythonw daily_snapshot.py         # Run silently (Task Scheduler)
"""

import sys
import os
import logging
from datetime import date

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils import get_logs_folder
from src.snapshot_scheduler import run_daily_snapshot


def setup_logging() -> logging.Logger:
    """Configure logging to daily log file."""
    logs_folder = get_logs_folder()
    os.makedirs(logs_folder, exist_ok=True)

    today_str = date.today().strftime("%Y%m%d")
    log_path = os.path.join(logs_folder, f"daily_{today_str}.log")

    logger = logging.getLogger("daily_snapshot")
    logger.setLevel(logging.INFO)

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
    logger.addHandler(handler)

    return logger


def main():
    logger = setup_logging()
    logger.info("Daily snapshot started")

    result = run_daily_snapshot(skip_uk=False)

    logger.info(f"Status: {result['status']}")
    logger.info(f"Message: {result['message']}")
    logger.info(f"Snapshot count: {result['snapshot_count']}")

    # Print to console too (visible when run manually, ignored by pythonw)
    print(f"[{result['status'].upper()}] {result['message']}")

    if result["snapshot_count"] >= 30:
        msg = "30+ snapshots collected — ready for Prophet training!"
        logger.info(msg)
        print(msg)


if __name__ == "__main__":
    main()
