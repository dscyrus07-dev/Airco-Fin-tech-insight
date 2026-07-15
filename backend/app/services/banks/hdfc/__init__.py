"""
Airco Insights — HDFC Bank Processor Module
============================================
Complete, self-contained HDFC bank statement processor.
100% accuracy-first design with strict validation at every step.

Processing Pipeline:
1. Structure Validation → Validate PDF structure is HDFC format
2. Parser → Extract raw transactions with 100% row capture
3. Transaction Validation → Validate all required fields present
4. Balance Reconciliation → Verify opening + credits - debits = closing
5. Rule Engine → Deterministic HDFC-specific classification
6. AI Fallback → Claude API for unresolved cases only
7. Recurring Engine → Detect recurring patterns
8. Aggregation Engine → Financial analytics
9. Excel Generator → Formatted report generation

Design Principles:
- NO output until 100% validated
- Transaction count must match statement summary
- Balance must reconcile to the last paisa
- No missing fields allowed
- AI is LAST RESORT, not primary
"""

from .processor import HDFCProcessor
from .structure_validator import HDFCStructureValidator, HDFCStructureError
from .parser import HDFCParser, HDFCParseError
from .transaction_validator import HDFCTransactionValidator, HDFCValidationError
from .reconciliation import HDFCReconciliation, HDFCReconciliationError
from .rule_engine import HDFCRuleEngine
from .ai_fallback import HDFCAIFallback
from .recurring_engine import HDFCRecurringEngine
from .aggregation_engine import HDFCAggregationEngine

__all__ = [
    "HDFCProcessor",
    "HDFCStructureValidator",
    "HDFCStructureError",
    "HDFCParser",
    "HDFCParseError",
    "HDFCTransactionValidator",
    "HDFCValidationError",
    "HDFCReconciliation",
    "HDFCReconciliationError",
    "HDFCRuleEngine",
    "HDFCAIFallback",
    "HDFCRecurringEngine",
    "HDFCAggregationEngine",
]
