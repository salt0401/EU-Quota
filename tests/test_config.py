# -*- coding: utf-8 -*-
"""
Tests for src/config.py - Configuration and quarter utilities
"""
import pytest
from datetime import date
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import (
    get_current_quarter,
    get_current_quarter_start,
    get_quarter_dates,
    get_quarter_label,
    parse_validity_period,
    format_period_display,
    build_quota_url,
    detect_quarter_from_validity,
    EU_BASE_URL,
    UK_BASE_URL,
    QUARTER_INFO,
)


class TestGetCurrentQuarter:
    """Tests for get_current_quarter function"""

    def test_q1_january(self):
        assert get_current_quarter(date(2026, 1, 15)) == 1

    def test_q1_february(self):
        assert get_current_quarter(date(2026, 2, 28)) == 1

    def test_q1_march(self):
        assert get_current_quarter(date(2026, 3, 31)) == 1

    def test_q2_april(self):
        assert get_current_quarter(date(2026, 4, 1)) == 2

    def test_q2_june(self):
        assert get_current_quarter(date(2026, 6, 30)) == 2

    def test_q3_july(self):
        assert get_current_quarter(date(2026, 7, 1)) == 3

    def test_q3_september(self):
        assert get_current_quarter(date(2026, 9, 30)) == 3

    def test_q4_october(self):
        assert get_current_quarter(date(2026, 10, 1)) == 4

    def test_q4_december(self):
        assert get_current_quarter(date(2026, 12, 31)) == 4

    def test_default_uses_today(self):
        # Should not raise an error
        result = get_current_quarter()
        assert 1 <= result <= 4


class TestGetCurrentQuarterStart:
    """Tests for get_current_quarter_start function"""

    def test_q1_start(self):
        assert get_current_quarter_start(date(2026, 2, 15)) == "2026-01-01"

    def test_q2_start(self):
        assert get_current_quarter_start(date(2026, 5, 20)) == "2026-04-01"

    def test_q3_start(self):
        assert get_current_quarter_start(date(2026, 8, 10)) == "2026-07-01"

    def test_q4_start(self):
        assert get_current_quarter_start(date(2026, 11, 25)) == "2026-10-01"

    def test_different_year(self):
        assert get_current_quarter_start(date(2025, 3, 1)) == "2025-01-01"


class TestGetQuarterDates:
    """Tests for get_quarter_dates function"""

    def test_q1_dates(self):
        start, end = get_quarter_dates(date(2026, 2, 15))
        assert start == "2026-01-01"
        assert end == "2026-03-31"

    def test_q2_dates(self):
        start, end = get_quarter_dates(date(2026, 5, 1))
        assert start == "2026-04-01"
        assert end == "2026-06-30"

    def test_q3_dates(self):
        start, end = get_quarter_dates(date(2026, 9, 15))
        assert start == "2026-07-01"
        assert end == "2026-09-30"

    def test_q4_dates(self):
        start, end = get_quarter_dates(date(2026, 12, 1))
        assert start == "2026-10-01"
        assert end == "2026-12-31"


class TestGetQuarterLabel:
    """Tests for get_quarter_label function"""

    def test_q1_label(self):
        result = get_quarter_label(date(2026, 1, 15))
        assert "Q1" in result
        assert "2026" in result
        assert "Jan-Mar" in result

    def test_q4_label(self):
        result = get_quarter_label(date(2026, 12, 15))
        assert "Q4" in result
        assert "2026" in result
        assert "Oct-Dec" in result


class TestParseValidityPeriod:
    """Tests for parse_validity_period function"""

    def test_valid_period(self):
        start, end = parse_validity_period("01-01-2026  -  31-03-2026")
        assert start == "01-01-2026"
        assert end == "31-03-2026"

    def test_period_with_single_dash(self):
        start, end = parse_validity_period("01-04-2026 - 30-06-2026")
        assert start == "01-04-2026"
        assert end == "30-06-2026"

    def test_empty_string(self):
        start, end = parse_validity_period("")
        assert start is None
        assert end is None

    def test_none_input(self):
        start, end = parse_validity_period(None)
        assert start is None
        assert end is None

    def test_invalid_format(self):
        start, end = parse_validity_period("invalid date string")
        assert start is None
        assert end is None


class TestFormatPeriodDisplay:
    """Tests for format_period_display function"""

    def test_format_q1(self):
        result = format_period_display("01-01-2026", "31-03-2026")
        assert result == "01-Jan-2026 to 31-Mar-2026"

    def test_format_q4(self):
        result = format_period_display("01-10-2025", "31-12-2025")
        assert result == "01-Oct-2025 to 31-Dec-2025"

    def test_invalid_format_returns_original(self):
        result = format_period_display("invalid", "dates")
        assert "invalid" in result
        assert "dates" in result


class TestBuildQuotaUrl:
    """Tests for build_quota_url function"""

    def test_eu_url_with_date(self):
        url = build_quota_url("098967", "2026-01-01", "eu")
        assert EU_BASE_URL in url
        assert "Code=098967" in url
        assert "StartDate=2026-01-01" in url
        assert "Lang=en" in url

    def test_eu_url_default_date(self):
        url = build_quota_url("098967", region="eu")
        assert EU_BASE_URL in url
        assert "Code=098967" in url
        # Should have some date
        assert "StartDate=" in url

    def test_uk_url(self):
        url = build_quota_url("058001", region="uk")
        assert UK_BASE_URL in url
        assert "order_number=058001" in url

    def test_uk_url_pads_order_number(self):
        url = build_quota_url("58001", region="uk")
        assert "order_number=058001" in url

    def test_uk_url_ignores_date(self):
        url = build_quota_url("058001", "2026-01-01", "uk")
        assert "StartDate" not in url

    def test_invalid_region_raises_error(self):
        with pytest.raises(ValueError) as exc_info:
            build_quota_url("123456", region="invalid")
        assert "Unknown region" in str(exc_info.value)


class TestDetectQuarterFromValidity:
    """Tests for detect_quarter_from_validity function"""

    def test_q1_detection(self):
        quarter, year = detect_quarter_from_validity("01-01-2026")
        assert quarter == 1
        assert year == 2026

    def test_q2_detection(self):
        quarter, year = detect_quarter_from_validity("15-05-2026")
        assert quarter == 2
        assert year == 2026

    def test_q3_detection(self):
        quarter, year = detect_quarter_from_validity("01-07-2025")
        assert quarter == 3
        assert year == 2025

    def test_q4_detection(self):
        quarter, year = detect_quarter_from_validity("31-12-2026")
        assert quarter == 4
        assert year == 2026

    def test_invalid_returns_current(self):
        # Should return current quarter instead of raising error
        quarter, year = detect_quarter_from_validity("invalid")
        assert 1 <= quarter <= 4
        assert year >= 2025


class TestConstants:
    """Tests for configuration constants"""

    def test_quarter_info_complete(self):
        assert len(QUARTER_INFO) == 4
        for q in [1, 2, 3, 4]:
            assert q in QUARTER_INFO
            assert "months" in QUARTER_INFO[q]
            assert "start" in QUARTER_INFO[q]
            assert "end" in QUARTER_INFO[q]
            assert "label" in QUARTER_INFO[q]

    def test_eu_base_url_valid(self):
        assert EU_BASE_URL.startswith("https://")
        assert "ec.europa.eu" in EU_BASE_URL

    def test_uk_base_url_valid(self):
        assert UK_BASE_URL.startswith("https://")
        assert "trade-tariff.service.gov.uk" in UK_BASE_URL
