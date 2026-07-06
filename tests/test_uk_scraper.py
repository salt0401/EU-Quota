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
    normalize_order_number,
    UK_QUOTA_ORDER_NUMBERS,
)


class TestNormalizeOrderNumber:
    """One blank cell flips the workbook column to float64; the normalizer
    must survive int, float, and string forms"""

    def test_int(self):
        assert normalize_order_number(58600) == '058600'

    def test_float_from_dtype_drift(self):
        assert normalize_order_number(58600.0) == '058600'

    def test_string_with_leading_zero(self):
        assert normalize_order_number('058600') == '058600'

    def test_plain_string(self):
        assert normalize_order_number('58600') == '058600'


class _FakeResponse:
    """Minimal stand-in for requests.Response"""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    """Records the requested URL and returns a canned JSON payload"""

    def __init__(self, payload):
        self._payload = payload
        self.last_url = None

    def get(self, url, timeout=None):
        self.last_url = url
        return _FakeResponse(self._payload)


class TestUKQuotaScraperFetchParsing:
    """Tests for fetch_quota JSON parsing against a mocked API session"""

    def _scraper_with(self, payload):
        scraper = UKQuotaScraper(headless=True)
        scraper.session = _FakeSession(payload)
        return scraper

    def test_parses_balances_and_status(self):
        # Shape taken from a live 058600 response (steel trade measure, Q1 2026-27)
        payload = {'data': [{'attributes': {
            'balance': '90248498.8',
            'initial_volume': '93750000.0',
            'validity_start_date': '2026-07-01T00:00:00.000Z',
            'validity_end_date': '2026-09-30T23:59:59.000Z',
            'status': 'Open',
        }}]}
        result = self._scraper_with(payload).fetch_quota('058600')
        assert result['current_balance_kg'] == 90248498.8
        assert result['opening_balance_kg'] == 93750000.0
        assert result['status'] == 'Open'
        assert '2026' in result['validity_period']

    def test_pads_order_number_in_url(self):
        scraper = self._scraper_with({'data': []})
        scraper.fetch_quota('58600')
        assert 'order_number=058600' in scraper.session.last_url

    def test_no_data_returns_no_data_status(self):
        result = self._scraper_with({'data': []}).fetch_quota('058600')
        assert result['status'] == 'No Data'
        assert result['current_balance_kg'] is None


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
    """UK_QUOTA_ORDER_NUMBERS pins Table 4 of the DBT steel trade measure
    effective 1 July 2026 (order numbers 058600-058671)"""

    def test_all_order_numbers_6_digits(self):
        for key, order_num in UK_QUOTA_ORDER_NUMBERS.items():
            assert len(order_num) == 6, f"Order number {order_num} for {key} is not 6 digits"

    def test_all_order_numbers_start_with_058(self):
        for key, order_num in UK_QUOTA_ORDER_NUMBERS.items():
            assert order_num.startswith('058'), f"Order number {order_num} for {key} doesn't start with 058"

    def test_expected_order_number_set(self):
        nums = sorted(UK_QUOTA_ORDER_NUMBERS.values())
        assert len(nums) == 75
        assert len(set(nums)) == 75, "duplicate order numbers"
        # Table 4 block (058600-058671) plus the three Category-1
        # authorised-use quotas (058673-058675; 058672 is unused)
        expected = list(range(58600, 58672)) + [58673, 58674, 58675]
        assert [int(n) for n in nums] == expected

    def test_twenty_categories(self):
        cats = {k.split('_', 1)[0] for k in UK_QUOTA_ORDER_NUMBERS}
        assert len(cats) == 20
        assert cats == {'1', '4', '5', '6', '7', '12A', '12B', '13', '14', '15',
                        '16', '17', '19', '20', '21', '25A', '25B', '26', '27', '28'}

    def test_spot_checks_against_table4(self):
        assert UK_QUOTA_ORDER_NUMBERS['1_European_Union'] == '058600'
        assert UK_QUOTA_ORDER_NUMBERS['1_Residual'] == '058603'
        assert UK_QUOTA_ORDER_NUMBERS['13_Turkey'] == '058626'
        assert UK_QUOTA_ORDER_NUMBERS['28_Residual'] == '058671'

    def test_every_category_has_eu_and_residual_quota(self):
        cats = {k.split('_', 1)[0] for k in UK_QUOTA_ORDER_NUMBERS}
        for cat in cats:
            assert f'{cat}_European_Union' in UK_QUOTA_ORDER_NUMBERS
            assert f'{cat}_Residual' in UK_QUOTA_ORDER_NUMBERS


class TestUKCustomerReportExclusions:
    """Failed / No-Data rows carry only template-derived figures and must not
    render as untouched quotas in the customer sheet"""

    def test_failed_rows_excluded(self):
        from src.excel_generator import prepare_uk_customer_data
        df = pd.DataFrame({
            'input_quota_category': ['Cat 1', 'Cat 1'],
            'input_country': ['European Union', 'India'],
            'input_order_number': ['058600', '058601'],
            'opening_balance_kg': [93750000.0, 8364000.0],
            'current_balance_kg': [90000000.0, 8364000.0],
            'scrape_status': [None, 'failed'],
        })
        result = prepare_uk_customer_data(calculate_uk_metrics(df))
        assert len(result) == 1
        assert result['Country'].iloc[0] == 'European Union'

    def test_all_failed_returns_empty(self):
        from src.excel_generator import prepare_uk_customer_data
        df = pd.DataFrame({
            'input_quota_category': ['Cat 1'],
            'input_country': ['European Union'],
            'input_order_number': ['058600'],
            'opening_balance_kg': [93750000.0],
            'current_balance_kg': [93750000.0],
            'scrape_status': ['failed'],
        })
        result = prepare_uk_customer_data(calculate_uk_metrics(df))
        assert result.empty


class TestUKScraperInit:
    """Tests for UKQuotaScraper initialization"""

    def test_default_headless(self):
        scraper = UKQuotaScraper()
        assert scraper.headless is True
        assert scraper.session is None

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
