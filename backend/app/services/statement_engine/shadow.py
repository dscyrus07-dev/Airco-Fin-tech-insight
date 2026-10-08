"""Shadow wiring for the v2 statement engine: run the v2 router next to the legacy
pipeline and record a small comparison, without ever serving v2 output.

STATEMENT_ENGINE_V2_MODE:
    off     default; no v2 work is done, the pipeline behaves exactly as before.
    shadow  after the legacy parser finishes, route_pdf runs under a hard timeout and a
            PII-free comparison record is persisted via the caller's sink (audit job
            event, which lives under the existing 7-day retention) or the module log.
            The legacy response, status code and error paths are never touched.
    serve   not enabled; selecting it raises immediately so it can never be half-on.
"""
from __future__ import annotations

import hashlib
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from decimal import Decimal
from typing import Any, Callable, Dict, Optional

log = logging.getLogger(__name__)

MODE_ENV = "STATEMENT_ENGINE_V2_MODE"
SHADOW_TIMEOUT_S = 60.0
_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="v2-shadow")

ShadowSink = Callable[[Dict[str, Any]], None]


def v2_mode() -> str:
    """Current v2 mode: "off" | "shadow". "serve" raises — it is not enabled."""
    mode = (os.getenv(MODE_ENV) or "off").strip().lower()
    if mode == "serve":
        raise RuntimeError(f"{MODE_ENV}=serve is not enabled: v2 results must never be served")
    if mode not in ("off", "shadow"):
        log.warning("%s=%r is not a valid mode; treating as off", MODE_ENV, mode)
        return "off"
    return mode


def _sha8(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:8]


def _log_sink(record: Dict[str, Any]) -> None:
    log.info("v2_shadow %s", json_safe(record))


def json_safe(record: Dict[str, Any]) -> Dict[str, Any]:
    return {k: (str(v) if isinstance(v, Decimal) else v) for k, v in record.items()}


def _v2_route(pdf_path: str):
    """route_pdf under production defaults (detector on, header-only off)."""
    from .extractors.registry import DEFAULT_REGISTRY
    from .v2_router import route_pdf
    return route_pdf(pdf_path, DEFAULT_REGISTRY)


def _legacy_extraction(bank_key: str, result: Any):
    """The pipeline's output as an ExtractionResult for the migration comparator."""
    from app.services.migration.contract import ExtractionResult
    from app.services.pipeline.models import NormalizedTransaction, StatementMetadata

    vf = getattr(result, "verification", None) or {}
    checks = vf.get("checks") or {}
    if isinstance(checks, dict):
        oc = (checks.get("opening_closing_check") or {}).get("detail") or {}
    else:
        oc = next(
            (c.get("detail") or {} for c in checks
             if isinstance(c, dict) and c.get("name") == "opening_closing_check"),
            {},
        )

    def _dec(v):
        return None if v in (None, "") else Decimal(str(v).replace(",", ""))

    meta = StatementMetadata(
        bank_name="", bank_key=bank_key,
        opening_balance=_dec(oc.get("opening")) or Decimal("0"),
        closing_balance=_dec(oc.get("closing")) or Decimal("0"),
        extras={"legacy_opening_known": oc.get("opening") is not None,
                "legacy_closing_known": oc.get("closing") is not None},
    )
    txns = [
        NormalizedTransaction.from_mapping(t if isinstance(t, dict) else t.to_dict())
        for t in (getattr(result, "transactions", None) or [])
    ]
    return ExtractionResult(engine="old", metadata=meta, transactions=txns,
                            verification_status=vf.get("state") or None)


def _compare(bank_key: str, result: Any, v2_result) -> Dict[str, Any]:
    """Scalar agreement between the legacy output and the v2 result, via the migration comparator."""
    from app.services.migration.comparator import compare_results

    old = _legacy_extraction(bank_key, result)
    cmp_ = compare_results("shadow", bank_key, old, v2_result)
    codes = {f.code for f in cmp_.findings}
    legacy_known = (old.metadata.extras or {})
    return {
        "overall": cmp_.overall.value,
        "agree": {
            "opening": cmp_.opening_match if legacy_known.get("legacy_opening_known") else None,
            "closing": cmp_.closing_match if legacy_known.get("legacy_closing_known") else None,
            "rows": "TXN_COUNT" not in codes,
            "total_debit": "TOTAL_DEBIT" not in codes,
            "total_credit": "TOTAL_CREDIT" not in codes,
        },
    }


def run_v2_shadow(
    file_path: str,
    bank_key: str,
    result: Any,
    *,
    sink: Optional[ShadowSink] = None,
    audit_service: Any = None,
    job_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Run the v2 router alongside a finished legacy extraction and persist a small record.

    Returns None in "off" mode. In "shadow" it never raises into the pipeline: every
    failure — v2 exception, timeout, comparator problem, sink problem — is recorded as
    shadow_error:<type> and swallowed. "serve" raises via v2_mode().
    """
    if v2_mode() != "shadow":
        return None
    record: Dict[str, Any] = {"bank_key": bank_key}
    try:
        record["sha8"] = _sha8(file_path)
    except Exception:
        record["sha8"] = None
    try:
        import time

        start = time.monotonic()
        try:
            routed = _POOL.submit(_v2_route, file_path).result(timeout=SHADOW_TIMEOUT_S)
        except FutureTimeout:
            record["shadow_error"] = "TimeoutError"
            routed = None
        record["v2_ms"] = round((time.monotonic() - start) * 1000, 1)
        if routed is not None:
            record.update(
                v2_status=routed.status,
                layout_id=routed.layout_id,
                fallback_reason=routed.fallback_reason or None,
                v2_verdict=((routed.result.metadata.extras or {}).get("verdict") if routed.result else None),
            )
            if routed.result is not None:
                try:
                    record.update(_compare(bank_key, result, routed.result))
                except Exception as exc:
                    record["shadow_error"] = f"compare:{type(exc).__name__}"
    except Exception as exc:
        record["shadow_error"] = type(exc).__name__
    try:
        if sink is not None:
            sink(record)
        elif audit_service is not None and job_id:
            audit_service.create_job_event(
                job_id, event_type="v2_shadow", event_name="v2_shadow_compare",
                event_category="shadow", metadata=record,
            )
        else:
            _log_sink(record)
    except Exception:
        log.debug("v2 shadow sink failed", exc_info=True)
    return None
