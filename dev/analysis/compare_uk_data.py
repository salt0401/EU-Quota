# -*- coding: utf-8 -*-
"""Compare UK input order numbers with MEPS template UK section"""
import pandas as pd

print("=" * 80)
print("UK 配額資料比對分析")
print("=" * 80)

# Read UK input file
df_uk_input = pd.read_excel('data/input/uk_quota_urls.xlsx', header=4)
# First row of header is actually data - add it
first_row = pd.read_excel('data/input/uk_quota_urls.xlsx', header=None).iloc[4].values
print(f"\n### UK INPUT FILE (uk_quota_urls.xlsx) ###")
print(f"第一列實際是資料 (被當作標題): {first_row}")

# Reconstruct the full data including the "header" row
df_uk_input_raw = pd.read_excel('data/input/uk_quota_urls.xlsx', header=None)
# Skip first 4 rows (instructions), take from row 4 onwards
df_uk_full = df_uk_input_raw.iloc[4:].reset_index(drop=True)
df_uk_full.columns = ['Order_Number', 'Quota_Category', 'Country', 'Template_Quota_Limit', 'Extra']
print(f"\n總資料筆數: {len(df_uk_full)}")

# Get unique order numbers
uk_orders = df_uk_full['Order_Number'].dropna().astype(int).astype(str).str.zfill(6).unique()
print(f"唯一配額編號數: {len(uk_orders)}")
print(f"配額編號列表:")
for i, order in enumerate(sorted(uk_orders)):
    print(f"  {i+1}. {order}")

# Read MEPS template UK section
print(f"\n\n### MEPS TEMPLATE UK SECTION ###")
df_template = pd.read_excel('templates/meps_customer_template.xlsx', sheet_name='United Kingdom', header=14)
print(f"UK 資料筆數: {len(df_template)}")
print(f"欄位: {list(df_template.columns)}")

# Get unique category-country combinations in template
template_categories = df_template['Quota Category'].dropna().unique()
template_countries = df_template['Country'].dropna().unique()
print(f"\n模板中唯一配額類別數: {len(template_categories)}")
print(f"模板中唯一國家數: {len(template_countries)}")

# Compare categories
print("\n### 配額類別比對 ###")
input_categories = df_uk_full['Quota_Category'].dropna().unique()
print(f"輸入檔配額類別: {len(input_categories)}")

print("\n--- 模板中的配額類別 ---")
for cat in sorted(template_categories):
    print(f"  - {cat}")

print("\n--- 輸入檔的配額類別 ---")
for cat in sorted(input_categories):
    print(f"  - {cat}")

# Check if all template categories are in input
print("\n\n### 遺漏分析 ###")
missing_in_input = set(template_categories) - set(input_categories)
if missing_in_input:
    print(f"模板有但輸入檔沒有的類別:")
    for cat in missing_in_input:
        print(f"  ⚠ {cat}")
else:
    print("✓ 所有模板類別都在輸入檔中")

# Check input quota limits vs template
print("\n\n### 配額限額比對 (Template Quota Limit) ###")
print("輸入檔的配額限額:")
for idx, row in df_uk_full.iterrows():
    order = str(row['Order_Number']).split('.')[0] if pd.notna(row['Order_Number']) else 'N/A'
    cat = row['Quota_Category'] if pd.notna(row['Quota_Category']) else 'N/A'
    country = row['Country'] if pd.notna(row['Country']) else 'N/A'
    limit = row['Template_Quota_Limit'] if pd.notna(row['Template_Quota_Limit']) else 'N/A'
    print(f"  {order}: {cat} | {country} | {limit}")
