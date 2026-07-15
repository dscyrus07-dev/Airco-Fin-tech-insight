"""
Airco Insights - Unknown Bank Recurring Engine
"""

import logging
from collections import Counter
from typing import Dict, List

from .._shared.generic_bank import GenericRecurringEngine

logger = logging.getLogger(__name__)


class UnknownRecurringEngine(GenericRecurringEngine):
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def detect(self, transactions: List[Dict]) -> List[Dict]:
        """
        Detect recurring transactions.
        Recurring = same description (case-insensitive) AND same amount appears >= 3 times.
        """
        transactions = transactions.copy()
        desc_norm = [str(t.get("description", "")).lower().strip() for t in transactions]

        def make_key(idx):
            amt = transactions[idx].get("debit") or transactions[idx].get("credit") or 0
            # 5% tolerance band
            band = round(amt / max(amt * 0.05, 1)) if amt > 0 else 0
            return (desc_norm[idx], band)

        keys = [make_key(i) for i in range(len(transactions))]
        key_counts = Counter(keys)
        
        for i, txn in enumerate(transactions):
            txn["is_recurring"] = key_counts[keys[i]] >= 3
            txn["recurring"] = "Yes" if txn["is_recurring"] else "No"

        return transactions
