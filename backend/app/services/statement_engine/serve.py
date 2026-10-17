"""Serving path for the v2 statement engine (contract: docs/engine/V2_API_CONTRACT.md).

Flag-gated, default OFF. In `serve` mode an allow-listed bank's statement may be
processed from verified v2 rows; everything else stays on the legacy path with a
small additive `statement_engine` block describing what happened.

Never raises into the pipeline: any v2 problem degrades to "legacy, unchanged".
"""
from __future__ import annotations

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .shadow import v2_mode
from .v2_router import DETECTOR_TO_SPEC_BANK, _CONFIDENT, detect_spec_bank, route_pages

log = logging.getLogger(__name__)

SERVE_BANKS_ENV = "STATEMENT_ENGINE_V2_SERVE_BANKS"
SERVE_TIMEOUT_S = float(os.getenv("STATEMENT_ENGINE_V2_SERVE_TIMEOUT_S", "30"))
_POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="v2-serve")

# user-facing spec key when the selection is "auto-detect" / not a real bank
_AUTO_KEYS = {"unknown", "auto", "auto_detect", "autodetect", "other", ""}


def serve_banks() -> frozenset:
    """Spec bank keys allowed to be served by v2 (empty = none, even in serve mode)."""
    raw = os.getenv(SERVE_BANKS_ENV) or ""
    return frozenset(k.strip().lower() for k in raw.split(",") if k.strip())


def spec_key_for(bank_key: str) -> str:
    """Pipeline bank key -> spec bank key (the allowlist and layouts use spec keys)."""
    return DETECTOR_TO_SPEC_BANK.get((bank_key or "").lower(), (bank_key or "").lower())


def pipeline_key_for(spec_key: str) -> str:
    """Spec bank key -> legacy pipeline processor key (reverse of spec_key_for)."""
    rev = {v: k for k, v in DETECTOR_TO_SPEC_BANK.items()}
    return rev.get((spec_key or "").lower(), (spec_key or "").lower())


def spec_bank_keys() -> frozenset:
    """Spec bank keys that have at least one registered layout."""
    from .extractors.registry import DEFAULT_REGISTRY
    return frozenset(s.bank_key for s in DEFAULT_REGISTRY._specs.values())


def serving_enabled_for(bank_key: str) -> bool:
    """True when mode==serve and this bank may be v2-served.

    A concrete bank needs its spec key in the allowlist. An auto-detect
    selection defers eligibility to the routed bank (checked again in
    decide_serve); with an empty allowlist nothing is ever served."""
    try:
        mode = v2_mode()
    except Exception:
        return False
    if mode != "serve" or not serve_banks():
        return False
    if (bank_key or "").lower() in _AUTO_KEYS:
        return True
    return spec_key_for(bank_key) in serve_banks()


# --------------------------------------------------------------------------- #
# Routing                                                                      #
# --------------------------------------------------------------------------- #

def _route_once(pdf_path: str, spec_key: str):
    """Read pages once, detect + route through the production router."""
    from .extractors.registry import DEFAULT_REGISTRY
    from .extraction.pdf_extractor import read_pages

    pages = read_pages(pdf_path, None)
    _det_spec, det = detect_spec_bank(pages)
    routed = route_pages(pages, DEFAULT_REGISTRY, "" if spec_key in _AUTO_KEYS else spec_key)
    return routed, det


def route_for_serve(pdf_path: str, spec_key: str, timeout_s: float = SERVE_TIMEOUT_S):
    """(RoutedExtraction, DetectionResult, elapsed_ms) or (None, det, ms) on timeout."""
    start = time.monotonic()
    try:
        routed, det = _POOL.submit(_route_once, pdf_path, spec_key).result(timeout=timeout_s)
    except FutureTimeout:
        return None, None, round((time.monotonic() - start) * 1000, 1)
    return routed, det, round((time.monotonic() - start) * 1000, 1)


# --------------------------------------------------------------------------- #
# Outcome helpers                                                              #
# --------------------------------------------------------------------------- #

def v2_verdict(routed) -> Optional[str]:
    if routed is None or routed.status != "v2" or routed.result is None:
        return None
    return (routed.result.metadata.extras or {}).get("verdict")


