"""Airco Insights — IDFC Bank Processor Module"""

from .processor import IDFCProcessor, IDFCProcessorError, IDFCProcessingResult
from .structure_validator import IDFCStructureValidator, IDFCStructureError
from .parser import IDFCParser, IDFCParseError
from .transaction_validator import IDFCTransactionValidator, IDFCValidationError
from .reconciliation import IDFCReconciliation, IDFCReconciliationError
from .rule_engine import IDFCRuleEngine
from .ai_fallback import IDFCAIFallback
from .recurring_engine import IDFCRecurringEngine
from .aggregation_engine import IDFCAggregationEngine
from .idfc_classifier import IDFCClassifier

__all__ = ["IDFCProcessor", "IDFCProcessorError", "IDFCProcessingResult", "IDFCStructureValidator", "IDFCStructureError", "IDFCParser", "IDFCParseError", "IDFCTransactionValidator", "IDFCValidationError", "IDFCReconciliation", "IDFCReconciliationError", "IDFCRuleEngine", "IDFCAIFallback", "IDFCRecurringEngine", "IDFCAggregationEngine", "IDFCExcelGenerator", "IDFCFormulaExcelEngine", "IDFCClassifier"]
