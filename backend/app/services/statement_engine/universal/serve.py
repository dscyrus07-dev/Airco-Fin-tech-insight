"""T3 universal-reader serving: flag-gated helpers used by the pipeline
orchestrator. STATEMENT_ENGINE_UNIVERSAL_MODE=off|shadow|serve (default off).

off    — nothing runs; behaviour identical to baseline.
shadow — when no other tier produced a result, run T3 and record the block only.
serve  — when T1 (v2) and T2 (legacy) cannot produce a result, serve T3 output:
         REVIEW rows go through the same downstream steps (reconcile, classify,
         Excel + Statement Check, history); FAILED means the job still fails,
         honestly, with the T3 code. T3 output is never VERIFIED.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..serve import V2RowSource
from . import reader as _reader
from .reader import UniversalResult

ENV = "STATEMENT_ENGINE_UNIVERSAL_MODE"
_MODES = ("off", "shadow", "serve")


def mode() -> str:
    m = (os.environ.get(ENV) or "off").strip().lower()
    return m if m in _MODES else "off"


def attempt(pdf_path: str, bank_hint: str = "Unknown bank", isolated: bool = True):
    """Run the T3 reader under the isolation guard (hard timeout + memory
    ceiling in a child process). Returns (UniversalResult, V2RowSource|None).
    Never raises. isolated=False runs in-process (tests/debug only)."""
    if not isolated:
        try:
            res = _reader.read(pdf_path, bank_hint=bank_hint or "Unknown bank")
            return res, row_source_from_outcome(res)
        except Exception as exc:                                    # defence in depth
            return (UniversalResult(verdict="FAILED", code="CRASH",
                                    detail=type(exc).__name__, bank_hint=bank_hint), None)
    try:
        from .isolated import run_isolated
        return run_isolated(pdf_path, bank_hint=bank_hint or "Unknown bank")
    except Exception as exc:
        return (UniversalResult(verdict="FAILED", code="CRASH",
                                detail=type(exc).__name__, bank_hint=bank_hint), None)


def row_source_from_outcome(res: UniversalResult) -> Optional[V2RowSource]:
    """UniversalResult -> V2RowSource for _run_pipeline's engine hook; None when
    there is no served row data (FAILED/T0 carry none)."""
    if not res.ok or res.outcome is None or not res.outcome.rows:
        return None
    out = res.outcome
    txns = [t.txn.to_dict() for t in out.rows]
    s = out.summary
    return V2RowSource(
        transactions=txns,
        opening_balance=s.opening if s else None,
        closing_balance=s.closing if s else None,
        total_debits=s.debits if s else None,
        total_credits=s.credits if s else None,
        dr_count=getattr(s, "dr_count", None) if s else None,
        cr_count=getattr(s, "cr_count", None) if s else None,
        statement_from=out.period[0] if out.period else None,
        statement_to=out.period[1] if out.period else None,
        account_number=out.account_number or None,
        ifsc=out.ifsc or None,
    )


def block_for(res: UniversalResult, *, served: bool, u_mode: str) -> Dict[str, Any]:
    """Additive 'universal' sub-block inside statement_engine (contract, U5)."""
    return {
        "tier": "T3",
        "engine": "universal",
        "mode": u_mode,
        "served": served,
        "verdict": res.verdict,                       # REVIEW | FAILED | T0 code
        "code": res.code,                             # GENERAL_READER or failure code
        "detail": res.detail[:200] if res.detail else "",
        "needs_review": res.ok,
        "review_codes": [_reader.GENERAL_READER] if res.ok else ([res.code] if res.code else []),
        "anchored": False,                            # T3 never claims independent verification
        "bank_hint": res.bank_hint,
        "rows": res.meta.get("rows", 0),
        "elapsed_ms": round(res.elapsed_s * 1000, 1),
        "pre_cap_verdict": res.meta.get("checks_verdict"),
        "infer": {k: res.meta.get(k) for k in
                  ("header", "money", "date_shape", "amount_form", "confidence", "margin",
                   "rows_sample", "chain_frac")
                  if res.meta.get(k) is not None},
    }


def engine_block_for(res: UniversalResult, u_mode: str,
                     detected_bank: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Top-level statement_engine block when T3 served the result."""
    return {
        "engine": "universal",
        "mode": u_mode,
        "layout_id": "universal_auto",
        "verdict": "REVIEW",
        "needs_review": True,
        "review_codes": [_reader.GENERAL_READER],
        "anchored": False,
        "detected_bank": detected_bank,
        "advisory": None,
        "universal": block_for(res, served=True, u_mode=u_mode),
    }


def audit_attempt(audit_service, job_id: Optional[str], block: Dict[str, Any]) -> None:
    """Structured job event per tier (U6c): no content, verdict + codes + timing only."""
    if not audit_service or not job_id:
        return
    try:
        audit_service.create_job_event(
            job_id,
            event_type="t3_universal_decision",
            event_name="t3_universal_decision",
            event_category="universal",
            metadata=dict(block),
        )
    except Exception:
        pass
