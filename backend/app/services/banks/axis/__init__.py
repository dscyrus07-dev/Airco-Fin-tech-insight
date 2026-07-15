"""
Airco Insights — Axis Bank Processor Module
============================================
Complete, self-contained Axis Bank statement processor.
100% accuracy-first design with strict validation at every step.

Processing Pipeline:
1. Structure Validation → Validate PDF structure is Axis Bank format
2. Parser              → Extract raw transactions with 100% row capture
3. Transaction Validation → Validate all required fields
4. Balance Reconciliation → Verify opening + credits - debits = closing
5. Rule Engine         → Deterministic Axis-specific classification
6. AI Fallback         → Stub (disabled by default)
7. Recurring Engine    → Detect recurring patterns
8. Aggregation Engine  → Financial analytics
9. Report Generator    → 5-sheet Excel report
"""

from .processor import AxisProcessor, AxisProcessorError
from .structure_validator import AxisStructureValidator, AxisStructureError
from .parser import AxisParser, AxisParseError
from .transaction_validator import AxisTransactionValidator, AxisValidationError
from .reconciliation import AxisReconciliation, AxisReconciliationError
from .rule_engine import AxisRuleEngine
from .ai_fallback import AxisAIFallback
from .recurring_engine import AxisRecurringEngine
from .aggregation_engine import AxisAggregationEngine
from .axis_classifier import AxisClassifier

__all__ = [
    "AxisProcessor",
    "AxisProcessorError",
    "AxisStructureValidator",
    "AxisStructureError",
    "AxisParser",
    "AxisParseError",
    "AxisTransactionValidator",
    "AxisValidationError",
    "AxisReconciliation",
    "AxisReconciliationError",
    "AxisRuleEngine",
    "AxisAIFallback",
    "AxisRecurringEngine",
    "AxisAggregationEngine",
    "AxisClassifier",
]
