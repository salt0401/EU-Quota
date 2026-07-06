# -*- coding: utf-8 -*-
"""
EU Quota Scraper - Main Entry Point
Automated collection of EU steel tariff quota data

Author: MEPS International

Usage:
    python -m src.main
    python run.py
    python run.py -i custom_input.xlsx -o custom_output.xlsx
"""

import os
import sys
import argparse
import pandas as pd
from datetime import datetime, date

# Add project root to path (parent of src/)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import (
    EUQuotaScraper,
    UKQuotaScraper,
    get_current_quarter_start,
    calculate_quota_metrics,
    clean_quota_data,
    prepare_customer_data,
    generate_meps_report
)
from src.data_processor import extract_period_info, get_quota_summary
from src.excel_generator import save_raw_data, save_snapshot
from src.utils import (
    get_output_folder,
    get_snapshot_folder,
    get_input_folder,
    ensure_directories,
    generate_output_filename,
    format_date_display
)


# Default input filenames
DEFAULT_INPUT_FILE = "quota_urls.xlsx"
DEFAULT_UK_INPUT_FILE = "uk_quota_urls.xlsx"


def load_quota_urls(filepath: str) -> pd.DataFrame:
    """
    Load quota order numbers from Excel file

    Args:
        filepath: Path to Excel file with quota URLs

    Returns:
        pd.DataFrame with order numbers and metadata
    """
    print(f"Loading quota list from: {filepath}")

    def is_valid_header(columns):
        """Check if columns contain 'Order Number' as a column name"""
        for col in columns:
            col_str = str(col).lower().strip()
            # Must be "order number" not just contain "order" (to avoid matching URLs)
            if col_str == 'order number' or col_str == 'order_number':
                return True
        return False

    # Try to auto-detect header row by looking for "Order Number" column
    # Prioritize row 5 (index 4) which is the standard format
    for header_row in [4, 0, 1, 2, 3, 5]:
        try:
            df = pd.read_excel(filepath, header=header_row)
            if is_valid_header(df.columns):
                print(f"  Found header at row {header_row + 1}")
                break
        except Exception:
            continue
    else:
        # Default to row 5 if no header found
        df = pd.read_excel(filepath, header=4)
        print(f"  Using default header at row 5")

    # Filter out rows with NaN in the order number column
    order_col = None
    for col in df.columns:
        col_str = str(col).lower().strip()
        if col_str == 'order number' or col_str == 'order_number':
            order_col = col
            break

    if order_col:
        df = df[df[order_col].notna()]

    print(f"  Found {len(df)} quotas to process")

    return df


