# -*- coding: utf-8 -*-
"""
Simple Baseline Models (Phase 2)
Non-Prophet baselines for comparison and sanity-checking.

Planned models:
- Naive last-value forecast
- Simple moving average
- Linear trend extrapolation
"""

import pandas as pd
from typing import Optional


def naive_forecast(
    df: pd.DataFrame,
    periods: int = 30,
) -> pd.DataFrame:
    """
    Naive forecast: repeat the last observed value.

    Args:
        df: DataFrame with ``ds`` and ``y`` columns.
        periods: Number of days to forecast.

    Returns:
        pd.DataFrame: Forecast DataFrame with ``ds`` and ``yhat`` columns.

    Raises:
        NotImplementedError: Phase 2 — not yet implemented.
    """
    raise NotImplementedError("naive_forecast is planned for Phase 2")


def moving_average_forecast(
    df: pd.DataFrame,
    window: int = 7,
    periods: int = 30,
) -> pd.DataFrame:
    """
    Simple moving average forecast.

    Args:
        df: DataFrame with ``ds`` and ``y`` columns.
        window: Lookback window in days.
        periods: Number of days to forecast.

    Returns:
        pd.DataFrame: Forecast DataFrame with ``ds`` and ``yhat`` columns.

    Raises:
        NotImplementedError: Phase 2 — not yet implemented.
    """
    raise NotImplementedError("moving_average_forecast is planned for Phase 2")


def linear_trend_forecast(
    df: pd.DataFrame,
    periods: int = 30,
) -> pd.DataFrame:
    """
    Linear trend extrapolation using least-squares fit.

    Args:
        df: DataFrame with ``ds`` and ``y`` columns.
        periods: Number of days to forecast.

    Returns:
        pd.DataFrame: Forecast DataFrame with ``ds``, ``yhat``, ``slope``,
        ``intercept`` columns.

    Raises:
        NotImplementedError: Phase 2 — not yet implemented.
    """
    raise NotImplementedError("linear_trend_forecast is planned for Phase 2")
