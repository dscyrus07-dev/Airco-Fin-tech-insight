"""Load a captured old_result.json (scripts/capture_old_output.py) as an ExtractionResult.

The normalized block was produced at a documented boundary (to_normalized on RAW parser rows,
no repair, no classification). A future V2 extractor must emit the same boundary.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.services.pipeline.models import NormalizedTransaction, StatementMetadata

from .contract import ContractError, ExtractionResult

SUPPORTED_SCHEMA = "airco.old_result/1"


def _dec(x: Any) -> Optional[Decimal]:
    return None if x in (None, "") else Decimal(str(x))


def load_extraction_result(source: Union[str, Path, Dict[str, Any]]) -> ExtractionResult:
    doc = source if isinstance(source, dict) else json.loads(Path(source).read_text(encoding="utf-8"))
    if doc.get("schema") != SUPPORTED_SCHEMA:
        raise ContractError(f"unsupported old_result schema: {doc.get('schema')!r}")
    if doc.get("stage") != "RAW":
        raise ContractError(f"old_result stage must be RAW, got {doc.get('stage')!r}")
    status = doc.get("status")
    if status != "OK":
        err = doc.get("error") or {}
        from app.services.pipeline.models import StatementMetadata as _M
        return ExtractionResult(
            engine="old", metadata=_M(bank_name="", bank_key=doc.get("bank_key", "")), transactions=[],
            failure=f"{status}: {err.get('code')}: {err.get('message')}",
        )
    norm = doc["normalized"]
    nm = norm["metadata"]
    meta = StatementMetadata(
        bank_name=nm.get("bank_name", ""), bank_key=nm.get("bank_key", ""),
        account_number=nm.get("account_number", ""), account_holder=nm.get("account_holder", ""),
        account_type=nm.get("account_type", ""),
        opening_balance=_dec(nm.get("opening_balance")) or Decimal("0"),
        closing_balance=_dec(nm.get("closing_balance")) or Decimal("0"),
        statement_from=nm.get("statement_from", ""), statement_to=nm.get("statement_to", ""),
    )
    txns: List[NormalizedTransaction] = [
        NormalizedTransaction(
            date=t["date"], description=t["description"], debit=_dec(t.get("debit")) or None,
            credit=_dec(t.get("credit")) or None, balance=_dec(t.get("balance")) or Decimal("0"),
            ref_no=t.get("ref_no") or "", value_date=t.get("value_date"),
        )
        for t in norm["transactions"]
    ]
    printed = doc.get("printed") or {}
    warnings: List[str] = []
    derived = doc.get("derived") or {}
    if derived.get("closing_from_last_row") and nm.get("closing_balance") is not None:
        if _dec(nm["closing_balance"]) != _dec(derived["closing_from_last_row"]):
            warnings.append("old metadata closing_balance != last row balance (metadata unreliable as a reference)")
    if (derived.get("balance_chain_breaks") or 0) > 0:
        warnings.append(f"old rows have {derived['balance_chain_breaks']} balance-chain breaks")
    return ExtractionResult(
        engine="old", metadata=meta, transactions=txns,
        printed_total_debit=_dec(printed.get("total_debits")), printed_total_credit=_dec(printed.get("total_credits")),
        verification_status=(doc.get("verification") or {}).get("state"), warnings=warnings,
    )
