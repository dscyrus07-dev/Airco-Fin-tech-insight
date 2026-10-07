"""Extractor contract for the old-vs-new migration comparator.

Reuses the EXISTING canonical models (pipeline.models.NormalizedTransaction and
StatementMetadata). No new transaction schema is introduced.

Verification boundary: an ExtractionResult is always the RAW parser output, i.e.
BEFORE balance repair / classification. Verification observes this stage; the
comparator refuses anything else so a repair step can never hide an extraction
difference.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Protocol, Sequence, runtime_checkable

from app.services.pipeline.models import NormalizedTransaction, StatementMetadata

RAW_STAGE = "RAW"


class ContractError(ValueError):
    """The extractor returned something that breaks the migration contract."""


@dataclass
class ExtractionResult:
    engine: str                                   # "old" | "v2" (free label)
    metadata: StatementMetadata
    transactions: List[NormalizedTransaction]
    stage: str = RAW_STAGE                        # must stay RAW (pre-repair)
    printed_total_debit: Optional[Decimal] = None   # totals printed on the statement, if the extractor read them
    printed_total_credit: Optional[Decimal] = None
    printed_totals_reconciled: Optional[bool] = None  # extractor's own verdict: printed totals reconcile (incl. via reversal rule)
    verification_status: Optional[str] = None     # e.g. VERIFIED / REVIEW / FAILED from the verification engine
    failure: Optional[str] = None                 # set when extraction failed; transactions should then be empty
    warnings: List[str] = field(default_factory=list)

    def validate(self) -> None:
        if self.stage != RAW_STAGE:
            raise ContractError(
                f"{self.engine}: extraction stage must be {RAW_STAGE} (pre-repair), got {self.stage!r}"
            )
        if self.failure and self.transactions:
            raise ContractError(f"{self.engine}: a failed extraction must not return transactions")


@runtime_checkable
class StatementExtractor(Protocol):
    """What a V2 (or adapted old) extractor must implement.

    - Must return RAW rows (before repair_transaction_sides / classification).
    - Must not raise for ordinary parse failures: set `failure` instead (raising is
      tolerated and recorded as PARSER_FAILURE).
    - `password` is used in memory only, never logged or stored.
    """

    name: str

    def extract(self, pdf_path: str, password: Optional[str] = None) -> ExtractionResult: ...


@dataclass
class CorpusItem:
    """One statement in the comparison corpus."""

    item_id: str
    pdf_path: str
    bank_key: str
    password: Optional[str] = None


Corpus = Sequence[CorpusItem]
