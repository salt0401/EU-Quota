# -*- coding: utf-8 -*-
"""
EU Quota Excel Generator
Creates MEPS-style Excel reports by modifying template XML directly

Strategy: Copy the template file and modify XML directly using zipfile,
preserving all slicers, drawings, and interactive elements that openpyxl strips.
"""

import os
import shutil
import zipfile
import tempfile
import re
import pandas as pd
from datetime import date, datetime
from typing import Optional, Tuple
from xml.etree import ElementTree as ET

from .data_processor import extract_period_info, prepare_customer_data, get_quota_summary
from .utils import get_templates_folder


# XML namespaces used in Excel files
NAMESPACES = {
    'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}

# Register namespaces to preserve them during XML modification
for prefix, uri in NAMESPACES.items():
    if prefix != 'main':  # main namespace is default, don't prefix it
        ET.register_namespace(prefix, uri)
ET.register_namespace('', NAMESPACES['main'])


def generate_meps_report(
    df: pd.DataFrame,
    output_path: str,
    period_display: Optional[str] = None,
    latest_data_date: Optional[str] = None
) -> str:
    """
    Generate MEPS-style Excel report by copying template and updating XML directly

    Args:
        df: Processed DataFrame with quota metrics
        output_path: Full path for output file
        period_display: Optional custom period string
        latest_data_date: Optional custom latest data date

    Returns:
        str: Path to generated file
    """
    # Extract period info if not provided
    if period_display is None or latest_data_date is None:
        auto_period, auto_latest, quarter, year = extract_period_info(df)
        if period_display is None:
            period_display = auto_period
        if latest_data_date is None:
            latest_data_date = auto_latest

    # Prepare customer data
    customer_df = prepare_customer_data(df)

    # Get template path
    template_path = os.path.join(get_templates_folder(), "meps_customer_template.xlsx")

    if os.path.exists(template_path):
        # Use XML-based update to preserve slicers
        return _update_template_xml(template_path, output_path, customer_df,
                                    period_display, latest_data_date)
    else:
        # Fallback: generate from scratch using openpyxl (no slicers)
        return _generate_from_scratch(output_path, customer_df,
                                      period_display, latest_data_date)


def _update_template_xml(
    template_path: str,
    output_path: str,
    df: pd.DataFrame,
    period_display: str,
    latest_data: str
) -> str:
    """
    Update template using direct XML manipulation to preserve slicers

    This approach:
    1. Extracts template xlsx to temp directory
    2. Modifies sharedStrings.xml (for date text updates)
    3. Modifies sheet2.xml (for EU data)
    4. Modifies sheet3.xml (for UK placeholder)
    5. Repackages the xlsx preserving all other files (slicers, drawings, etc.)
    """
    # Create a temporary directory for extraction
    with tempfile.TemporaryDirectory() as temp_dir:
        # Extract the template xlsx (it's a ZIP file)
        with zipfile.ZipFile(template_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)

        # Update sharedStrings.xml with new date strings
        shared_strings_path = os.path.join(temp_dir, 'xl', 'sharedStrings.xml')
        if os.path.exists(shared_strings_path):
            _update_shared_strings(shared_strings_path, period_display, latest_data)

        # Update sheet2.xml (European Union) with new data
        sheet2_path = os.path.join(temp_dir, 'xl', 'worksheets', 'sheet2.xml')
        if os.path.exists(sheet2_path):
            _update_eu_sheet_xml(sheet2_path, df)

        # Update sheet3.xml (United Kingdom) - clear data, keep structure
        sheet3_path = os.path.join(temp_dir, 'xl', 'worksheets', 'sheet3.xml')
        if os.path.exists(sheet3_path):
            _update_uk_sheet_xml(sheet3_path)

        # Package to a temp file first, then move to output
        temp_output = os.path.join(temp_dir, 'output.xlsx')
        _repackage_xlsx_to_file(temp_dir, temp_output)

        # Try to write to output path, handle if locked
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
            shutil.move(temp_output, output_path)
        except PermissionError:
            # File is locked (probably open in Excel), use alternative filename
            base, ext = os.path.splitext(output_path)
            alt_output = f"{base}_new{ext}"
            print(f"  Warning: {os.path.basename(output_path)} is locked, saving as {os.path.basename(alt_output)}")
            shutil.move(temp_output, alt_output)
            return alt_output

    return output_path


def _update_shared_strings(filepath: str, period_display: str, latest_data: str):
    """Update date strings in sharedStrings.xml"""

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Update the period string (matches pattern like "Current quota period: XX-XXX-XXXX to XX-XXX-XXXX")
    period_pattern = r'Current quota period: [^<]+'
    new_period = f'Current quota period: {period_display}'
    content = re.sub(period_pattern, new_period, content)

    # Update the latest data string
    latest_pattern = r'Latest available data: [^<]+'
    new_latest = f'Latest available data: {latest_data}'
    content = re.sub(latest_pattern, new_latest, content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def _update_eu_sheet_xml(filepath: str, df: pd.DataFrame):
    """Update European Union sheet with new data rows"""

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse XML
    # We need to preserve the XML declaration and namespaces
    tree = ET.parse(filepath)
    root = tree.getroot()

    # Find sheetData element
    ns = {'': NAMESPACES['main']}
    sheet_data = root.find('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData')

    if sheet_data is None:
        print("Warning: Could not find sheetData in sheet2.xml")
        return

    # Get all existing rows
    rows = sheet_data.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')

    # Find rows to remove (data rows start at row 16)
    rows_to_remove = []
    for row in rows:
        row_num = int(row.get('r', 0))
        if row_num >= 16:
            rows_to_remove.append(row)

    # Remove old data rows
    for row in rows_to_remove:
        sheet_data.remove(row)

    # Add new data rows
    for idx, row_data in enumerate(df.values):
        row_num = 16 + idx
        row_elem = _create_data_row(row_num, row_data)
        sheet_data.append(row_elem)

    # Update dimension
    dimension = root.find('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}dimension')
    if dimension is not None:
        last_row = 15 + len(df)
        dimension.set('ref', f'A1:G{last_row}')

    # Write back
    tree.write(filepath, xml_declaration=True, encoding='UTF-8')

    # Fix namespace declaration (ElementTree sometimes mangles it)
    _fix_xml_namespaces(filepath)


def _create_data_row(row_num: int, data: tuple) -> ET.Element:
    """Create an XML row element for data"""

    ns = NAMESPACES['main']
    row = ET.Element(f'{{{ns}}}row')
    row.set('r', str(row_num))
    row.set('spans', '1:7')

    col_letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G']

    for col_idx, value in enumerate(data):
        cell = ET.SubElement(row, f'{{{ns}}}c')
        cell.set('r', f'{col_letters[col_idx]}{row_num}')

        if col_idx < 2:  # Text columns (Quota Category, Country)
            cell.set('t', 'inlineStr')
            inline_str = ET.SubElement(cell, f'{{{ns}}}is')
            t_elem = ET.SubElement(inline_str, f'{{{ns}}}t')
            t_elem.text = str(value) if value else ''
        else:  # Numeric columns
            v_elem = ET.SubElement(cell, f'{{{ns}}}v')
            if pd.isna(value):
                v_elem.text = '0'
            elif isinstance(value, float) and value < 1:  # Percentage
                v_elem.text = str(value)
            else:
                v_elem.text = str(int(value) if isinstance(value, float) and value == int(value) else value)

    return row


def _update_uk_sheet_xml(filepath: str):
    """Update UK sheet - clear data rows but keep structure"""

    tree = ET.parse(filepath)
    root = tree.getroot()

    # Find sheetData element
    sheet_data = root.find('.//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheetData')

    if sheet_data is None:
        return

    # Get all existing rows and remove data rows (row >= 16)
    rows = sheet_data.findall('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row')
    rows_to_remove = [row for row in rows if int(row.get('r', 0)) >= 16]

    for row in rows_to_remove:
        sheet_data.remove(row)

    # Add placeholder row
    ns = NAMESPACES['main']
    placeholder_row = ET.Element(f'{{{ns}}}row')
    placeholder_row.set('r', '16')
    placeholder_row.set('spans', '1:7')

    cell = ET.SubElement(placeholder_row, f'{{{ns}}}c')
    cell.set('r', 'A16')
    cell.set('t', 'inlineStr')
    inline_str = ET.SubElement(cell, f'{{{ns}}}is')
    t_elem = ET.SubElement(inline_str, f'{{{ns}}}t')
    t_elem.text = 'UK data not yet available'

    sheet_data.append(placeholder_row)

    # Write back
    tree.write(filepath, xml_declaration=True, encoding='UTF-8')
    _fix_xml_namespaces(filepath)


def _fix_xml_namespaces(filepath: str):
    """Fix XML namespace declarations that ElementTree may have modified"""

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Ensure proper namespace declaration
    if 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"' not in content:
        # Add default namespace if missing
        content = content.replace(
            '<worksheet ',
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        )

    # Remove ns0: prefix if present (ElementTree artifact)
    content = content.replace('ns0:', '')
    content = content.replace(':ns0', '')
    content = content.replace('xmlns:ns0', 'xmlns')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)


def _repackage_xlsx_to_file(source_dir: str, output_path: str):
    """Repackage extracted files back into xlsx"""

    # Skip the output file itself if it exists in source_dir
    skip_file = os.path.basename(output_path)

    # Create new zip with xlsx extension
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                if file == skip_file:
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, arcname)


