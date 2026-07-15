"""
Airco Insights — ICICI Bank AI Fallback
========================================
AI classification stub for unresolved ICICI Bank transactions.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from ...intelligence import ClaudeIntelligenceLayer, GroqIntelligenceLayer, LearningStore

from .._shared.category_registry import get_allowed_categories, normalize_category

logger = logging.getLogger(__name__)

ALLOWED_CATEGORIES = get_allowed_categories()


@dataclass
class AIClassificationResult:
    classified_count: int
    total_sent: int
    api_calls: int
    estimated_cost_usd: float
    estimated_cost_inr: float


class ICICIAIFallback:
    """AI fallback stub for ICICI Bank transactions."""

    def __init__(self, api_key: Optional[str] = None):
        from ...intelligence import ClaudeIntelligenceLayer, GroqIntelligenceLayer, LearningStore

        self.api_key = api_key
        self.logger  = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.learning_store = LearningStore()
        intelligence_cls = ClaudeIntelligenceLayer if api_key and api_key.startswith("sk-ant-") else GroqIntelligenceLayer
        self.intelligence = intelligence_cls(
            api_key=api_key,
            bank_name="ICICI",
            learning_store=self.learning_store,
        )

    def classify_unclassified(
        self,
        transactions: List[Dict[str, Any]],
        bank_name: str = "ICICI",
        account_type: str = "Salaried",
    ) -> List[Dict[str, Any]]:
        classified, _ = self.classify(transactions, bank_name=bank_name, account_type=account_type)
        return classified

    def classify(
        self,
        transactions: List[Dict[str, Any]],
        bank_name: str = "ICICI",
        account_type: str = "Salaried",
    ) -> Tuple[List[Dict[str, Any]], AIClassificationResult]:
        result, stats = self.intelligence.classify(
            transactions=transactions,
            bank_name=bank_name,
            account_type=account_type,
            allowed_categories=set(ALLOWED_CATEGORIES),
        )
        return result, AIClassificationResult(
            classified_count=stats.classified_count,
            total_sent=stats.total_sent,
            api_calls=stats.api_calls,
            estimated_cost_usd=stats.estimated_cost_usd,
            estimated_cost_inr=stats.estimated_cost_inr,
        )