def v2_checks(routed) -> Dict[str, Dict[str, Any]]:
    if routed is None or routed.result is None:
        return {}
    return dict((routed.result.metadata.extras or {}).get("checks") or {})


def _status(checks: Dict[str, Dict[str, Any]], name: str) -> Optional[str]:
    c = checks.get(name)
    return (c or {}).get("status")


def anchored(routed) -> bool:
    """True when the independent-anchor check ran and passed (printed reference)."""
    return _status(v2_checks(routed), "reference") == "pass"


def review_codes(routed) -> List[str]:
    """Contract §4: codes derived from per-check statuses, never from message text."""
    checks = v2_checks(routed)
    codes: List[str] = []
    st = {n: _status(checks, n) for n in ("reference", "chain", "side", "totals", "dates",
                                          "date_outliers", "period", "schema", "segments",
                                          "checkpoints", "balance_delta")}
    if st["reference"] in ("skipped", "skip"):
        codes.append("NO_INDEPENDENT_ANCHOR")
    elif st["reference"] == "fail":
        codes.append("REFERENCE_MISMATCH")
    if st["chain"] == "skipped":
        codes.append("NO_RUNNING_BALANCE")          # balance-less layout: chain cannot engage; REVIEW ceiling
    elif st["chain"] == "fail":
        codes.append("CHAIN_BREAK")
    if st["chain"] == "warn" and (checks.get("chain") or {}).get("same_date_disorder"):
        codes.append("SAME_DATE_DISORDER")          # same-date rows print out of balance order; reorder reconciles
    if st["checkpoints"] == "fail":
        codes.append("CHECKPOINT_MISMATCH")         # printed B/F-C/F balance contradicts the rows between
    if st["balance_delta"] == "fail":
        codes.append("BALANCE_DELTA_MISMATCH")      # printed opening->closing gap disagrees with the sums
    if st["segments"] in ("fail", "warn"):
        codes.append("SEGMENT_COUNT_MISMATCH")      # per-account printed transaction count not reproduced
    if st["side"] in ("fail", "warn"):
        codes.append("SIDE_MISMATCH")
    if st["totals"] in ("fail", "warn"):
        codes.append("TOTALS_MISMATCH")
    if st["dates"] == "warn":
        codes.append("DATE_ORDER")
    if st["date_outliers"] == "warn":
        codes.append("DATE_OUTLIER")
    if st["period"] == "warn":
        codes.append("OUTSIDE_PERIOD")
    if st["schema"] == "fail":
        codes.append("SCHEMA_ERRORS")
    if routed is not None and routed.result is not None \
            and any(str(w).startswith("rows_without_section_date") for w in (routed.result.warnings or [])):
        codes.append("SECTION_DATE_MISSING")        # date-grouped layout: a transaction printed before any section date
    if routed is not None and routed.result is not None and routed.result.warnings:
        codes.append("EXTRACTION_WARNINGS")
    return codes


def bank_mismatch(det, spec_key: str) -> bool:
    """Detector is confident and names a different spec bank than the one selected."""
    if det is None or det.bank_id is None or det.confidence.name not in _CONFIDENT:
        return False
    det_spec = DETECTOR_TO_SPEC_BANK.get(det.bank_id)
    if not det_spec:
        return False
    if spec_key in _AUTO_KEYS:
        return False  # auto-detect: the detector IS the source, not a mismatch
    return det_spec != spec_key


def detected_bank_block(det, selected_spec_key: str, mismatch: bool) -> Optional[Dict[str, Any]]:
    """Contract §3/§6 detected_bank object."""
    from .registry import default_registry
    reg = default_registry()
    if mismatch:
        cfg = reg.get(det.bank_id) if det else None
        return {
            "key": det.bank_id,
            "name": cfg.display_name if cfg else det.bank_id,
            "confidence": det.confidence.name if det else None,
            "source": "detector",
        }
    if selected_spec_key in _AUTO_KEYS and det is not None and det.bank_id and det.confidence.name in _CONFIDENT:
        cfg = reg.get(det.bank_id)
        return {
            "key": det.bank_id,
            "name": cfg.display_name if cfg else det.bank_id,
            "confidence": det.confidence.name,
            "source": "detector",
        }
    cfg = reg.get(selected_spec_key)
    if cfg is None:  # spec keys like 'bob' differ from detector ids ('bank_of_baroda')
        cfg = next((b for b in reg.banks.values() if DETECTOR_TO_SPEC_BANK.get(b.id) == selected_spec_key), None)
    return {
        "key": selected_spec_key or None,
        "name": cfg.display_name if cfg else selected_spec_key or None,
        "confidence": None,
        "source": "user",
    }


