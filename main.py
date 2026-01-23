# -*- coding: utf-8 -*-
"""
EU Quota Scraper - Main Entry Point
Automated collection of EU steel tariff quota data

Author: Data Intern @ MEPS International

Usage:
    python main.py                    # Interactive mode
    python main.py --auto             # Automatic mode (uses defaults)
    python main.py --input quotas.xlsx --output report.xlsx
"""

import os
import sys
import argparse
import pandas as pd
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eu_quota_scraper import (
    EUQuotaScraper,
    get_current_quarter_start,
    calculate_quota_metrics,
    export_to_excel,
    save_snapshot
)
from eu_quota_scraper.data_processor import clean_quota_data, prepare_customer_report


# Default paths
# Default paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT_FILE = os.path.join(SCRIPT_DIR, "EU Quota URL's.xlsx")
DEFAULT_OUTPUT_DIR = os.path.join(SCRIPT_DIR, "data", "output")
DEFAULT_SNAPSHOT_DIR = os.path.join(SCRIPT_DIR, "data", "snapshots")


def load_quota_urls(filepath: str) -> pd.DataFrame:
    """
    Load quota order numbers from Excel file
    
    Args:
        filepath: Path to Excel file with quota URLs
        
    Returns:
        pd.DataFrame with order numbers and metadata
    """
    print(f"📂 Loading quota list from: {filepath}")
    
    # Try to auto-detect header row by looking for key columns
    # The EU Quota URL's.xlsx file has header on row 5 (index 4)
    for header_row in [0, 4, 1, 2, 3]:
        try:
            df = pd.read_excel(filepath, header=header_row)
            # Check if we have the expected column
            if any('order' in str(col).lower() for col in df.columns):
                print(f"   ✅ Found header at row {header_row + 1}")
                break
        except Exception:
            continue
    else:
        # Default fallback
        df = pd.read_excel(filepath, header=4)
    
    # Filter out rows with NaN in the order number column
    order_col = None
    for col in df.columns:
        if 'order' in str(col).lower():
            order_col = col
            break
    
    if order_col:
        df = df[df[order_col].notna()]
    
    print(f"   Found {len(df)} quotas to process")
    print(f"   Columns: {list(df.columns)}")
    
    return df


def run_scraper(input_file: str = None,
                output_file: str = None,
                auto_mode: bool = False) -> pd.DataFrame:
    """
    Main scraping workflow
    
    Args:
        input_file: Path to input Excel file with quota URLs
        output_file: Path for output Excel file
        auto_mode: If True, run without user prompts
        
    Returns:
        pd.DataFrame: Scraped and processed data
    """
    print("""
    ╔══════════════════════════════════════════════════════════════╗
         EU Quota Scraper - Steel Tariff Quota Tracker
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Determine input file
    if input_file is None:
        input_file = DEFAULT_INPUT_FILE
    
    if not os.path.exists(input_file):
        print(f"❌ Input file not found: {input_file}")
        return None
    
    # Load quota URLs
    quotas_df = load_quota_urls(input_file)
    
    # Display current quarter info
    quarter_start = get_current_quarter_start()
    print(f"\n📅 Current quarter start: {quarter_start}")
    
    # Confirm before proceeding (unless auto mode)
    if not auto_mode:
        print(f"\n📊 Ready to scrape {len(quotas_df)} quotas")
        user_input = input("   Continue? [y/n]: ").strip().lower()
        if user_input not in ['y', 'yes']:
            print("\n⏭️ Scraping cancelled")
            return None
    
    # Initialize scraper and fetch data
    print("\n" + "=" * 60)
    print("Starting data collection...")
    print("=" * 60)
    
    scraper = EUQuotaScraper(headless=True)
    
    # Determine column names (handle different Excel formats)
    order_col = None
    date_col = None
    
    for col in quotas_df.columns:
        col_lower = col.lower()
        if 'order' in col_lower and 'number' in col_lower:
            order_col = col
        elif 'order' in col_lower:
            order_col = col
        if 'date' in col_lower or 'quarter' in col_lower:
            date_col = col
    
    if order_col is None:
        order_col = quotas_df.columns[0]
        print(f"   ⚠️ Using first column as order number: {order_col}")
    
    if date_col is None:
        # Use current quarter for all
        quotas_df['_start_date'] = quarter_start
        date_col = '_start_date'
        print(f"   ⚠️ Using current quarter start date: {quarter_start}")
    
    # Fetch all quotas
    raw_data = scraper.fetch_all_quotas(quotas_df, order_col=order_col, date_col=date_col)
    
    if raw_data.empty:
        print("\n❌ No data was collected")
        return None
    
    # Clean and process data
    print("\n" + "=" * 60)
    print("Processing data...")
    print("=" * 60)
    
    cleaned_data = clean_quota_data(raw_data)
    processed_data = calculate_quota_metrics(cleaned_data)
    
    # Save snapshot
    print("\n📸 Saving snapshot...")
    os.makedirs(DEFAULT_SNAPSHOT_DIR, exist_ok=True)
    save_snapshot(processed_data, DEFAULT_SNAPSHOT_DIR)
    
    # Export to Excel
    print("\n💾 Exporting results...")
    os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
    
    if output_file is None:
        timestamp = datetime.now().strftime('%Y%m%d')
        output_file = f"eu_quota_report_{timestamp}.xlsx"
    
    export_to_excel(processed_data, output_file, DEFAULT_OUTPUT_DIR)
    
    # Also create customer-ready report
    customer_report = prepare_customer_report(processed_data)
    if not customer_report.empty:
        customer_file = output_file.replace('.xlsx', '_customer.xlsx')
        export_to_excel(customer_report, customer_file, DEFAULT_OUTPUT_DIR, 
                       sheet_name='Quota Summary')
    
    # Display summary
    print("\n" + "=" * 60)
    print("📊 Summary")
    print("=" * 60)
    
    success_count = len(processed_data[processed_data.get('order_number', pd.Series()).notna()])
    print(f"   ✅ Quotas scraped: {success_count}/{len(quotas_df)}")
    
    if 'quota_used_pct' in processed_data.columns:
        high_usage = processed_data[processed_data['quota_used_pct'] > 75]
        if len(high_usage) > 0:
            print(f"   ⚠️ High usage (>75%): {len(high_usage)} quotas")
    
    if 'critical' in processed_data.columns:
        critical_count = processed_data['critical'].sum()
        if critical_count > 0:
            print(f"   🚨 Critical quotas: {critical_count}")
    
    print(f"\n📁 Output directory: {os.path.abspath(DEFAULT_OUTPUT_DIR)}")
    
    return processed_data


def main():
    """Main entry point with argument parsing"""
    parser = argparse.ArgumentParser(
        description='EU Quota Scraper - Steel Tariff Quota Tracker',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                          # Interactive mode
    python main.py --auto                   # Automatic mode
    python main.py -i quotas.xlsx -o output.xlsx
        """
    )
    
    parser.add_argument('-i', '--input', 
                       help='Input Excel file with quota URLs',
                       default=None)
    parser.add_argument('-o', '--output',
                       help='Output Excel filename',
                       default=None)
    parser.add_argument('--auto',
                       action='store_true',
                       help='Run in automatic mode (no prompts)')
    
    args = parser.parse_args()
    
    result = run_scraper(
        input_file=args.input,
        output_file=args.output,
        auto_mode=args.auto
    )
    
    if result is not None:
        print("\n✅ Scraping complete!")
    else:
        print("\n❌ Scraping failed or was cancelled")
        sys.exit(1)


if __name__ == "__main__":
    main()
