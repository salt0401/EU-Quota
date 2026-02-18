# -*- coding: utf-8 -*-
"""
Forecasting Preprocessor (Phase 2)
Feature engineering for time-series forecasting.

Planned features:
- Rolling statistics (mean, std, trend)
- Seasonality indicators (quarter start/end effects)
- External regressors (e.g., steel price indices)
"""

import pandas as pd
from typing import Optional


def add_rolling_features(
    df: pd.DataFrame,
    window: int = 7,
    metrics: Optional[list[str]] = None,
) -> pd.DataFrame:
    """
    Add rolling window statistics to time series data.

    Args:
        df: DataFrame with ``ds`` and ``y`` columns.
        window: Rolling window size in days.
        metrics: List of rolling metrics to compute (e.g. ``["mean", "std"]``).

    Returns:
        pd.DataFrame: Input DataFrame with additional rolling feature columns.

    Raises:
        NotImplementedError: Phase 2 — not yet implemented.
    """
    raise NotImplementedError("add_rolling_features is planned for Phase 2")


def add_seasonality_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add quarter-boundary and seasonality indicator columns.

    Args:
        df: DataFrame with ``ds`` column.

    Returns:
        pd.DataFrame: Input DataFrame with seasonality flag columns.

    Raises:
        NotImplementedError: Phase 2 — not yet implemented.
    """
    raise NotImplementedError("add_seasonality_flags is planned for Phase 2")


def detect_outliers(
    df: pd.DataFrame,
    method: str = "iqr",
    threshold: float = 1.5,
) -> pd.DataFrame:
    """
    Flag outlier data points in the time series.

    Args:
        df: DataFrame with ``ds`` and ``y`` columns.
        method: Detection method (``"iqr"`` or ``"zscore"``).
        threshold: Sensitivity threshold.

    Returns:
        pd.DataFrame: Input DataFrame with ``is_outlier`` boolean column.

    Raises:
        NotImplementedError: Phase 2 — not yet implemented.
    """
    raise NotImplementedError("detect_outliers is planned for Phase 2")
