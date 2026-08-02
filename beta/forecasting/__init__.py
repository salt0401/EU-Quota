# -*- coding: utf-8 -*-
"""
EU Quota Forecasting Package  [EXPERIMENTAL]

Time-series forecasting for quota utilization using Prophet.
This module is fully decoupled from the main scraping/reporting pipeline.

Usage:
    from beta.forecasting import load_history, get_snapshot_summary
    data = load_history()
    print(get_snapshot_summary(data))

Phase 1: Data loading and preparation (current)
Phase 2: Preprocessing + baseline models (planned)

`load_history()` is the live source (the committed daily history).
`load_all_snapshots()` is legacy — nothing produces those files any more.
`REGIME_START` guards the 1 July 2026 boundary; do not train across it.
"""

from .data_loader import (
    load_history,
    load_all_snapshots,
    get_quota_time_series,
    get_all_quota_ids,
    get_snapshot_summary,
    prepare_prophet_df,
    MIN_PROPHET_DAYS,
    REGIME_START,
)

__all__ = [
    "load_history",
    "load_all_snapshots",
    "get_quota_time_series",
    "get_all_quota_ids",
    "get_snapshot_summary",
    "prepare_prophet_df",
    "MIN_PROPHET_DAYS",
    "REGIME_START",
]
