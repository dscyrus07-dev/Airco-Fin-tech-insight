"""
Shared pipeline package (normalized schema + future shared steps).

Phase 1: models + to_normalized only.
Phases 2–6: reporting, classification, reconciliation, orchestrator.
"""

from .models import (
    NormalizedTransaction,
    PipelineResult,
    StatementMetadata,
)
from .normalize import to_normalized, transactions_to_dicts

# Reporting re-exports (Phase 2a / 5)
from .reporting import (  # noqa: F401
    LiteExcelGenerator,
    SHEET_ORDER,
    build_lite_report_model,
    generate_lite_excel,
    FormulaExcelEngine,
    FormulaExcelEngineBase,
)

# Reconciliation re-exports (Phase 3)
from .reconciliation import (  # noqa: F401
    ReconciliationMismatch,
    SharedReconciliationResult,
    auto_correct_debit_credit,
    compute_reconciliation,
)

# Aggregation / recurring re-exports (Phase 4)
from .aggregation import (  # noqa: F401
    SharedAggregationEngine,
    SharedAggregationResult,
)
from .recurring import SharedRecurringEngine  # noqa: F401

__all__ = [
    "NormalizedTransaction",
    "StatementMetadata",
    "PipelineResult",
    "to_normalized",
    "transactions_to_dicts",
    "LiteExcelGenerator",
    "SHEET_ORDER",
    "build_lite_report_model",
    "generate_lite_excel",
    "FormulaExcelEngine",
    "FormulaExcelEngineBase",
    "ReconciliationMismatch",
    "SharedReconciliationResult",
    "auto_correct_debit_credit",
    "compute_reconciliation",
    "SharedAggregationEngine",
    "SharedAggregationResult",
    "SharedRecurringEngine",
]