# --------------------------------------------------------------------------- #
# Block (contract §3)                                                          #
# --------------------------------------------------------------------------- #

def minimal_block(mode: str) -> Dict[str, Any]:
    """Mode off/shadow or v2 untouched: legacy rows served, nothing else known."""
    return {
        "engine": "legacy",
        "mode": mode,
        "layout_id": None,
        "verdict": None,
        "needs_review": False,
        "review_codes": [],
        "anchored": False,
        "detected_bank": None,
        "advisory": None,
    }


def advisory_block(routed) -> Dict[str, Any]:
    """v2 outcome attached to a legacy-served result."""
    return {
        "verdict": v2_verdict(routed),
        "review_codes": review_codes(routed),
        "layout_id": routed.layout_id if routed else None,
    }


def engine_block(
    *,
    engine: str,
    mode: str,
    routed=None,
    verdict: Optional[str] = None,
    needs_review: bool = False,
    codes: Optional[List[str]] = None,
    detected_bank: Optional[Dict[str, Any]] = None,
    advisory: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "engine": engine,
        "mode": mode,
        "layout_id": routed.layout_id if routed else None,
        "verdict": verdict,
        "needs_review": needs_review,
        "review_codes": list(codes or []),
        "anchored": anchored(routed) if routed else False,
        "detected_bank": detected_bank,
        "advisory": advisory,
    }


# --------------------------------------------------------------------------- #
# Policy + serving decision (contract §2)                                       #
# --------------------------------------------------------------------------- #

@dataclass
class ServePlan:
    """What process_statement should do, computed before any pipeline run."""
    block: Dict[str, Any]
    serve_v2: bool = False            # run the pipeline on v2 rows
    needs_review: bool = False        # v2 rows served but flagged
    run_legacy: bool = True           # legacy processor should run (normally)
    advisory: bool = False            # attach v2 outcome to a legacy result
    routed: Any = None
    v2_spec_key: str = ""             # bank whose processor should run v2 rows
    mismatch: bool = False
    routed_ms: float = 0.0


def decide_serve(
    *,
    bank_key: str,
    spec_key: str,
    routed,
    det,
    legacy_available: bool,
    routed_ms: float,
) -> ServePlan:
    """Apply the contract §2 matrix. Never raises."""
    mode = "serve"
    mismatch = bank_mismatch(det, spec_key)
    det_block = detected_bank_block(det, spec_key, mismatch)
    verdict = v2_verdict(routed)
    codes = review_codes(routed)
    if mismatch:
        codes = codes + ["BANK_MISMATCH"]

    if mismatch or verdict == "FAILED" or verdict is None:
        # never serve v2 rows: legacy runs; a real v2 verdict becomes advisory
        adv = advisory_block(routed) if verdict in ("REVIEW", "FAILED") else None
        block = engine_block(engine="legacy", mode=mode, routed=routed if adv else None,
                             verdict=None, needs_review=False, codes=["BANK_MISMATCH"] if mismatch else [],
                             detected_bank=det_block, advisory=adv)
        return ServePlan(block=block, advisory=adv is not None, routed=routed,
                         mismatch=mismatch, routed_ms=routed_ms)

    # auto-detect: the routed bank, not the selection, decides serve eligibility
    if spec_key in _AUTO_KEYS:
        routed_key = _spec_key_of_routed(routed, "")
        if routed_key not in serve_banks():
            block = engine_block(engine="legacy", mode=mode, routed=None,
                                 verdict=None, needs_review=False, codes=[],
                                 detected_bank=det_block, advisory=None)
            return ServePlan(block=block, routed=routed, mismatch=mismatch,
                             routed_ms=routed_ms)
        spec_key = routed_key

    # VERIFIED or REVIEW on an allowlisted bank
    if verdict == "VERIFIED" or not legacy_available:
        serve_v2 = True
        needs_review = verdict != "VERIFIED"
        adv = None
    else:
        # REVIEW + legacy available: legacy serves, v2 outcome advises
        serve_v2, needs_review = False, False
        adv = advisory_block(routed)
    block = engine_block(
        engine="v2" if serve_v2 else "legacy",
        mode=mode,
        routed=routed,
        verdict=verdict if serve_v2 else None,
        needs_review=needs_review,
        codes=codes if serve_v2 else (["BANK_MISMATCH"] if mismatch else []),
        detected_bank=det_block,
        advisory=adv,
    )
    spec_for_rows = spec_key if spec_key not in _AUTO_KEYS else _spec_key_of_routed(routed, spec_key)
    return ServePlan(block=block, serve_v2=serve_v2, needs_review=needs_review,
                     run_legacy=not serve_v2, advisory=adv is not None,
                     routed=routed, v2_spec_key=spec_for_rows,
                     mismatch=mismatch, routed_ms=routed_ms)


