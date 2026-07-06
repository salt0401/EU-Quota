# -*- coding: utf-8 -*-
"""
Tests for src/data_processor.py - Data calculations and transformations
"""
import pytest
import pandas as pd
import numpy as np
from datetime import date
import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data_processor import (
    clean_quota_data,
    calculate_quota_metrics,
    extract_period_info,
    prepare_customer_data,
    get_quota_summary,
)


class TestCleanQuotaData:
    """Tests for clean_quota_data function"""

    def test_standardizes_column_names(self):
        df = pd.DataFrame({
            'Order Number': ['098967'],
            'Validity Period': ['01-01-2026 - 31-03-2026'],
            'Initial Amount': [1000000],
        })
        result = clean_quota_data(df)
        assert 'order_number' in result.columns
        assert 'validity_period' in result.columns
        assert 'initial_amount' in result.columns

    def test_converts_numeric_columns(self):
        df = pd.DataFrame({
            'initial_amount': ['1000000'],
            'amount': ['500000'],
            'balance': ['300000'],
        })
        result = clean_quota_data(df)
        assert result['initial_amount'].dtype in [np.float64, np.int64]
        assert result['amount'].dtype in [np.float64, np.int64]

    def test_handles_empty_numeric_values(self):
        df = pd.DataFrame({
            'initial_amount': ['', None, '1000'],
            'amount': [None, '', '500'],
        })
        result = clean_quota_data(df)
        # Empty values should be filled with 0
        assert result['initial_amount'].iloc[0] == 0
        assert result['initial_amount'].iloc[1] == 0
        assert result['initial_amount'].iloc[2] == 1000

    def test_renames_long_column_names(self):
        df = pd.DataFrame({
            'total_awaiting_allocation_(indicative)': [1000],
            'allocated_percentage_at_the_last_allocation': [50.5],
        })
        result = clean_quota_data(df)
        assert 'awaiting_allocation' in result.columns
        assert 'allocation_pct' in result.columns

    def test_renames_awaiting_allocation_with_doubled_space(self):
        # The TARIC label carries a doubled space, which used to produce
        # 'total_awaiting_allocation__(indicative)' and miss the rename —
        # silently zeroing awaiting_allocation in the Balance Remaining formula
        df = pd.DataFrame({
            'Total awaiting allocation  (indicative)': [125256],
        })
        result = clean_quota_data(df)
        assert 'awaiting_allocation' in result.columns
        assert result['awaiting_allocation'].iloc[0] == 125256

    def test_renames_awaiting_allocation_double_underscore(self):
        # Old snapshots saved the already-broken column name
        df = pd.DataFrame({
            'total_awaiting_allocation__(indicative)': [5000],
        })
        result = clean_quota_data(df)
        assert 'awaiting_allocation' in result.columns

    def test_renames_awaiting_allocation_spaced_parens(self):
        # '(indicative)' sits in its own HTML node on the live TARIC page, so
        # separator-joined text yields 'Total awaiting allocation ( indicative )'
        df = pd.DataFrame({
            'Total awaiting allocation ( indicative )': [7000],
        })
        result = clean_quota_data(df)
        assert 'awaiting_allocation' in result.columns
        assert result['awaiting_allocation'].iloc[0] == 7000


