"""
Airco Insights — ICICI Bank Processor Module
=============================================
Complete, self-contained ICICI Bank statement processor.
"""

from .processor import ICICIProcessor, ICICIProcessorError
from .structure_validator import ICICIStructureValidator, ICICIStructureError
from .parser import ICICIParser, ICICIParseError
from .transaction_validator import ICICITransactionValidator, ICICIValidationError
from .reconciliation import ICICIReconciliation, ICICIReconciliationError
from .rule_engine import ICICIRuleEngine
from .ai_fallback import ICICIAIFallback
from .recurring_engine import ICICIRecurringEngine
from .aggregation_engine import ICICIAggregationEngine
from .icici_classifier import ICICIClassifier

__all__ = [
    "ICICIProcessor", "ICICIProcessorError",
    "ICICIStructureValidator", "ICICIStructureError",
    "ICICIParser", "ICICIParseError",
    "ICICITransactionValidator", "ICICIValidationError",
    "ICICIReconciliation", "ICICIReconciliationError",
    "ICICIRuleEngine", "ICICIAIFallback",
    "ICICIRecurringEngine", "ICICIAggregationEngine",
    "ICICIExcelGenerator", "ICICIClassifier",
]
