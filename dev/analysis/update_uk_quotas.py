# -*- coding: utf-8 -*-
"""
Update uk_quota_urls.xlsx - Replace old 058019 with new 2026 order numbers
"""
import pandas as pd
import shutil
from datetime import datetime

# Backup original file
backup_name = f'data/input/uk_quota_urls_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
shutil.copy('data/input/uk_quota_urls.xlsx', backup_name)
print(f"Backup created: {backup_name}")

# Read the file
df = pd.read_excel('data/input/uk_quota_urls.xlsx', header=None)
print(f"Original file shape: {df.shape}")

# Order number mapping: old -> new
# Based on HMRC verification for Category 13 Rebars:
# 058019 is obsolete, replaced by:
ORDER_MAPPING = {
    # Old order number (058019) rows need to be replaced based on country
    'All others': 58020,    # New residual quota number
    'Egypt*': 58131,        # Country-specific
    'Vietnam*': 58136,      # Country-specific (new for 2026)
    'Algeria*': 58130,      # Country-specific
    'New Zealand*': 58133,  # Country-specific
    'Norway*': 58134,       # Country-specific
    'Taiwan*': 58020,       # Taiwan uses residual (058020)
}

# Quota limits from most recent search (2026 Q3)
QUOTA_LIMITS = {
    'All others': 23514,    # Residual quota
    'Egypt*': 4703,         # 20% cap
    'Vietnam*': 4703,       # 20% cap (new)
    'Algeria*': 4703,       # 20% cap
    'New Zealand*': 4703,   # 20% cap
    'Norway*': 4703,        # 20% cap
    'Taiwan*': 4703,        # 20% cap (uses residual)
}

# Find and replace rows with 058019 / 58019
updated_count = 0
rows_to_check = []

for idx, row in df.iterrows():
    order_num = row.iloc[0]
    if pd.notna(order_num):
        order_str = str(int(order_num)) if isinstance(order_num, float) else str(order_num)
        if order_str in ['58019', '058019']:
            country = str(row.iloc[2]) if pd.notna(row.iloc[2]) else 'Unknown'
            old_limit = row.iloc[3] if pd.notna(row.iloc[3]) else 0
            
            # Get new order number based on country
            if country in ORDER_MAPPING:
                new_order = ORDER_MAPPING[country]
                new_limit = QUOTA_LIMITS.get(country, old_limit)
                
                print(f"Row {idx}: {order_str} ({country}) -> {new_order} (Limit: {old_limit} -> {new_limit})")
                
                df.iloc[idx, 0] = new_order
                df.iloc[idx, 3] = new_limit
                updated_count += 1
                rows_to_check.append((idx, country, new_order, new_limit))
            else:
                print(f"Row {idx}: {order_str} ({country}) - UNKNOWN MAPPING!")

print(f"\nTotal rows updated: {updated_count}")

# Save updated file
df.to_excel('data/input/uk_quota_urls.xlsx', header=False, index=False)
print(f"\nFile saved: data/input/uk_quota_urls.xlsx")

# Display updated rows
print("\n=== Updated Rows Summary ===")
for idx, country, order, limit in rows_to_check:
    print(f"  Row {idx}: Order {order:06d} | {country} | Limit: {limit}")