def _generate_from_scratch(
    output_path: str,
    df: pd.DataFrame,
    period_display: str,
    latest_data: str
) -> str:
    """
    Generate report from scratch using openpyxl (fallback if template not available)
    Note: This won't have slicers
    """
    from openpyxl import Workbook
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    MEPS_BLUE = "16477C"
    HEADER_FILL = PatternFill(start_color=MEPS_BLUE, end_color=MEPS_BLUE, fill_type="solid")
    HEADER_FONT = Font(name="Segoe UI", bold=True, size=11, color="FFFFFF")
    DATA_FONT = Font(name="Segoe UI", size=11)
    TITLE_FONT = Font(name="Kalinga", bold=True, size=26, color="FFFFFF")
    SUBTITLE_FONT = Font(name="Kalinga", size=12, color="FFFFFF")

    wb = Workbook()

    # Create sheets
    ws_inst = wb.active
    ws_inst.title = "Instructions"
    ws_eu = wb.create_sheet("European Union")
    ws_uk = wb.create_sheet("United Kingdom")

    # Build EU Data sheet
    # Set header background
    for row in range(1, 15):
        for col in range(1, 8):
            ws_eu.cell(row=row, column=col).fill = HEADER_FILL

    ws_eu['A1'] = "MEPS European Union Quota Update"
    ws_eu['A1'].font = TITLE_FONT

    ws_eu['A2'] = f"Current quota period: {period_display}"
    ws_eu['A3'] = f"Latest available data: {latest_data}"
    ws_eu['A2'].font = SUBTITLE_FONT
    ws_eu['A3'].font = SUBTITLE_FONT

    # Data table starts at row 15
    start_row = 15
    headers = list(df.columns)
    for col_idx, header in enumerate(headers, 1):
        cell = ws_eu.cell(row=start_row, column=col_idx, value=header)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    # Write data
    for row_idx, row_data in enumerate(df.values, start_row + 1):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws_eu.cell(row=row_idx, column=col_idx, value=value)
            cell.font = DATA_FONT
            if col_idx >= 3:
                cell.alignment = Alignment(horizontal='right')

    # Set column widths
    col_widths = [64, 40, 20, 20, 15, 20, 15]
    for col_idx, width in enumerate(col_widths, 1):
        ws_eu.column_dimensions[get_column_letter(col_idx)].width = width

    ws_eu.freeze_panes = f'A{start_row + 1}'

    # UK placeholder
    for row in range(1, 15):
        for col in range(1, 8):
            ws_uk.cell(row=row, column=col).fill = HEADER_FILL

    ws_uk['A1'] = "MEPS United Kingdom Quota Update"
    ws_uk['A1'].font = TITLE_FONT
    ws_uk['A2'] = f"Current quota period: {period_display}"
    ws_uk['A3'] = f"Latest available data: {latest_data}"
    ws_uk['A15'] = "UK data not yet available"

    wb.save(output_path)
    return output_path


def save_raw_data(df: pd.DataFrame, output_path: str) -> str:
    """Save raw scraped data to Excel"""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    MEPS_BLUE = "16477C"
    HEADER_FILL = PatternFill(start_color=MEPS_BLUE, end_color=MEPS_BLUE, fill_type="solid")

    wb = Workbook()
    ws = wb.active
    ws.title = "Raw Data"

    # Write headers
    headers = list(df.columns)
    for col_idx, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL

    # Write data
    for row_idx, row_data in enumerate(df.values, 2):
        for col_idx, value in enumerate(row_data, 1):
            ws.cell(row=row_idx, column=col_idx, value=value)

    # Auto-adjust widths
    for col_idx, header in enumerate(headers, 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = min(len(str(header)) + 5, 30)

    ws.freeze_panes = 'A2'
    wb.save(output_path)
    return output_path


def save_snapshot(df: pd.DataFrame, output_folder: str) -> str:
    """Save timestamped snapshot"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"snapshot_{timestamp}.xlsx"
    output_path = os.path.join(output_folder, filename)

    df_copy = df.copy()
    df_copy['snapshot_timestamp'] = datetime.now().isoformat()

    save_raw_data(df_copy, output_path)
    return output_path
