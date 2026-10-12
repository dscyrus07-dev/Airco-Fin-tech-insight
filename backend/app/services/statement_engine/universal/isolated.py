"""Run the T3 reader in a child process: a hard wall-clock timeout plus a memory
ceiling, so one pathological PDF can never stall or OOM the API worker. The
parent kills the child on timeout and reports FAILED/TIME_BUDGET. On POSIX the
child sets an address-space rlimit; on Windows the ceiling is skipped (page cap
+ read budget still apply). Rows come back as an already-serialised
V2RowSource-shaped dict — enough for the serve path, which never needs the live
outcome objects."""
from __future__ import annotations

import multiprocessing as _mp
import os
import queue as _queue
from typing import Any, Dict, Optional, Tuple

from ..serve import V2RowSource
from .reader import UniversalResult
from . import serve as _serve

_ISOLATE_TIMEOUT_S = float(os.environ.get("STATEMENT_ENGINE_UNIVERSAL_TIMEOUT", "45"))
_MEM_LIMIT_BYTES = int(os.environ.get("STATEMENT_ENGINE_UNIVERSAL_MEM_MB", "1536")) * 1024 * 1024
_META_KEYS = ("checks_verdict", "header", "money", "date_shape", "amount_form",
              "confidence", "margin", "rows_sample", "chain_frac", "rows")


def _child(pdf_path: str, bank_hint: str, q) -> None:
    try:
        import resource  # POSIX only
        resource.setrlimit(resource.RLIMIT_AS, (_MEM_LIMIT_BYTES, _MEM_LIMIT_BYTES))
    except Exception:
        pass
    try:
        from .reader import read
        res = read(pdf_path, bank_hint=bank_hint)
        rs = _serve.row_source_from_outcome(res)
        q.put({"verdict": res.verdict, "code": res.code, "detail": res.detail,
               "elapsed": res.elapsed_s,
               "meta": {k: res.meta.get(k) for k in _META_KEYS if res.meta.get(k) is not None},
               "row_source": {
                   "transactions": rs.transactions,
                   "opening_balance": str(rs.opening_balance) if rs.opening_balance is not None else None,
                   "closing_balance": str(rs.closing_balance) if rs.closing_balance is not None else None,
                   "total_debits": str(rs.total_debits) if rs.total_debits is not None else None,
                   "total_credits": str(rs.total_credits) if rs.total_credits is not None else None,
                   "dr_count": rs.dr_count, "cr_count": rs.cr_count,
                   "statement_from": rs.statement_from, "statement_to": rs.statement_to,
                   "account_number": rs.account_number, "ifsc": rs.ifsc,
               } if rs else None})
    except BaseException as exc:
        q.put({"verdict": "FAILED", "code": "CRASH", "detail": type(exc).__name__})


def _rs_from(payload: Optional[Dict[str, Any]]) -> Optional[V2RowSource]:
    if not payload:
        return None
    from decimal import Decimal, InvalidOperation

    def _dec(v):
        try:
            return None if v in (None, "") else Decimal(str(v))
        except (InvalidOperation, ValueError):
            return None
    return V2RowSource(transactions=payload.get("transactions") or [],
                       opening_balance=_dec(payload.get("opening_balance")),
                       closing_balance=_dec(payload.get("closing_balance")),
                       total_debits=_dec(payload.get("total_debits")),
                       total_credits=_dec(payload.get("total_credits")),
                       dr_count=payload.get("dr_count"), cr_count=payload.get("cr_count"),
                       statement_from=payload.get("statement_from"),
                       statement_to=payload.get("statement_to"),
                       account_number=payload.get("account_number"), ifsc=payload.get("ifsc"))


def run_isolated(pdf_path: str, bank_hint: str = "Unknown bank",
                 timeout_s: float = _ISOLATE_TIMEOUT_S) -> Tuple[UniversalResult, Optional[V2RowSource]]:
    """(result, row_source). result.ok is True only for REVIEW, and row_source is
    non-None exactly then — FAILED/T0 results carry no row data."""
    ctx = _mp.get_context("spawn")
    q = ctx.Queue()
    p = ctx.Process(target=_child, args=(pdf_path, bank_hint, q), daemon=True)
    p.start()
    try:
        payload = q.get(timeout=timeout_s)
    except (_queue.Empty, EOFError):
        payload = None
    finally:
        if p.is_alive():
            p.terminate()
        p.join(timeout=5)
    if payload is None:
        return (UniversalResult(verdict="FAILED", code="TIME_BUDGET",
                                detail=f"isolated read exceeded {timeout_s}s or the worker died",
                                bank_hint=bank_hint, elapsed_s=timeout_s), None)
    res = UniversalResult(verdict=payload["verdict"], code=payload.get("code", ""),
                          detail=payload.get("detail", ""), bank_hint=bank_hint,
                          elapsed_s=payload.get("elapsed", 0.0))
    res.meta.update(payload.get("meta") or {})
    if res.ok:
        res.meta.setdefault("rows", len((payload.get("row_source") or {}).get("transactions") or []))
    return res, _rs_from(payload.get("row_source"))
