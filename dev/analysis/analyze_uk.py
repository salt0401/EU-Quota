# -*- coding: utf-8 -*-
"""Detailed analysis of UK quota files"""
import pandas as pd

print("=" * 70)
print("UK QUOTA DETAILED ANALYSIS")
print("=" * 70)

# 1. UK Quota URLs - get all order numbers
print("\n### UK QUOTA URLS ###")
df_uk = pd.read_excel('data/input/uk_quota_urls.xlsx', header=4)
print(f"Shape: {df_uk.shape}")
print(f"Columns: {list(df_uk.columns)}")

# Get all data
print("\n--- ALL UK DATA ---")
for idx, row in df_uk.iterrows():
    print(f"Row {idx}: {list(row.values)}")

# Count order numbers
order_col = None
for col in df_uk.columns:
    if 'order' in str(col).lower():
        order_col = col
        break

if order_col:
    uk_orders = df_uk[order_col].dropna().astype(str).str.strip()
    # Remove non-numeric
    uk_orders = [o for o in uk_orders if o and o != 'nan']
    print(f"\n*** TOTAL UK ORDER NUMBERS: {len(uk_orders)} ***")
    for i, order in enumerate(uk_orders):
        print(f"  {i+1}. {order}")
