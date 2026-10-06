"""Old-vs-new extraction comparison (migration support). Pure; no I/O beyond the extractors given."""

from .comparator import (  # noqa: F401
    ComparatorConfig,
    ComparisonResult,
    Diff,
    Finding,
    ParityReport,
    compare_results,
    run_parity,
)
from .contract import (  # noqa: F401
    ContractError,
    CorpusItem,
    ExtractionResult,
    StatementExtractor,
)
