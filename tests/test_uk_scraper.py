# -*- coding: utf-8 -*-
"""
Tests for src/uk_scraper.py - UK Quota Scraper
Tests parsing functions without actual web requests
"""
import pytest
import pandas as pd
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.uk_scraper import (
    UKQuotaScraper,
    convert_kg_to_tonnes,
    calculate_uk_metrics,
    UK_QUOTA_ORDER_NUMBERS,
)


class TestUKQuotaScraperParseKgValue:
    """Tests for _parse_kg_value method"""

    @pytest.fixture
    def scraper(self):
        return UKQuotaScraper(headless=True)

    def test_parse_standard_format(self, scraper):
        result = scraper._parse_kg_value("183,592,000.000 Kilogram (kg)")
        assert result == 183592000.0

    def test_parse_with_commas(self, scraper):
        result = scraper._parse_kg_value("1,234,567 Kilogram")
        assert result == 1234567.0

    def test_parse_lowercase_kg(self, scraper):
        result = scraper._parse_kg_value("1000 kg")
        assert result == 1000.0

    def test_parse_without_unit(self, scraper):
        result = scraper._parse_kg_value("1,000,000")
        assert result == 1000000.0

    def test_parse_decimal(self, scraper):
        result = scraper._parse_kg_value("165,243,093.260 Kilogram (kg)")
        assert result == 165243093.26

    def test_parse_empty_returns_none(self, scraper):
        result = scraper._parse_kg_value("")
        assert result is None

    def test_parse_none_returns_none(self, scraper):
        result = scraper._parse_kg_value(None)
        assert result is None

    def test_parse_just_kilogram(self, scraper):
        result = scraper._parse_kg_value("500000 Kilogram")
        assert result == 500000.0


class TestUKQuotaScraperParseDateRange:
    """Tests for _parse_date_range method"""

    @pytest.fixture
    def scraper(self):
        return UKQuotaScraper(headless=True)

    def test_parse_standard_range(self, scraper):
        start, end = scraper._parse_date_range("1 January 2026 to 31 March 2026")
        assert start == "1 January 2026"
        assert end == "31 March 2026"

    def test_parse_q2_range(self, scraper):
        start, end = scraper._parse_date_range("1 April 2026 to 30 June 2026")
        assert start == "1 April 2026"
        assert end == "30 June 2026"

    def test_parse_empty_returns_none(self, scraper):
        start, end = scraper._parse_date_range("")
        assert start is None
        assert end is None

    def test_parse_none_returns_none(self, scraper):
        start, end = scraper._parse_date_range(None)
        assert start is None
        assert end is None

    def test_parse_invalid_format(self, scraper):
        start, end = scraper._parse_date_range("invalid date range")
        assert start is None
        assert end is None


class TestUKQuotaScraperBuildUrl:
    """Tests for _build_url method"""

    @pytest.fixture
    def scraper(self):
        return UKQuotaScraper(headless=True)

    def test_build_url_6_digit(self, scraper):
        url = scraper._build_url("058001")
        assert "order_number=058001" in url
        assert scraper.base_url in url

    def test_build_url_pads_short_number(self, scraper):
        url = scraper._build_url("58001")
        assert "order_number=058001" in url

    def test_build_url_integer_input(self, scraper):
        url = scraper._build_url(58001)
        assert "order_number=058001" in url


class TestConvertKgToTonnes:
    """Tests for convert_kg_to_tonnes function"""

    def test_standard_conversion(self):
        result = convert_kg_to_tonnes(1000)
        assert result == 1.0

    def test_large_number(self):
        result = convert_kg_to_tonnes(183592000)
        assert result == 183592.0

    def test_decimal_result(self):
        result = convert_kg_to_tonnes(1500)
        assert result == 1.5

    def test_zero(self):
        result = convert_kg_to_tonnes(0)
        assert result == 0.0

    def test_none_returns_zero(self):
        result = convert_kg_to_tonnes(None)
        assert result == 0.0

    def test_nan_returns_zero(self):
        import numpy as np
        result = convert_kg_to_tonnes(np.nan)
        assert result == 0.0