class TestCalculateQuotaMetrics:
    """Tests for calculate_quota_metrics function - MEPS formulas"""

    def test_quota_limit_formula(self):
        """Quota Limit = amount + transferred_amount"""
        df = pd.DataFrame({
            'amount': [1000000],
            'transferred_amount': [50000],
            'balance': [500000],
            'awaiting_allocation': [0],
        })
        result = calculate_quota_metrics(df)
        assert result['quota_limit'].iloc[0] == 1050000

    def test_balance_remaining_formula(self):
        """Balance Remaining = balance - awaiting_allocation"""
        df = pd.DataFrame({
            'amount': [1000000],
            'transferred_amount': [0],
            'balance': [500000],
            'awaiting_allocation': [10000],
        })
        result = calculate_quota_metrics(df)
        assert result['balance_remaining'].iloc[0] == 490000

    def test_balance_remaining_not_negative(self):
        """Balance remaining should be clipped to 0"""
        df = pd.DataFrame({
            'amount': [1000000],
            'transferred_amount': [0],
            'balance': [10000],
            'awaiting_allocation': [50000],  # More than balance
        })
        result = calculate_quota_metrics(df)
        assert result['balance_remaining'].iloc[0] == 0

    def test_quota_allocated_formula(self):
        """Quota Allocated = Quota Limit - Balance Remaining"""
        df = pd.DataFrame({
            'amount': [1000000],
            'transferred_amount': [0],
            'balance': [400000],
            'awaiting_allocation': [0],
        })
        result = calculate_quota_metrics(df)
        # quota_limit = 1000000, balance_remaining = 400000
        # quota_allocated = 1000000 - 400000 = 600000
        assert result['quota_allocated'].iloc[0] == 600000

    def test_percentage_allocated(self):
        """% Allocated = (Quota Allocated / Quota Limit) * 100"""
        df = pd.DataFrame({
            'amount': [1000000],
            'transferred_amount': [0],
            'balance': [250000],
            'awaiting_allocation': [0],
        })
        result = calculate_quota_metrics(df)
        # quota_limit = 1000000, quota_allocated = 750000
        # pct_allocated = 75%
        assert result['pct_allocated'].iloc[0] == 75.0

    def test_percentage_remaining(self):
        """% Remaining = (Balance Remaining / Quota Limit) * 100"""
        df = pd.DataFrame({
            'amount': [1000000],
            'transferred_amount': [0],
            'balance': [250000],
            'awaiting_allocation': [0],
        })
        result = calculate_quota_metrics(df)
        # balance_remaining = 250000, quota_limit = 1000000
        # pct_remaining = 25%
        assert result['pct_remaining'].iloc[0] == 25.0

    def test_handles_zero_quota_limit(self):
        """Division by zero should be handled"""
        df = pd.DataFrame({
            'amount': [0],
            'transferred_amount': [0],
            'balance': [0],
            'awaiting_allocation': [0],
        })
        result = calculate_quota_metrics(df)
        assert result['pct_allocated'].iloc[0] == 0.0
        assert result['pct_remaining'].iloc[0] == 0.0

    def test_creates_missing_columns(self):
        """Should create missing numeric columns with default 0"""
        df = pd.DataFrame({
            'order_number': ['098967'],
        })
        result = calculate_quota_metrics(df)
        assert 'amount' in result.columns
        assert 'transferred_amount' in result.columns
        assert 'balance' in result.columns


class TestExtractPeriodInfo:
    """Tests for extract_period_info function"""

    def test_extracts_validity_period(self):
        df = pd.DataFrame({
            'validity_start': ['01-01-2026'],
            'validity_end': ['31-03-2026'],
        })
        period_display, latest_data, quarter, year = extract_period_info(df)
        assert '01-Jan-2026' in period_display
        assert '31-Mar-2026' in period_display
        assert quarter == 1
        assert year == 2026

    def test_handles_missing_validity(self):
        df = pd.DataFrame({
            'order_number': ['098967'],
        })
        period_display, latest_data, quarter, year = extract_period_info(df)
        assert period_display == ""
        # Should return current quarter/year
        assert 1 <= quarter <= 4

    def test_extracts_scrape_timestamp(self):
        df = pd.DataFrame({
            'scrape_timestamp': ['2026-01-25T10:30:00'],
            'validity_start': ['01-01-2026'],
            'validity_end': ['31-03-2026'],
        })
        period_display, latest_data, quarter, year = extract_period_info(df)
        assert '25-Jan-2026' in latest_data