def _spec_key_of_routed(routed, fallback: str) -> str:
    """Spec bank that produced the routed layout (auto-detect serving)."""
    if routed is not None and routed.result is not None:
        key = (routed.result.metadata.bank_key or "") if routed.result.metadata else ""
        if key:
            return key
    return fallback


# --------------------------------------------------------------------------- #
# V2 rows -> pipeline row source                                                #
# --------------------------------------------------------------------------- #

@dataclass
class V2RowSource:
    """Everything _run_pipeline needs from a v2 outcome (engine-hook)."""
    transactions: List[Dict[str, Any]]
    opening_balance: Any = None
    closing_balance: Any = None
    total_debits: Any = None
    total_credits: Any = None
    dr_count: Any = None
    cr_count: Any = None
    statement_from: Optional[str] = None
    statement_to: Optional[str] = None
    account_number: Optional[str] = None
    ifsc: Optional[str] = None


def _recover_narration(rows: List[Dict[str, Any]]) -> None:
    """Some layouts print the narration under a column the spec reads as `ref`
    (e.g. Airtel "Transaction ID/Particulars"), leaving `description` empty, so the
    classifier saw nothing and every row fell to "Others". When the description is
    blank (or only stray digits) and ref_no is real text (>=3 letters, not a bare cheque number) use it as the
    narration. ref_no itself is left untouched."""
    import re as _re
    for r in rows:
        desc = str(r.get("description") or "").strip()
        if len(_re.findall(r"[A-Za-z]", desc)) >= 3:
            continue  # real narration already present
        ref = str(r.get("ref_no") or "").strip()
        if len(_re.findall(r"[A-Za-z]", ref)) >= 3:
            r["description"] = ref  # blank / stray wrap digits -> real text from ref


def row_source_from_routed(routed) -> Optional[V2RowSource]:
    """v2 result -> V2RowSource; None when there is no served row data."""
    if routed is None or routed.result is None:
        return None
    txns = routed.result.transactions or []
    if not txns:
        return None
    meta = routed.result.metadata
    extras = (meta.extras or {}) if meta else {}
    printed = extras.get("printed_summary") or {}
    rows = [t.to_dict() if hasattr(t, "to_dict") else dict(t) for t in txns]
    _recover_narration(rows)
    opening = printed.get("opening") or getattr(meta, "opening_balance", None)
    closing = printed.get("closing") or getattr(meta, "closing_balance", None)

    def _dec(v):
        from decimal import Decimal, InvalidOperation
        try:
            return None if v in (None, "") else Decimal(str(v).replace(",", ""))
        except (InvalidOperation, ValueError):
            return None

    total_debits = _dec(printed.get("debits")) or sum(
        (_dec(t.get("debit")) or 0) for t in rows) or None
    total_credits = _dec(printed.get("credits")) or sum(
        (_dec(t.get("credit")) or 0) for t in rows) or None
    return V2RowSource(
        transactions=rows,
        opening_balance=_dec(opening),
        closing_balance=_dec(closing),
        total_debits=total_debits,
        total_credits=total_credits,
        dr_count=printed.get("dr_count"),
        cr_count=printed.get("cr_count"),
        statement_from=getattr(meta, "statement_from", None) or None,
        statement_to=getattr(meta, "statement_to", None) or None,
        account_number=getattr(meta, "account_number", None),
        ifsc=extras.get("ifsc"),
    )


