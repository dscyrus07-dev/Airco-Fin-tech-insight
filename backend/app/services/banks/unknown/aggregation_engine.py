"""
Airco Insights - Unknown Bank Aggregation Engine
"""

import logging
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

from .._shared.generic_bank import GenericAggregationEngine

logger = logging.getLogger(__name__)


class UnknownAggregationEngine(GenericAggregationEngine):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def aggregate(
        self,
        transactions: List[Dict],
        opening: Optional[float] = None,
        closing: Optional[float] = None,
    ) -> Dict:
        """
        Compute monthly summaries, category breakdowns, and total counts.
        """
        monthly: Dict[str, Dict] = defaultdict(lambda: {"credit": 0.0, "debit": 0.0, "count": 0})
        category: Dict[str, Dict] = defaultdict(lambda: {"credit": 0.0, "debit": 0.0, "count": 0})

        total_credits = 0.0
        total_debits = 0.0
        total_count = len(transactions)

        for txn in transactions:
            date_str = txn.get("date", "")
            try:
                if isinstance(date_str, str):
                    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
                        try:
                            dt = datetime.strptime(date_str, fmt)
                            month_key = dt.strftime("%b-%Y")
                            break
                        except ValueError:
                            continue
                else:
                    month_key = "Unknown"
            except Exception:
                month_key = "Unknown"

            credit = txn.get("credit") or 0
            debit = txn.get("debit") or 0
            cat = txn.get("category") or "Others"

            monthly[month_key]["credit"] += credit
            monthly[month_key]["debit"] += debit
            monthly[month_key]["count"] += 1

            category[cat]["credit"] += credit
            category[cat]["debit"] += debit
            category[cat]["count"] += 1

            total_credits += credit
            total_debits += debit

        return {
            "monthly": dict(monthly),
            "category": dict(category),
            "total_credits": total_credits,
            "total_debits": total_debits,
            "total_count": total_count,
            "opening_balance": opening,
            "closing_balance": closing,
        }
