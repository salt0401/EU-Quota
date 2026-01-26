# -*- coding: utf-8 -*-
"""
Tests for src/utils.py - File and date utilities
"""
import pytest
from datetime import date, datetime
import os
import sys

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils import (
    get_output_folder,
    get_snapshot_folder,
    get_input_folder,
    get_templates_folder,
    generate_output_filename,
    format_date_display,
    parse_date_string,
)


class TestGetOutputFolder:
    """Tests for get_output_folder function"""

    def test_creates_dated_path(self):
        result = get_output_folder(date(2026, 1, 25))
        assert "2026-01-25" in result
        assert "data" in result
        assert "output" in result

    def test_uses_today_by_default(self):
        result = get_output_folder()
        today_str = date.today().strftime("%Y-%m-%d")
        assert today_str in result

    def test_path_ends_with_date_folder(self):
        result = get_output_folder(date(2026, 3, 15))
        assert result.endswith("2026-03-15")


class TestGenerateOutputFilename:
    """Tests for generate_output_filename function"""

    def test_generates_correct_format(self):
        result = generate_output_filename("eu_quota_report", date(2026, 1, 25))
        assert result == "eu_quota_report_20260125.xlsx"

    def test_custom_extension(self):
        result = generate_output_filename("report", date(2026, 1, 25), "csv")
        assert result == "report_20260125.csv"

    def test_uses_today_by_default(self):
        result = generate_output_filename("test")
        today_str = date.today().strftime("%Y%m%d")
        assert today_str in result
        assert result.endswith(".xlsx")

    def test_different_prefixes(self):
        result1 = generate_output_filename("eu_quota_raw", date(2026, 1, 25))
        result2 = generate_output_filename("MEPS_Quota_Update", date(2026, 1, 25))
        assert result1 == "eu_quota_raw_20260125.xlsx"
        assert result2 == "MEPS_Quota_Update_20260125.xlsx"


class TestFormatDateDisplay:
    """Tests for format_date_display function"""

    def test_formats_january(self):
        result = format_date_display(date(2026, 1, 15))
        assert result == "15-Jan-2026"

    def test_formats_december(self):
        result = format_date_display(date(2026, 12, 31))
        assert result == "31-Dec-2026"

    def test_pads_single_digit_day(self):
        result = format_date_display(date(2026, 3, 5))
        assert result == "05-Mar-2026"

    def test_all_months(self):
        expected = {
            1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
            5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
            9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
        }
        for month, abbrev in expected.items():
            result = format_date_display(date(2026, month, 1))
            assert abbrev in result


class TestParseDateString:
    """Tests for parse_date_string function"""

    def test_parses_dd_mm_yyyy(self):
        result = parse_date_string("25-01-2026")
        assert result == date(2026, 1, 25)

    def test_parses_yyyy_mm_dd(self):
        result = parse_date_string("2026-01-25")
        assert result == date(2026, 1, 25)

    def test_parses_dd_slash_mm_slash_yyyy(self):
        result = parse_date_string("25/01/2026")
        assert result == date(2026, 1, 25)

    def test_parses_yyyy_slash_mm_slash_dd(self):
        result = parse_date_string("2026/01/25")
        assert result == date(2026, 1, 25)

    def test_returns_none_for_empty_string(self):
        result = parse_date_string("")
        assert result is None

    def test_returns_none_for_none(self):
        result = parse_date_string(None)
        assert result is None

    def test_returns_none_for_invalid_format(self):
        result = parse_date_string("invalid date")
        assert result is None

    def test_returns_none_for_partial_date(self):
        result = parse_date_string("25-01")
        assert result is None

    def test_handles_whitespace(self):
        result = parse_date_string("  2026-01-25  ")
        assert result == date(2026, 1, 25)

    def test_handles_numeric_input(self):
        # Should convert to string and try to parse
        result = parse_date_string(20260125)
        # This format isn't supported, should return None
        assert result is None


class TestFolderPaths:
    """Tests for folder path functions"""

    def test_snapshot_folder_path(self):
        result = get_snapshot_folder()
        assert "data" in result
        assert "snapshots" in result

    def test_input_folder_path(self):
        result = get_input_folder()
        assert "data" in result
        assert "input" in result

    def test_templates_folder_path(self):
        result = get_templates_folder()
        assert "templates" in result

    def test_all_paths_are_absolute(self):
        paths = [
            get_output_folder(),
            get_snapshot_folder(),
            get_input_folder(),
            get_templates_folder(),
        ]
        for path in paths:
            assert os.path.isabs(path), f"Path should be absolute: {path}"


class TestEdgeCases:
    """Edge case tests"""

    def test_leap_year_date(self):
        result = format_date_display(date(2024, 2, 29))
        assert result == "29-Feb-2024"

    def test_parse_leap_year_date(self):
        result = parse_date_string("29-02-2024")
        assert result == date(2024, 2, 29)

    def test_year_boundaries(self):
        # Last day of year
        result = format_date_display(date(2025, 12, 31))
        assert result == "31-Dec-2025"

        # First day of year
        result = format_date_display(date(2026, 1, 1))
        assert result == "01-Jan-2026"

    def test_output_folder_year_change(self):
        result_2025 = get_output_folder(date(2025, 12, 31))
        result_2026 = get_output_folder(date(2026, 1, 1))
        assert "2025-12-31" in result_2025
        assert "2026-01-01" in result_2026