# --------------------------------------------------------------------------- #
# Excel — "Statement Check" sheet (contract §8/W8-3)                            #
# --------------------------------------------------------------------------- #

_STATEMENT_CHECK_SHEET = "Statement Check"


def append_statement_check_sheet(excel_path: str, block: Dict[str, Any]) -> bool:
    """Append the Statement Check sheet after the existing sheets. Returns True on write.

    Caller decides when: engine == "v2" or needs_review or an advisory exists.
    Never alters existing sheets; never called at mode off.
    """
    if not excel_path or not os.path.isfile(excel_path):
        return False
    try:
        from openpyxl import load_workbook

        wb = load_workbook(excel_path)
        if _STATEMENT_CHECK_SHEET in wb.sheetnames:
            return True
        ws = wb.create_sheet(_STATEMENT_CHECK_SHEET)
        reasons = block.get("review_codes") or []
        advisory = block.get("advisory") or {}
        ws.append(["Statement Check"])
        ws.append(["Engine", block.get("engine")])
        ws.append(["Verdict", block.get("verdict") or (advisory.get("verdict") or "")])
        ws.append(["Independently verified", "yes" if block.get("anchored") else "no"])
        # A FAILED advisory means the engine read the statement but could not reconcile its balances while the legacy
        # parser produced this workbook: it must not say "no review needed" next to a FAILED verdict.
        advisory_failed = (advisory.get("verdict") == "FAILED") and block.get("engine") != "v2"
        ws.append(["Needs review", "yes" if (block.get("needs_review") or advisory_failed) else "no"])
        ws.append(["Review reasons", ", ".join(reasons) if reasons else "none"])
        if advisory:
            ws.append(["Advisory verdict", advisory.get("verdict") or ""])
            ws.append(["Advisory reasons", ", ".join(advisory.get("review_codes") or []) or "none"])
        if advisory_failed:
            ws.append(["Note", "The statement engine could not reconcile this statement's balances. The figures in this "
                               "workbook come from the legacy parser and may be incomplete: check the transaction count "
                               "against the PDF before relying on it."])
        ws.append(["Generated", datetime.now(timezone.utc).isoformat(timespec="seconds")])
        wb.save(excel_path)
        return True
    except Exception as exc:
        log.warning("Statement Check sheet append failed (%s); workbook unchanged", type(exc).__name__)
        return False


def apply_row_count_guard(block: Dict[str, Any], routed, workbook_rows: Optional[int]) -> Dict[str, Any]:
    """A served v2 workbook must carry exactly the rows the engine read.

    If it does not, the workbook is no longer what the engine verified: the block is flagged for review
    (it never claims a clean result). Only v2-served blocks are touched; counts that cannot be compared are ignored.
    """
    try:
        if not block or block.get("engine") != "v2" or routed is None or workbook_rows is None:
            return block
        engine_rows = len(routed.result.transactions or [])
        if engine_rows and int(workbook_rows) != engine_rows:
            block["needs_review"] = True
            block["anchored"] = False
            codes = list(block.get("review_codes") or [])
            if "WORKBOOK_ROW_COUNT_MISMATCH" not in codes:
                codes.append("WORKBOOK_ROW_COUNT_MISMATCH")
            block["review_codes"] = codes
            log.warning("v2 served workbook rows (%s) differ from engine rows (%s)", workbook_rows, engine_rows)
    except Exception:
        log.debug("row count guard failed", exc_info=True)
    return block


def wants_statement_check(block: Dict[str, Any]) -> bool:
    return bool(block) and (
        block.get("engine") == "v2" or block.get("needs_review") or bool(block.get("advisory"))
    )


def audit_serve_decision(audit_service, job_id: Optional[str], block: Dict[str, Any]) -> None:
    """Persist the decision block as the v2_serve_decision job event (block only)."""
    if not audit_service or not job_id or not block:
        return
    try:
        audit_service.create_job_event(
            job_id,
            event_type="v2_serve_decision",
            event_name="v2_serve_decision",
            event_category="v2",
            metadata=dict(block),
        )
    except Exception:
        log.debug("v2_serve_decision audit failed", exc_info=True)
