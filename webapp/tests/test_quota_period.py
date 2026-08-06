# -*- coding: utf-8 -*-
"""
Tests for the Jul-Jun quota year.

The boundary cases here are the whole point: a Jul-Jun year means January
belongs to the quota year that opened the *previous* July, and getting that
wrong silently mislabels six months of data.
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from webapp import quota_period as qp


class TestQuarterNumbering:
    """Jul-Sep is Q1, per the business definition -- NOT calendar Q3."""

    @pytest.mark.parametrize("month,expected", [
        (7, 1), (8, 1), (9, 1),
        (10, 2), (11, 2), (12, 2),
        (1, 3), (2, 3), (3, 3),
        (4, 4), (5, 4), (6, 4),
    ])
    def test_every_month_maps_to_the_right_quarter(self, month, expected):
        assert qp.quota_quarter(date(2026, month, 15)) == expected

    def test_july_is_q1_not_q3(self):
        # The trap: src/config.py calls July calendar-Q3. Both are correct for
        # their own purpose; only this one is correct for reporting.
        assert qp.quota_quarter(date(2026, 7, 1)) == 1


class TestQuotaYearLabelling:

    def test_july_opens_a_new_quota_year(self):
        assert qp.quota_year_label(date(2026, 7, 1)) == "2026/27"

    def test_june_still_belongs_to_the_year_that_opened_last_july(self):
        assert qp.quota_year_label(date(2027, 6, 30)) == "2026/27"

    def test_january_belongs_to_the_previous_julys_year(self):
        # The single most likely place to introduce an off-by-one-year bug.
        assert qp.quota_year_label(date(2027, 1, 15)) == "2026/27"
        assert qp.quota_year_start(date(2027, 1, 15)) == 2026

    def test_the_day_the_year_rolls_over(self):
        assert qp.quota_year_label(date(2027, 6, 30)) == "2026/27"
        assert qp.quota_year_label(date(2027, 7, 1)) == "2027/28"

    def test_label_pads_single_digit_years(self):
        assert qp.quota_year_label(date(2099, 8, 1)) == "2099/00"


class TestQuarterBoundaries:

    @pytest.mark.parametrize("d,start,end", [
        (date(2026, 7, 6),  date(2026, 7, 1),  date(2026, 9, 30)),
        (date(2026, 11, 2), date(2026, 10, 1), date(2026, 12, 31)),
        (date(2027, 2, 9),  date(2027, 1, 1),  date(2027, 3, 31)),
        (date(2027, 5, 20), date(2027, 4, 1),  date(2027, 6, 30)),
    ])
    def test_start_and_end(self, d, start, end):
        assert qp.quarter_start(d) == start
        assert qp.quarter_end(d) == end

    def test_oct_dec_quarter_ends_on_new_years_eve(self):
        # month + 3 would be 13; the code special-cases it.
        assert qp.quarter_end(date(2026, 12, 31)) == date(2026, 12, 31)

    def test_quarter_lengths_are_real_calendar_lengths(self):
        assert qp.quarter_length(date(2026, 7, 1)) == 92    # Jul+Aug+Sep
        assert qp.quarter_length(date(2026, 10, 1)) == 92   # Oct+Nov+Dec
        assert qp.quarter_length(date(2027, 1, 1)) == 90    # Jan+Feb+Mar, 2027
        assert qp.quarter_length(date(2028, 1, 1)) == 91    # leap year Feb

    def test_leap_day_is_handled(self):
        assert qp.quota_quarter(date(2028, 2, 29)) == 3
        assert qp.day_in_quarter(date(2028, 2, 29)) == 60


class TestDayInQuarter:
    """The axis that makes cross-quarter comparison possible."""

    def test_first_day_is_day_one(self):
        assert qp.day_in_quarter(date(2026, 7, 1)) == 1

    def test_counts_from_the_quarter_start(self):
        assert qp.day_in_quarter(date(2026, 7, 6)) == 6
        assert qp.day_in_quarter(date(2026, 8, 2)) == 33

    def test_last_day_equals_quarter_length(self):
        d = date(2026, 9, 30)
        assert qp.day_in_quarter(d) == qp.quarter_length(d) == 92

    def test_same_offset_in_different_quarters_is_comparable(self):
        # This is the requirement: "compare the same point in different
        # quarters". Day 33 of Q1 and day 33 of Q2 must both be 33.
        assert qp.day_in_quarter(date(2026, 8, 2)) == 33
        assert qp.day_in_quarter(date(2026, 11, 2)) == 33


class TestDescribe:

    def test_bundles_everything_for_a_known_date(self):
        p = qp.describe(date(2026, 8, 2))
        assert p.year_label == "2026/27"
        assert p.quarter == 1
        assert p.quarter_label == "Q1 (Jul-Sep)"
        assert p.start == date(2026, 7, 1)
        assert p.end == date(2026, 9, 30)
        assert p.day_in_quarter == 33
        assert p.quarter_length == 92
        assert p.key == "2026/27-Q1"

    def test_pct_elapsed_is_the_yardstick_for_burn_rate(self):
        # 33 of 92 days -> 35.9%. A quota 60% used at this point is running hot.
        assert qp.describe(date(2026, 8, 2)).pct_elapsed == 35.9
        assert qp.describe(date(2026, 7, 1)).pct_elapsed == 1.1
        assert qp.describe(date(2026, 9, 30)).pct_elapsed == 100.0


class TestQuartersSince:

    def test_enumerates_each_quarter_once_in_order(self):
        got = [p.key for p in qp.quarters_since(date(2026, 7, 6), date(2027, 5, 1))]
        assert got == ["2026/27-Q1", "2026/27-Q2", "2026/27-Q3", "2026/27-Q4"]

    def test_single_quarter_range(self):
        got = [p.key for p in qp.quarters_since(date(2026, 7, 6), date(2026, 8, 2))]
        assert got == ["2026/27-Q1"]

    def test_crosses_the_quota_year_boundary(self):
        got = [p.key for p in qp.quarters_since(date(2027, 5, 1), date(2027, 8, 1))]
        assert got == ["2026/27-Q4", "2027/28-Q1"]


class TestParsePeriodKey:
    """Values arrive from a URL query string, so bad input must not raise."""

    @pytest.mark.parametrize("key,expected", [
        ("2026/27-Q1", date(2026, 7, 1)),
        ("2026/27-Q2", date(2026, 10, 1)),
        ("2026/27-Q3", date(2027, 1, 1)),   # calendar year AFTER the year opened
        ("2026/27-Q4", date(2027, 4, 1)),
    ])
    def test_round_trips_every_quarter(self, key, expected):
        assert qp.parse_period_key(key) == expected

    def test_round_trip_through_describe(self):
        for d in (date(2026, 7, 6), date(2026, 11, 2), date(2027, 2, 9), date(2027, 5, 20)):
            assert qp.parse_period_key(qp.describe(d).key) == qp.quarter_start(d)

    @pytest.mark.parametrize("bad", ["", "garbage", "2026/27-Q9", "2026/27",
                                     "-Q1", "abc/de-Q1", None, "2026/27-QX"])
    def test_malformed_input_returns_none_instead_of_raising(self, bad):
        assert qp.parse_period_key(bad) is None


class TestRegimeStart:

    def test_matches_the_documented_boundary(self):
        assert qp.REGIME_START == date(2026, 7, 1)

    def test_regime_start_is_day_one_of_a_quota_year(self):
        # Convenient and not accidental: the new regimes began exactly on a
        # quota-year boundary, so no partial first quarter needs handling.
        assert qp.day_in_quarter(qp.REGIME_START) == 1
        assert qp.quota_quarter(qp.REGIME_START) == 1


class TestDaysRemaining:

    def test_counts_the_days_after_the_given_date(self):
        # 2026-08-02 is day 33 of Q1's 92 days, so 59 remain after it.
        p = qp.describe(date(2026, 8, 2))
        assert (p.day_in_quarter, p.quarter_length) == (33, 92)
        assert p.days_remaining == 59

    def test_is_zero_on_the_final_day_of_the_quarter(self):
        for d in (date(2026, 9, 30), date(2026, 12, 31),
                  date(2027, 3, 31), date(2027, 6, 30)):
            assert qp.describe(d).days_remaining == 0, d

    def test_is_one_less_than_the_length_on_day_one(self):
        for d in (date(2026, 7, 1), date(2026, 10, 1),
                  date(2027, 1, 1), date(2027, 4, 1)):
            p = qp.describe(d)
            assert p.days_remaining == p.quarter_length - 1, d

    def test_agrees_with_pct_elapsed(self):
        """Both describe the same clock, so they must not contradict.

        The masthead shows them side by side; a countdown measured from today
        while the percentage was measured from the data date would disagree
        visibly on any day the scrape was stale.
        """
        for d in (date(2026, 7, 15), date(2026, 8, 2), date(2027, 5, 20)):
            p = qp.describe(d)
            assert p.days_remaining + p.day_in_quarter == p.quarter_length
            assert p.pct_elapsed == round(
                100.0 * (p.quarter_length - p.days_remaining) / p.quarter_length, 1)
