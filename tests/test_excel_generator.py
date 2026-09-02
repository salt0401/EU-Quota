# -*- coding: utf-8 -*-
"""
Tests for src/excel_generator.py — the customer-workbook preparation step.

Narrow on purpose: the workbook writer itself is exercised end to end by the
daily run, and unit-testing XML assembly would pin implementation rather than
behaviour. What is pinned here is the arithmetic that decides what a cell says.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.excel_generator import prepare_uk_customer_data


class TestUKPercentageFallback:
    """The fallback used when a UK frame arrives without percentages.

    It never fires in the current pipeline — `uk_scraper.calculate_uk_metrics`
    computes both from raw kilograms first — but it is the last place a
    percentage can be invented, so its behaviour at the edges is worth holding.
    """

    def _frame(self, limit, allocated):
        return pd.DataFrame({
            'input_order_number': ['058600'],
            'input_quota_category': ['Hot rolled - 1'],
            'input_country': ['European Union'],
            'quota_limit_tonnes': [limit],
            'quota_allocated_tonnes': [allocated],
            'balance_remaining_tonnes': [
                None if limit is None else limit - allocated],
        })

    def test_missing_limit_gives_unknown_not_zero(self):
        """Changed 2026-09-02. It returned 0, which the workbook would show as
        "0%" — asserting that none of the quota had been used, about a quota
        whose limit was never learned. Unknown is the honest cell."""
        out = prepare_uk_customer_data(self._frame(0.0, 0.0))
        assert pd.isna(out['% Quota Allocated'].iloc[0])
        assert pd.isna(out['% Balance Remaining'].iloc[0])

    def test_a_real_limit_still_computes(self):
        """The guard must not swallow the ordinary case."""
        out = prepare_uk_customer_data(self._frame(1000.0, 750.0))
        assert out['% Quota Allocated'].iloc[0] == 0.75
        assert out['% Balance Remaining'].iloc[0] == 0.25

    def test_supplied_percentages_are_not_recomputed(self):
        """If the scraper already computed them from kilograms, they win.

        This is the load-bearing half: percentages derived here would come from
        tonnes that have already been rounded, so they are very slightly coarser
        than the ones computed upstream from raw kg.
        """
        df = self._frame(1000.0, 750.0)
        df['pct_allocated'] = [0.7503]
        df['pct_remaining'] = [0.2497]
        out = prepare_uk_customer_data(df)
        assert out['% Quota Allocated'].iloc[0] == 0.7503
