"""
Airco Insights — Kotak Bank Processor Module
=============================================
Complete, self-contained Kotak Mahindra Bank statement processor.
"""

from .processor import KotakProcessor, KotakProcessorError
from .structure_validator import KotakStructureValidator, KotakStructureError
from .parser import KotakParser, KotakParseError
from .transaction_validator import KotakTransactionValidator, KotakValidationError
from .reconciliation import KotakReconciliation, KotakReconciliationError
from .rule_engine import KotakRuleEngine
from .ai_fallback import KotakAIFallback
from .recurring_engine import KotakRecurringEngine
from .aggregation_engine import KotakAggregationEngine
from .kotak_classifier import KotakClassifier

__all__ = [
    "KotakProcessor", "KotakProcessorError",
    "KotakStructureValidator", "KotakStructureError",
    "KotakParser", "KotakParseError",
    "KotakTransactionValidator", "KotakValidationError",
    "KotakReconciliation", "KotakReconciliationError",
    "KotakRuleEngine", "KotakAIFallback",
    "KotakRecurringEngine", "KotakAggregationEngine",
    "KotakExcelGenerator", "KotakClassifier",
]
