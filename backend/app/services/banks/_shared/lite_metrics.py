"""
Compatibility shim — Lite metrics live in app.services.pipeline.reporting.

Do not add logic here. New imports should use:
    from app.services.pipeline.reporting import build_lite_report_model
"""

from app.services.pipeline.reporting.lite_metrics import *  # noqa: F401,F403
from app.services.pipeline.reporting.lite_metrics import (
    ACCOUNT_INFO_KEYS,
    LITE_CATEGORY_MAP,
    MONTHLY_METRIC_KEYS,
    SUMMARY_STAT_KEYS,
    build_eod_series,
    build_lite_report_model,
    compute_account_info,
    compute_monthly_analysis,
    compute_summary_stats,
    filter_transactions,
    normalize_transactions,
    top_n_transactions,
)

__all__ = [
    "ACCOUNT_INFO_KEYS",
    "LITE_CATEGORY_MAP",
    "MONTHLY_METRIC_KEYS",
    "SUMMARY_STAT_KEYS",
    "build_eod_series",
    "build_lite_report_model",
    "compute_account_info",
    "compute_monthly_analysis",
    "compute_summary_stats",
    "filter_transactions",
    "normalize_transactions",
    "top_n_transactions",
]
