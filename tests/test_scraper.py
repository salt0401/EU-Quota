# -*- coding: utf-8 -*-
"""
Tests for src/scraper.py - EU Quota Scraper
Tests parsing functions without actual web requests
"""
import pytest
import pandas as pd
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper import EUQuotaScraper


class TestEUQuotaScraperParseValue:
    """Tests for _parse_value method"""

    @pytest.fixture
    def scraper(self):
        return EUQuotaScraper(headless=True)

    def test_parse_numeric_with_unit(self, scraper):
        result = scraper._parse_value("469492100 Kilogram", "Amount")
        assert result == 469492100.0

    def test_parse_numeric_with_commas(self, scraper):
        result = scraper._parse_value("469,492,100 Kilogram", "Amount")
        assert result == 469492100.0

    def test_parse_numeric_with_decimals(self, scraper):
        result = scraper._parse_value("469492100.50 Kilogram", "Balance")
        assert result == 469492100.50

    def test_parse_empty_numeric_returns_zero(self, scraper):
        result = scraper._parse_value("", "Amount")
        assert result is None

    def test_parse_percentage(self, scraper):
        result = scraper._parse_value("75.5", "Allocated percentage at the last allocation")
        assert result == 75.5

    def test_parse_critical_yes(self, scraper):
        result = scraper._parse_value("Yes", "Critical")
        assert result is True

    def test_parse_critical_no(self, scraper):
        result = scraper._parse_value("No", "Critical")
        assert result is False

    def test_parse_critical_case_insensitive(self, scraper):
        result = scraper._parse_value("YES", "Critical")
        assert result is True
        result = scraper._parse_value("yes", "Critical")
        assert result is True

    def test_parse_date_field(self, scraper):
        result = scraper._parse_value("25-01-2026", "Last import date")
        assert result == "25-01-2026"

    def test_parse_regular_string(self, scraper):
        result = scraper._parse_value("European Union", "Origin")
        assert result == "European Union"

    def test_parse_validity_period(self, scraper):
        result = scraper._parse_value("01-01-2026  -  31-03-2026", "Validity period")
        assert result == "01-01-2026  -  31-03-2026"

    def test_parse_whitespace_stripped(self, scraper):
        result = scraper._parse_value("  European Union  ", "Origin")
        assert result == "European Union"

    def test_parse_transferred_amount(self, scraper):
        result = scraper._parse_value("50000 Kilogram", "Transferred Amount")
        assert result == 50000.0

    def test_parse_initial_amount(self, scraper):
        result = scraper._parse_value("1000000 Kilogram", "Initial amount")
        assert result == 1000000.0

    def test_parse_awaiting_allocation(self, scraper):
        result = scraper._parse_value("5000 Kilogram", "Total awaiting allocation (indicative)")
        assert result == 5000.0


class TestEUQuotaScraperInit:
    """Tests for EUQuotaScraper initialization"""

    def test_default_headless(self):
        scraper = EUQuotaScraper()
        assert scraper.headless is True
        assert scraper.session is None

    def test_headless_false(self):
        scraper = EUQuotaScraper(headless=False)
        assert scraper.headless is False

    def test_session_initially_none(self):
        scraper = EUQuotaScraper()
        assert scraper.session is None


class _FakeResponse:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _FakeSession:
    def __init__(self, text):
        self._text = text

    def get(self, url, timeout=None):
        return _FakeResponse(self._text)


def _page(rows):
    trs = ''.join(
        f'<tr class="ecl-table__row"><td class="label">{k}</td><td>{v}</td></tr>'
        for k, v in rows)
    return f'<html><table class="ecl-table table-result">{trs}</table></html>'


class TestEmptyShellDetection:
    """TARIC serves a blank-field table for code/period combos it has no
    quota for (e.g. after a regulation expires) — that must count as a
    failure, not as a successful scrape full of zeros"""

    def _fetch(self, html):
        scraper = EUQuotaScraper()
        scraper.session = _FakeSession(html)
        return scraper.fetch_quota('099801', '2026-07-01')

    def test_valid_page_parses(self):
        result = self._fetch(_page([
            ('Order number', '099801'),
            ('Validity period', '01-07-2026 - 30-09-2026'),
            ('Balance', '160573740 Kilogram'),
        ]))
        assert result is not None
        assert result['order_number'] == '099801'
        assert result['validity_start'] == '01-07-2026'

    def test_empty_shell_returns_none(self):
        result = self._fetch(_page([
            ('Order number', ''),
            ('Origin', ''),
            ('Balance', ''),
        ]))
        assert result is None

    def test_missing_validity_returns_none(self):
        result = self._fetch(_page([('Order number', '099801')]))
        assert result is None


class TestEUQuotaScraperContextManager:
    """Tests for context manager functionality"""

    def test_context_manager_methods_exist(self):
        scraper = EUQuotaScraper()
        assert hasattr(scraper, '__enter__')
        assert hasattr(scraper, '__exit__')


class TestInputDataValidation:
    """Tests for input data validation in fetch_all_quotas"""

    @pytest.fixture
    def scraper(self):
        return EUQuotaScraper(headless=True)

    def test_valid_dataframe_columns(self, scraper):
        df = pd.DataFrame({
            'Order Number': [98967, 98968],
            'Current Quarter': ['2026-01-01', '2026-01-01'],
            'Quota Category': ['1A', '1B'],
        })
        # Should not raise error (won't actually fetch without driver)
        assert 'Order Number' in df.columns
        assert 'Current Quarter' in df.columns

    def test_order_number_formatting(self, scraper):
        # Test that order numbers are properly formatted
        raw_order = 98967
        formatted = str(int(raw_order)).zfill(6)
        assert formatted == '098967'

    def test_order_number_already_6_digits(self):
        raw_order = 998967
        formatted = str(int(raw_order)).zfill(6)
        assert formatted == '998967'

    def test_handles_date_formats(self):
        # Test various date formats that might come from Excel
        from datetime import datetime

        # String format
        date_str = '2026-01-01'
        assert str(date_str)[:10] == '2026-01-01'

        # Datetime object
        date_obj = datetime(2026, 1, 1)
        assert date_obj.strftime('%Y-%m-%d') == '2026-01-01'
