# -*- coding: utf-8 -*-
"""Analyze Excel files to understand quota data structure"""
import pandas as pd
import os

print("=" * 70)
print("ANALYZING EXCEL FILES")
print("=" * 70)

# 1. UK Quota URLs
print("\n" + "=" * 70)
print("1. UK QUOTA URLS (uk_quota_urls.xlsx)")
print("=" * 70)
try:
    # Try different header rows
    for header_row in [0, 1, 2, 3, 4, 5, None]:
        try:
            df = pd.read_excel('data/input/uk_quota_urls.xlsx', header=header_row)
            if header_row is None:
                print(f"\nNo header (raw):")
            else:
                print(f"\nHeader at row {header_row}:")
            print(f"  Shape: {df.shape}")
            print(f"  Columns: {list(df.columns)[:5]}...")
            
            # Check for order number column
            for col in df.columns:
                col_str = str(col).lower()
                if 'order' in col_str:
                    # Count non-null values
                    non_null = df[col].dropna()
                    print(f"  Order column '{col}': {len(non_null)} values")
                    print(f"  Sample values: {list(non_null.head(10))}")
                    break
        except Exception as e:
            pass
    
    # Full view of UK data
    print("\n--- FULL UK DATA (header=4) ---")
    df_uk = pd.read_excel('data/input/uk_quota_urls.xlsx', header=4)
    print(f"Shape: {df_uk.shape}")
    print(f"Columns: {list(df_uk.columns)}")
    
    # Find order numbers
    order_col = None
    for col in df_uk.columns:
        if 'order' in str(col).lower():
            order_col = col
            break
    
    if order_col:
        uk_orders = df_uk[order_col].dropna().astype(str).tolist()
        print(f"\n*** UK ORDER NUMBERS ({len(uk_orders)} total) ***")
        for i, order in enumerate(uk_orders):
            print(f"  {i+1}. {order}")
    
    print("\n--- Full DataFrame ---")
    print(df_uk.to_string())
    
except Exception as e:
    print(f"Error: {e}")

# 2. EU Quota URLs
print("\n" + "=" * 70)
print("2. EU QUOTA URLS (quota_urls.xlsx)")
print("=" * 70)
try:
    df_eu = pd.read_excel('data/input/quota_urls.xlsx', header=4)
    print(f"Shape: {df_eu.shape}")
    print(f"Columns: {list(df_eu.columns)}")
    
    # Find order numbers
    order_col = None
    for col in df_eu.columns:
        if 'order' in str(col).lower():
            order_col = col
            break
    
    if order_col:
        eu_orders = df_eu[order_col].dropna()
        print(f"\n*** EU ORDER NUMBERS: {len(eu_orders)} total ***")
        print(f"First 10: {list(eu_orders.head(10))}")
        print(f"Last 10: {list(eu_orders.tail(10))}")
except Exception as e:
    print(f"Error: {e}")

# 3. MEPS Template
print("\n" + "=" * 70)
print("3. MEPS TEMPLATE (meps_customer_template.xlsx)")
print("=" * 70)
try:
    # List all sheets
    xl = pd.ExcelFile('templates/meps_customer_template.xlsx')
    print(f"Sheets: {xl.sheet_names}")
    
    for sheet in xl.sheet_names:
        print(f"\n--- Sheet: {sheet} ---")
        # Try to read with different header rows
        for header_row in [0, 1, 2, 3, 4, 5, 6, 7, 8]:
            try:
                df = pd.read_excel(xl, sheet_name=sheet, header=header_row)
                # Check if this looks like the data
                if len(df.columns) > 2 and not df.empty:
                    has_quota = any('quota' in str(c).lower() for c in df.columns)
                    has_country = any('country' in str(c).lower() for c in df.columns)
                    if has_quota or has_country:
                        print(f"  [Header at row {header_row}]")
                        print(f"  Shape: {df.shape}")
                        print(f"  Columns: {list(df.columns)}")
                        # Show first few rows
                        print(df.head(20).to_string())
                        break
            except:
                pass
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 70)
print("ANALYSIS COMPLETE")
print("=" * 70)
