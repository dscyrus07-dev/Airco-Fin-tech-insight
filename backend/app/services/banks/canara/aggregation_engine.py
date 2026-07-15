"""Phase 4: Canara aggregation wraps shared pipeline.aggregation."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.pipeline.aggregation.engine import (
    CategorySummary,
    MonthlySummary,
    SharedAggregationEngine,
    SharedAggregationResult,
)

logger = logging.getLogger(__name__)


@dataclass
class AggregationResult:
    opening_balance: float
    closing_balance: float
    total_credits: float
    total_debits: float
    credit_count: int
    debit_count: int
    monthly_summary: Dict[str, Dict]
    debit_categories: List[CategorySummary] = field(default_factory=list)
    credit_categories: List[CategorySummary] = field(default_factory=list)
    monthly_summaries: List[MonthlySummary] = field(default_factory=list)
    weekly_credits: Dict[str, float] = field(default_factory=dict)
    weekly_debits: Dict[str, float] = field(default_factory=dict)
    recurring_total: float = 0.0
    one_time_total: float = 0.0
    recurring_count: int = 0
    one_time_count: int = 0
    top_debit_merchants: List[Dict[str, Any]] = field(default_factory=list)
    top_credit_merchants: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "opening_balance": self.opening_balance,
            "closing_balance": self.closing_balance,
            "total_credits": self.total_credits,
            "total_debits": self.total_debits,
            "credit_count": self.credit_count,
            "debit_count": self.debit_count,
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
        }


class CanaraAggregationEngine:
    TOP_MERCHANTS_LIMIT = 10

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._engine = SharedAggregationEngine()

    def aggregate(
        self,
        transactions: List[Dict[str, Any]],
        opening: Optional[float] = None,
        closing: Optional[float] = None,
    ) -> AggregationResult:
        if not transactions:
            return AggregationResult(
                opening_balance=opening or 0,
                closing_balance=closing or 0,
                total_credits=0,
                total_debits=0,
                credit_count=0,
                debit_count=0,
                monthly_summary={},
            )
        open_bal = opening
        close_bal = closing if closing is not None else (transactions[-1].get("balance") or 0)
        shared = self._engine.aggregate(
            transactions,
            opening_balance=open_bal,
            closing_balance=close_bal,
        )
        credit_count = sum(1 for t in transactions if (t.get("credit") or 0) > 0)
        debit_count = sum(1 for t in transactions if (t.get("debit") or 0) > 0)
        monthly_summary = {
            m.month: {
                "credits": m.total_credits,
                "debits": m.total_debits,
                "credit_count": m.credit_count,
                "debit_count": m.debit_count,
            }
            for m in shared.monthly_summaries
        }
        return AggregationResult(
            opening_balance=shared.opening_balance,
            closing_balance=shared.closing_balance,
            total_credits=shared.total_credits,
            total_debits=shared.total_debits,
            credit_count=credit_count,
            debit_count=debit_count,
            monthly_summary=monthly_summary,
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
        )
