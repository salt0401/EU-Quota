#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
EU Quota Scraper - Run Script

This is a convenience wrapper to run the scraper from the project root.
The actual implementation is in src/main.py.

Usage:
    python run.py                     # Scrape both EU and UK
    python run.py --skip-uk           # Scrape EU only
    python run.py -i eu.xlsx -u uk.xlsx -o output.xlsx
"""

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.main import main

if __name__ == "__main__":
    main()
