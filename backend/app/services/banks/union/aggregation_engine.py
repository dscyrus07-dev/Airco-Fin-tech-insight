"""Phase 4: union aggregation wraps shared pipeline.aggregation."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from app.services.pipeline.aggregation.engine import (
    CategorySummary,
    MonthlySummary,
    SharedAggregationEngine,
    SharedAggregationResult,
)

logger = logging.getLogger(__name__)


@dataclass
class UnionAggregationResult:
    debit_categories: List[CategorySummary]
    credit_categories: List[CategorySummary]
    monthly_summaries: List[MonthlySummary]
    weekly_credits: Dict[str, float]
    weekly_debits: Dict[str, float]
    recurring_total: float
    one_time_total: float
    recurring_count: int
    one_time_count: int
    top_debit_merchants: List[Dict[str, Any]]
    top_credit_merchants: List[Dict[str, Any]]
    total_credits: float
    total_debits: float
    opening_balance: float
    closing_balance: float

    def to_dict(self) -> dict:
        return {
            "debit_categories": [
                {
                    "category": c.category,
                    "total": c.total_amount,
                    "count": c.transaction_count,
                    "avg": c.avg_amount,
                    "percentage": c.percentage,
                }
                for c in self.debit_categories
            ],
            "credit_categories": [
                {
                    "category": c.category,
                    "total": c.total_amount,
                    "count": c.transaction_count,
                    "avg": c.avg_amount,
                    "percentage": c.percentage,
                }
                for c in self.credit_categories
            ],
            "monthly": [
                {
                    "month": m.month,
                    "credits": m.total_credits,
                    "debits": m.total_debits,
                    "net": m.net_flow,
                    "count": m.transaction_count,
                }
                for m in self.monthly_summaries
            ],
            "weekly_credits": self.weekly_credits,
            "weekly_debits": self.weekly_debits,
            "recurring": {"total": self.recurring_total, "count": self.recurring_count},
            "one_time": {"total": self.one_time_total, "count": self.one_time_count},
            "totals": {
                "credits": self.total_credits,
                "debits": self.total_debits,
                "opening": self.opening_balance,
                "closing": self.closing_balance,
            },
        }

    @classmethod
    def from_shared(cls, shared: SharedAggregationResult) -> "UnionAggregationResult":
        return cls(
            debit_categories=list(shared.debit_categories),
            credit_categories=list(shared.credit_categories),
            monthly_summaries=list(shared.monthly_summaries),
            weekly_credits=dict(shared.weekly_credits),
            weekly_debits=dict(shared.weekly_debits),
            recurring_total=shared.recurring_total,
            one_time_total=shared.one_time_total,
            recurring_count=shared.recurring_count,
            one_time_count=shared.one_time_count,
            top_debit_merchants=list(shared.top_debit_merchants),
            top_credit_merchants=list(shared.top_credit_merchants),
            total_credits=shared.total_credits,
            total_debits=shared.total_debits,
            opening_balance=shared.opening_balance,
            closing_balance=shared.closing_balance,
        )


class UnionAggregationEngine:
    """Phase 4: delegates to SharedAggregationEngine."""

    TOP_MERCHANTS_LIMIT = 10

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._engine = SharedAggregationEngine()

    def aggregate(
        self,
        transactions: List[Dict[str, Any]],
        opening_balance: float = 0,
        closing_balance: float = 0,
    ) -> UnionAggregationResult:
        shared = self._engine.aggregate(
            transactions,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
        )
        return UnionAggregationResult.from_shared(shared)