class TestPrepareCustomerData:
    """Tests for prepare_customer_data function"""

    def test_selects_correct_columns(self):
        df = pd.DataFrame({
            'input_quota_category': ['Category 1A'],
            'origin': ['European Union'],
            'quota_limit': [1000000000],  # in kg
            'quota_allocated': [500000000],
            'pct_allocated': [50.0],
            'balance_remaining': [500000000],
            'pct_remaining': [50.0],
            'extra_column': ['ignored'],
        })
        result = prepare_customer_data(df)
        assert 'Quota Category' in result.columns
        assert 'Country' in result.columns
        assert 'extra_column' not in result.columns

    def test_converts_kg_to_tonnes(self):
        df = pd.DataFrame({
            'input_quota_category': ['Category 1A'],
            'origin': ['EU'],
            'quota_limit': [1000000],  # 1000 tonnes in kg
            'quota_allocated': [500000],
            'balance_remaining': [500000],
            'pct_allocated': [50.0],
            'pct_remaining': [50.0],
        })
        result = prepare_customer_data(df)
        # Should be divided by 1000
        assert result['Quota Limit (Tonnes)'].iloc[0] == 1000.0
        assert result['Quota Allocated (Tonnes)'].iloc[0] == 500.0
        assert result['Balance Remaining (Tonnes)'].iloc[0] == 500.0

    def test_renames_columns_for_display(self):
        df = pd.DataFrame({
            'input_quota_category': ['1A'],
            'origin': ['EU'],
            'quota_limit': [1000],
            'quota_allocated': [500],
            'pct_allocated': [50.0],
            'balance_remaining': [500],
            'pct_remaining': [50.0],
        })
        result = prepare_customer_data(df)
        assert 'Quota Category' in result.columns
        assert 'Country' in result.columns
        assert '% Quota Allocated' in result.columns

    def test_uses_input_country_as_fallback(self):
        df = pd.DataFrame({
            'input_quota_category': ['1A'],
            'input_country': ['Germany'],
            'quota_limit': [1000],
        })
        result = prepare_customer_data(df)
        assert 'Country' in result.columns
        assert result['Country'].iloc[0] == 'Germany'

    def test_prefers_curated_input_country_over_origin(self):
        # Input file names follow Annex I of Reg. 2026/1457; raw TARIC origin
        # is unnormalized and can contain concatenated exclusion lists
        df = pd.DataFrame({
            'input_quota_category': ['1.A'],
            'input_country': ['Türkiye'],
            'origin': ['Countries subject to measures Kazakhstan'],
            'quota_limit': [1000],
        })
        result = prepare_customer_data(df)
        assert result['Country'].iloc[0] == 'Türkiye'

    def test_falls_back_to_origin_when_input_country_empty(self):
        df = pd.DataFrame({
            'input_quota_category': ['1.A'],
            'input_country': [''],
            'origin': ['Japan'],
            'quota_limit': [1000],
        })
        result = prepare_customer_data(df)
        assert result['Country'].iloc[0] == 'Japan'

    def test_excludes_failed_scrapes_from_customer_report(self):
        # A failed scrape has no figures; a 0-tonne row would read as a real,
        # fully-exhausted-or-empty quota to customers
        df = pd.DataFrame({
            'input_quota_category': ['1.A', '1.A'],
            'input_country': ['Türkiye', 'Japan'],
            'input_order_number': ['099801', '099802'],
            'origin': ['Türkiye', None],
            'quota_limit': [1000000, 0],
            'quota_allocated': [500000, 0],
            'balance_remaining': [500000, 0],
            'pct_allocated': [50.0, 0.0],
            'pct_remaining': [50.0, 0.0],
            'scrape_status': [None, 'failed'],
        })
        result = prepare_customer_data(df)
        assert len(result) == 1
        assert result['Country'].iloc[0] == 'Türkiye'

    def test_percentages_converted_to_fractions(self):
        # Internal metrics are 0-100; the customer sheet uses Excel '0%'
        # format, so values must be 0-1. A 0.5%-allocated quota must come
        # out as 0.005, not 0.5 (which Excel would display as 50%)
        df = pd.DataFrame({
            'input_quota_category': ['1.A'],
            'origin': ['EU'],
            'quota_limit': [1000000],
            'quota_allocated': [5000],
            'balance_remaining': [995000],
            'pct_allocated': [0.5],
            'pct_remaining': [99.5],
        })
        result = prepare_customer_data(df)
        assert result['% Quota Allocated'].iloc[0] == pytest.approx(0.005)
        assert result['% Balance Remaining'].iloc[0] == pytest.approx(0.995)


class TestGetQuotaSummary:
    """Tests for get_quota_summary function"""

    def test_counts_total_quotas(self):
        df = pd.DataFrame({
            'order_number': ['098967', '098968', '098969'],
        })
        summary = get_quota_summary(df)
        assert summary['total_quotas'] == 3

    def test_counts_high_usage(self):
        df = pd.DataFrame({
            'pct_allocated': [50, 80, 90, 76],
        })
        summary = get_quota_summary(df)
        # > 75%: 80, 90, 76 = 3 quotas
        assert summary['high_usage_count'] == 3

    def test_counts_exhausted(self):
        df = pd.DataFrame({
            'pct_allocated': [50, 100, 100.5, 99.9],
        })
        summary = get_quota_summary(df)
        # >= 100%: 100, 100.5 = 2 quotas
        assert summary['exhausted_count'] == 2

    def test_counts_critical(self):
        df = pd.DataFrame({
            'critical': [True, False, True, False],
        })
        summary = get_quota_summary(df)
        assert summary['critical_count'] == 2

    def test_handles_missing_columns(self):
        df = pd.DataFrame({
            'order_number': ['098967'],
        })
        summary = get_quota_summary(df)
        assert summary['high_usage_count'] == 0
        assert summary['critical_count'] == 0
        assert summary['exhausted_count'] == 0


class TestEdgeCases:
    """Edge case tests for data processor"""

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = clean_quota_data(df)
        assert len(result) == 0

    def test_large_numbers(self):
        df = pd.DataFrame({
            'amount': [999999999999],
            'transferred_amount': [0],
            'balance': [500000000000],
            'awaiting_allocation': [0],
        })
        result = calculate_quota_metrics(df)
        assert result['quota_limit'].iloc[0] == 999999999999
        assert result['pct_allocated'].iloc[0] == pytest.approx(50.0, rel=0.1)

    def test_decimal_values(self):
        df = pd.DataFrame({
            'amount': [1000000.5],
            'transferred_amount': [0.5],
            'balance': [500000.25],
            'awaiting_allocation': [0.25],
        })
        result = calculate_quota_metrics(df)
        assert result['quota_limit'].iloc[0] == 1000001.0
        assert result['balance_remaining'].iloc[0] == 500000.0