class TestCalculateUKMetrics:
    """Tests for calculate_uk_metrics function"""

    def test_calculates_quota_limit_tonnes(self):
        df = pd.DataFrame({
            'opening_balance_kg': [187671000],
            'current_balance_kg': [100000000],
        })
        result = calculate_uk_metrics(df)
        assert result['quota_limit_tonnes'].iloc[0] == 187671.0

    def test_calculates_balance_remaining_tonnes(self):
        df = pd.DataFrame({
            'opening_balance_kg': [187671000],
            'current_balance_kg': [100000000],
        })
        result = calculate_uk_metrics(df)
        assert result['balance_remaining_tonnes'].iloc[0] == 100000.0

    def test_calculates_quota_allocated_tonnes(self):
        df = pd.DataFrame({
            'opening_balance_kg': [1000000],  # 1000 tonnes
            'current_balance_kg': [400000],   # 400 tonnes remaining
        })
        result = calculate_uk_metrics(df)
        # Allocated = 1000 - 400 = 600 tonnes
        assert result['quota_allocated_tonnes'].iloc[0] == 600.0

    def test_calculates_percentage_allocated(self):
        df = pd.DataFrame({
            'opening_balance_kg': [1000000],  # 1000 tonnes
            'current_balance_kg': [250000],   # 250 tonnes remaining (75% used)
        })
        result = calculate_uk_metrics(df)
        # 750 allocated / 1000 total = 0.75
        assert result['pct_allocated'].iloc[0] == pytest.approx(0.75)

    def test_calculates_percentage_remaining(self):
        df = pd.DataFrame({
            'opening_balance_kg': [1000000],
            'current_balance_kg': [250000],
        })
        result = calculate_uk_metrics(df)
        # 250 remaining / 1000 total = 0.25
        assert result['pct_remaining'].iloc[0] == pytest.approx(0.25)

    def test_handles_zero_opening_balance(self):
        df = pd.DataFrame({
            'opening_balance_kg': [0],
            'current_balance_kg': [0],
        })
        result = calculate_uk_metrics(df)
        assert result['pct_allocated'].iloc[0] == 0
        assert result['pct_remaining'].iloc[0] == 0


class TestUKQuotaOrderNumbers:
    """Tests for UK_QUOTA_ORDER_NUMBERS constant"""

    def test_all_order_numbers_6_digits(self):
        for key, order_num in UK_QUOTA_ORDER_NUMBERS.items():
            assert len(order_num) == 6, f"Order number {order_num} for {key} is not 6 digits"

    def test_all_order_numbers_start_with_058(self):
        for key, order_num in UK_QUOTA_ORDER_NUMBERS.items():
            assert order_num.startswith('058'), f"Order number {order_num} for {key} doesn't start with 058"

    def test_category_1a_exists(self):
        assert '1A_EU' in UK_QUOTA_ORDER_NUMBERS
        assert '1A_All_others' in UK_QUOTA_ORDER_NUMBERS

    def test_category_1b_updated_for_2026(self):
        # Old 058003 should be replaced with 058110, 058111, 058112
        assert '1B_All_others_1' in UK_QUOTA_ORDER_NUMBERS
        assert '1B_All_others_2' in UK_QUOTA_ORDER_NUMBERS
        assert '1B_All_others_3' in UK_QUOTA_ORDER_NUMBERS
        assert UK_QUOTA_ORDER_NUMBERS['1B_All_others_1'] == '058110'
        assert UK_QUOTA_ORDER_NUMBERS['1B_All_others_2'] == '058111'
        assert UK_QUOTA_ORDER_NUMBERS['1B_All_others_3'] == '058112'

    def test_category_13_updated_for_2026(self):
        # Old 058019 should be replaced with 058020
        assert UK_QUOTA_ORDER_NUMBERS['13_All_others'] == '058020'
        # New individual country quotas
        assert '13_Egypt' in UK_QUOTA_ORDER_NUMBERS
        assert '13_Vietnam' in UK_QUOTA_ORDER_NUMBERS
        assert '13_Algeria' in UK_QUOTA_ORDER_NUMBERS
        assert '13_New_Zealand' in UK_QUOTA_ORDER_NUMBERS
        assert '13_Norway' in UK_QUOTA_ORDER_NUMBERS

    def test_no_duplicate_order_numbers_in_different_categories(self):
        # Some order numbers can be reused within same category (e.g., individual caps)
        # But check that major categories have unique primary order numbers
        primary_orders = [
            UK_QUOTA_ORDER_NUMBERS['1A_EU'],
            UK_QUOTA_ORDER_NUMBERS['4_EU'],
            UK_QUOTA_ORDER_NUMBERS['5_EU'],
            UK_QUOTA_ORDER_NUMBERS['6_EU'],
            UK_QUOTA_ORDER_NUMBERS['7_EU'],
        ]
        # These should all be unique
        assert len(primary_orders) == len(set(primary_orders))


class TestUKScraperInit:
    """Tests for UKQuotaScraper initialization"""

    def test_default_headless(self):
        scraper = UKQuotaScraper()
        assert scraper.headless is True
        assert scraper.driver is None

    def test_headless_false(self):
        scraper = UKQuotaScraper(headless=False)
        assert scraper.headless is False

    def test_base_url_set(self):
        scraper = UKQuotaScraper()
        assert "trade-tariff.service.gov.uk" in scraper.base_url


class TestIndividualCapLogic:
    """Tests for individual country cap handling"""

    def test_country_with_asterisk_detected(self):
        country = "Japan*"
        is_individual_cap = country.endswith('*')
        assert is_individual_cap is True

    def test_country_without_asterisk(self):
        country = "European Union"
        is_individual_cap = country.endswith('*')
        assert is_individual_cap is False

    def test_all_others_not_individual_cap(self):
        country = "All others"
        is_individual_cap = country.endswith('*')
        assert is_individual_cap is False
