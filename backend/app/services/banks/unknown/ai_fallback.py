"""
Airco Insights - Unknown Bank AI Fallback
"""

import logging
from typing import Dict, List, Optional

from .._shared.generic_bank import GenericAIFallback, GenericBankConfig

CONFIG = GenericBankConfig(
    bank_key="unknown",
    bank_name="Unknown",
    file_prefix="unknown",
    markers=[],
    support_aliases=["unknown", "unknown bank"],
)

logger = logging.getLogger(__name__)


class UnknownAIFallback(GenericAIFallback):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(CONFIG, api_key=api_key)
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def classify(self, transactions: List[Dict], bank_name: str, account_type: str) -> List[Dict]:
        if not self.api_key:
            logger.warning("No API key provided for AI fallback, returning transactions unchanged")
            return transactions

        try:
            return super().classify(transactions, bank_name, account_type)
        except Exception as e:
            self.logger.error(f"AI fallback classification failed: {e}")
            return transactions
