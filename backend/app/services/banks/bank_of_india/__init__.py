"""Airco Insights — Bank of India Processor Module"""

from .processor import BankOfIndiaProcessor, BankOfIndiaProcessorError, BankOfIndiaProcessingResult
from .structure_validator import BankOfIndiaStructureValidator, BankOfIndiaStructureError
from .parser import BankOfIndiaParser, BankOfIndiaParseError
from .transaction_validator import BankOfIndiaTransactionValidator, BankOfIndiaValidationError
from .reconciliation import BankOfIndiaReconciliation, BankOfIndiaReconciliationError
from .rule_engine import BankOfIndiaRuleEngine
from .ai_fallback import BankOfIndiaAIFallback
from .recurring_engine import BankOfIndiaRecurringEngine
from .aggregation_engine import BankOfIndiaAggregationEngine
from .bank_of_india_classifier import BankOfIndiaClassifier

__all__ = [
    "BankOfIndiaProcessor",
    "BankOfIndiaProcessorError",
    "BankOfIndiaProcessingResult",
    "BankOfIndiaStructureValidator",
    "BankOfIndiaStructureError",
    "BankOfIndiaParser",
    "BankOfIndiaParseError",
    "BankOfIndiaTransactionValidator",
    "BankOfIndiaValidationError",
    "BankOfIndiaReconciliation",
    "BankOfIndiaReconciliationError",
    "BankOfIndiaRuleEngine",
    "BankOfIndiaAIFallback",
    "BankOfIndiaRecurringEngine",
    "BankOfIndiaAggregationEngine",
    "BankOfIndiaExcelGenerator",
    "BankOfIndiaFormulaExcelEngine",
    "BankOfIndiaClassifier",
    "get_classifier",
    "classify",
    "generate_report",
]
