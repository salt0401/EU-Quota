# -*- coding: utf-8 -*-
"""
EU Quota Forecasting Package
Time-series forecasting for quota utilization using Prophet.

Phase 1: Data loading and preparation (current)
Phase 2: Preprocessing + baseline models (planned)
"""

from .data_loader import (
    load_all_snapshots,
    get_quota_time_series,
    get_all_quota_ids,
    get_snapshot_summary,
    prepare_prophet_df,
)

__all__ = [
    "load_all_snapshots",
    "get_quota_time_series",
    "get_all_quota_ids",
    "get_snapshot_summary",
    "prepare_prophet_df",
]
