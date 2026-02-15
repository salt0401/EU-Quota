# -*- coding: utf-8 -*-
"""
Deep comparison of template vs output Excel files
"""
import zipfile
import os

def analyze_xlsx(filepath, label):
    """Analyze internal structure of an xlsx file"""
    print(f"\n{'='*70}")
    print(f"ANALYZING: {label}")
    print(f"File: {filepath}")
    print(f"Size: {os.path.getsize(filepath):,} bytes")
    print('='*70)
    
    file_sizes = {}
    total_uncompressed = 0
    
    with zipfile.ZipFile(filepath, 'r') as zf:
        print(f"\nTotal files in archive: {len(zf.namelist())}")
        print(f"\n{'File':<50} {'Compressed':<12} {'Uncompressed':<15}")
        print('-'*77)
        
        for info in zf.infolist():
            file_sizes[info.filename] = {
                'compressed': info.compress_size,
                'uncompressed': info.file_size
            }
            total_uncompressed += info.file_size
            print(f"{info.filename:<50} {info.compress_size:>10,}  {info.file_size:>12,}")
        
        print('-'*77)
        print(f"{'TOTAL':<50} {sum(f['compressed'] for f in file_sizes.values()):>10,}  {total_uncompressed:>12,}")
    
    return file_sizes

def compare_files(template_path, output_path):
    """Compare two xlsx files"""
    template_sizes = analyze_xlsx(template_path, "TEMPLATE")
    output_sizes = analyze_xlsx(output_path, "OUTPUT")
    
    print(f"\n{'='*70}")
    print("SIZE DIFFERENCE ANALYSIS")
    print('='*70)
    
    all_files = set(template_sizes.keys()) | set(output_sizes.keys())
    
    print(f"\n{'File':<50} {'Template':<12} {'Output':<12} {'Diff':<12}")
    print('-'*86)
    
    total_diff = 0
    significant_diffs = []
    
    for filename in sorted(all_files):
        t_size = template_sizes.get(filename, {}).get('compressed', 0)
        o_size = output_sizes.get(filename, {}).get('compressed', 0)
        diff = o_size - t_size
        total_diff += diff
        
        if abs(diff) > 100:  # Only show significant differences
            sign = '+' if diff > 0 else ''
            print(f"{filename:<50} {t_size:>10,}  {o_size:>10,}  {sign}{diff:>10,}")
            significant_diffs.append((filename, t_size, o_size, diff))
    
    print('-'*86)
    print(f"{'TOTAL DIFFERENCE':<50} {'':<12} {'':<12} {total_diff:>10,} bytes")
    
    # Only present in template
    only_template = set(template_sizes.keys()) - set(output_sizes.keys())
    if only_template:
        print(f"\n*** FILES ONLY IN TEMPLATE (missing from output): ***")
        for f in only_template:
            size = template_sizes[f]['compressed']
            print(f"  {f} ({size:,} bytes)")
    
    # Only present in output
    only_output = set(output_sizes.keys()) - set(template_sizes.keys())
    if only_output:
        print(f"\n*** FILES ONLY IN OUTPUT (new files): ***")
        for f in only_output:
            size = output_sizes[f]['compressed']
            print(f"  {f} ({size:,} bytes)")
    
    return significant_diffs

# Run comparison
template_path = 'templates/meps_customer_template.xlsx'
output_path = 'data/output/2026-01-25/MEPS_Quota_Update_20260125.xlsx'

significant = compare_files(template_path, output_path)

print("\n" + "="*70)
print("TOP SIZE DIFFERENCES (sorted by absolute difference)")
print("="*70)
for filename, t_size, o_size, diff in sorted(significant, key=lambda x: abs(x[3]), reverse=True)[:10]:
    sign = '+' if diff > 0 else ''
    pct = (diff / t_size * 100) if t_size > 0 else 0
    print(f"{filename}")
    print(f"  Template: {t_size:,} bytes  ->  Output: {o_size:,} bytes")
    print(f"  Difference: {sign}{diff:,} bytes ({sign}{pct:.1f}%)")
