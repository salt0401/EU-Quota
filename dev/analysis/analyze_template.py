# -*- coding: utf-8 -*-
"""Analyze MEPS template UK section"""
import pandas as pd

print("=" * 70)
print("MEPS TEMPLATE ANALYSIS")
print("=" * 70)

# Read the MEPS template
xl = pd.ExcelFile('templates/meps_customer_template.xlsx')
print(f"Sheets: {xl.sheet_names}")

for sheet in xl.sheet_names:
    print(f"\n{'='*70}")
    print(f"SHEET: {sheet}")
    print("="*70)
    
    # Try to read with various header rows
    df = pd.read_excel(xl, sheet_name=sheet, header=None)
    print(f"Raw shape: {df.shape}")
    print("\n--- First 20 rows (raw) ---")
    print(df.head(20).to_string())
    
    print("\n--- All rows (raw) ---")
    for idx, row in df.iterrows():
        # Convert row to list and show non-null values
        vals = [str(v) for v in row.dropna().values]
        if vals and any(v.strip() for v in vals if v != 'nan'):
            print(f"Row {idx}: {vals}")