def run_scraper(
    input_file: str = None,
    output_file: str = None,
    scrape_date: date = None,
    uk_input_file: str = None,
    skip_uk: bool = False,
    publish: bool = False
) -> pd.DataFrame:
    """
    Main scraping workflow

    Args:
        input_file: Path to input Excel file with EU quota URLs
        output_file: Optional custom filename for output
        scrape_date: Date for output folder (defaults to today)
        uk_input_file: Path to UK quota URLs file (optional)
        skip_uk: Skip UK scraping if True
        publish: Also update data/published/ (latest report, daily history
                 CSV/XLSX, metadata) — used by the daily GitHub Actions run

    Returns:
        pd.DataFrame: Scraped and processed EU data
    """
    print("""
    ================================================================
       EU/UK Quota Scraper - Steel Tariff Quota Tracker v2.1
    ================================================================
    """)

    if scrape_date is None:
        scrape_date = date.today()

    # Ensure directories exist
    paths = ensure_directories(scrape_date)
    output_folder = paths["output"]

    print(f"Output folder: {output_folder}")

    # Determine input file
    if input_file is None:
        input_file = os.path.join(get_input_folder(), DEFAULT_INPUT_FILE)

    if not os.path.exists(input_file):
        print(f"Error: Input file not found: {input_file}")
        return None

    # Load quota URLs
    quotas_df = load_quota_urls(input_file)

    # Display current quarter info
    quarter_start = get_current_quarter_start()
    print(f"\nCurrent quarter start: {quarter_start}")
    print(f"Processing {len(quotas_df)} quotas...")

    # Initialize scraper and fetch data
    print("\n" + "=" * 60)
    print("Starting data collection...")
    print("=" * 60)

    scraper = EUQuotaScraper(headless=True)

    # Determine column names (handle different Excel formats)
    order_col = None
    date_col = None

    for col in quotas_df.columns:
        col_lower = str(col).lower()
        if 'order' in col_lower and 'number' in col_lower:
            order_col = col
        elif 'order' in col_lower:
            order_col = col
        if 'quarter' in col_lower or 'date' in col_lower:
            date_col = col

    if order_col is None:
        order_col = quotas_df.columns[0]
        print(f"  Using first column as order number: {order_col}")

    if date_col is None:
        quotas_df['_start_date'] = quarter_start
        date_col = '_start_date'
        print(f"  Using current quarter start date: {quarter_start}")

    # Fetch all quotas
    raw_data = scraper.fetch_all_quotas(quotas_df, order_col=order_col, date_col=date_col)

    if raw_data.empty:
        print("\nNo data was collected")
        return None

    # Clean and process data
    print("\n" + "=" * 60)
    print("Processing data...")
    print("=" * 60)

    cleaned_data = clean_quota_data(raw_data)
    processed_data = calculate_quota_metrics(cleaned_data)

    # Extract period information automatically
    period_display, latest_data, quarter, year = extract_period_info(processed_data)
    print(f"  Detected period: {period_display}")
    print(f"  Latest data: {latest_data}")

    # Save snapshot for historical tracking
    print("\nSaving snapshot...")
    snapshot_folder = get_snapshot_folder()
    snapshot_path = save_snapshot(processed_data, snapshot_folder)
    print(f"  Snapshot: {snapshot_path}")

    # Generate output files
    print("\nGenerating output files...")

    # 1. Raw data file
    raw_filename = generate_output_filename("eu_quota_raw", scrape_date)
    raw_path = os.path.join(output_folder, raw_filename)
    save_raw_data(processed_data, raw_path)
    print(f"  Raw data: {raw_path}")

    # 2. UK Scraping (if enabled)
    uk_processed_data = None

    if not skip_uk:
        # Determine UK input file
        if uk_input_file is None:
            uk_input_file = os.path.join(get_input_folder(), DEFAULT_UK_INPUT_FILE)

        if os.path.exists(uk_input_file):
            print("\n" + "=" * 60)
            print("UK Quota Scraping...")
            print("=" * 60)

            uk_quotas_df = load_quota_urls(uk_input_file)

            if not uk_quotas_df.empty:
                uk_scraper = UKQuotaScraper(headless=True)

                # Determine UK column names
                uk_order_col = None
                uk_category_col = None
                uk_country_col = None

                for col in uk_quotas_df.columns:
                    col_lower = str(col).lower()
                    if 'order' in col_lower:
                        uk_order_col = col
                    if 'category' in col_lower:
                        uk_category_col = col
                    if 'country' in col_lower:
                        uk_country_col = col

                if uk_order_col is None:
                    uk_order_col = uk_quotas_df.columns[0]

                # Find template limit column
                uk_limit_col = None
                for col in uk_quotas_df.columns:
                    col_lower = str(col).lower()
                    if 'template' in col_lower and 'limit' in col_lower:
                        uk_limit_col = col
                        break
                    if 'quota' in col_lower and 'limit' in col_lower:
                        uk_limit_col = col

                # Fetch UK data
                uk_raw_data = uk_scraper.fetch_all_quotas(
                    uk_quotas_df,
                    order_col=uk_order_col,
                    category_col=uk_category_col or 'Quota Category',
                    country_col=uk_country_col or 'Country',
                    template_limit_col=uk_limit_col or 'Template Quota Limit'
                )

                if not uk_raw_data.empty:
                    uk_processed_data = uk_raw_data
                    print(f"  UK quotas processed: {len(uk_processed_data)}")

                    # Save UK raw data
                    uk_raw_filename = generate_output_filename("uk_quota_raw", scrape_date)
                    uk_raw_path = os.path.join(output_folder, uk_raw_filename)
                    save_raw_data(uk_processed_data, uk_raw_path)
                    print(f"  UK raw data: {uk_raw_path}")
        else:
            print(f"\n  UK input file not found: {uk_input_file}")
            print("  Skipping UK scraping...")

    # 3. MEPS customer report (with EU and optionally UK data)
    if output_file is None:
        output_file = generate_output_filename("MEPS_Quota_Update", scrape_date)

    meps_path = os.path.join(output_folder, output_file)
    meps_path = generate_meps_report(processed_data, meps_path, period_display,
                                     latest_data, uk_df=uk_processed_data)
    print(f"  MEPS report: {meps_path}")

    # 4. Published data for the downloader (daily GitHub Actions run)
    if publish:
        from src.publisher import publish_data
        print("\nPublishing data for the downloader...")
        publish_dir = os.path.join(os.path.dirname(get_input_folder()), "published")
        publish_data(processed_data, uk_processed_data, meps_path,
                     publish_dir, run_date=scrape_date,
                     period_display=period_display)

    # Display summary
    summary = get_quota_summary(processed_data)

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"  EU quotas scraped: {summary['total_quotas']}")
    print(f"  EU high usage (>75%): {summary['high_usage_count']}")
    print(f"  EU critical quotas: {summary['critical_count']}")
    if uk_processed_data is not None and not uk_processed_data.empty:
        print(f"  UK quotas scraped: {len(uk_processed_data)}")
    print(f"\nOutput folder: {output_folder}")

    return processed_data


def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description='EU/UK Quota Scraper - Steel Tariff Quota Tracker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run.py                     # Scrape both EU and UK
    python run.py --skip-uk           # Scrape EU only
    python run.py -i eu.xlsx -u uk.xlsx -o output.xlsx
        """
    )

    parser.add_argument('-i', '--input',
                       help='Input Excel file with EU quota URLs',
                       default=None)
    parser.add_argument('-u', '--uk-input',
                       help='Input Excel file with UK quota URLs',
                       default=None)
    parser.add_argument('-o', '--output',
                       help='Output Excel filename',
                       default=None)
    parser.add_argument('--skip-uk',
                       action='store_true',
                       help='Skip UK scraping')
    parser.add_argument('--publish',
                       action='store_true',
                       help='Also update data/published/ (latest report + daily '
                            'history) for the downloader program')

    args = parser.parse_args()

    result = run_scraper(
        input_file=args.input,
        output_file=args.output,
        uk_input_file=args.uk_input,
        skip_uk=args.skip_uk,
        publish=args.publish
    )

    if result is not None:
        print("\nScraping complete!")
    else:
        print("\nScraping failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
