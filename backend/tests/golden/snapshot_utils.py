"""Shared helpers for golden snapshot capture and regression."""

from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.services.banks._shared.lite_metrics import build_lite_report_model


def mask_account_number(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    if len(digits) <= 4:
        return f"****{digits}" if digits else "****"
    return f"****{digits[-4:]}"


def _float_or_none(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return round(float(Decimal(str(value).replace(",", "").strip())), 2)
    except Exception:
        try:
            return round(float(value), 2)
        except Exception:
            return None


def _txn_row(txn: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "date": str(txn.get("date") or ""),
        "description": str(txn.get("description") or txn.get("narration") or ""),
        "debit": _float_or_none(txn.get("debit")),
        "credit": _float_or_none(txn.get("credit")),
        "balance": _float_or_none(txn.get("balance")) or 0.0,
        "category": str(txn.get("category") or txn.get("display_category") or ""),
        "confidence": _float_or_none(txn.get("confidence") or txn.get("confidence_score")) or 0.0,
        "source": str(txn.get("source") or txn.get("classification_source") or "rule"),
        "is_recurring": bool(txn.get("is_recurring") or False),
    }


def category_totals(transactions: Sequence[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    totals: Dict[str, Dict[str, float]] = defaultdict(lambda: {"debit": 0.0, "credit": 0.0, "count": 0})
    for txn in transactions:
        cat = str(txn.get("category") or "Others")
        debit = _float_or_none(txn.get("debit")) or 0.0
        credit = _float_or_none(txn.get("credit")) or 0.0
        totals[cat]["debit"] += debit
        totals[cat]["credit"] += credit
        totals[cat]["count"] += 1
    # Stable JSON: sorted keys, rounded floats
    return {
        cat: {
            "debit": round(vals["debit"], 2),
            "credit": round(vals["credit"], 2),
            "count": int(vals["count"]),
        }
        for cat, vals in sorted(totals.items(), key=lambda kv: kv[0].lower())
    }


def _mismatch_entry(item: Any) -> Dict[str, Any]:
    if item is None:
        return {}
    if hasattr(item, "__dict__") and not isinstance(item, dict):
        data = {
            "transaction_index": getattr(item, "transaction_index", None),
            "expected_balance": getattr(item, "expected_balance", None),
            "actual_balance": getattr(item, "actual_balance", None),
            "difference": getattr(item, "difference", None),
            "previous_balance": getattr(item, "previous_balance", None),
            "transaction_amount": getattr(item, "transaction_amount", None),
            "is_debit": getattr(item, "is_debit", None),
        }
    elif isinstance(item, dict):
        data = dict(item)
    else:
        return {"raw": str(item)}
    return {
        "transaction_index": data.get("transaction_index"),
        "expected_balance": _float_or_none(data.get("expected_balance")),
        "actual_balance": _float_or_none(data.get("actual_balance")),
        "difference": _float_or_none(data.get("difference")),
        "previous_balance": _float_or_none(data.get("previous_balance")),
        "transaction_amount": _float_or_none(data.get("transaction_amount")),
        "is_debit": data.get("is_debit"),
    }


def _normalize_reconciliation(raw: Any) -> Dict[str, Any]:
    """Normalize recon result for golden JSON (Phase 3-ready fields)."""
    mismatches_raw: List[Any] = []
    if raw is None:
        return {
            "is_reconciled": True,
            "opening_balance": None,
            "closing_balance": None,
            "calculated_closing": None,
            "total_credits": None,
            "total_debits": None,
            "mismatch_count": 0,
            "final_difference": None,
            "transaction_count": None,
            "mismatches": [],
            "source": "empty",
        }

    # Preserve mismatches from object before to_dict (HDFC to_dict drops the list)
    if not isinstance(raw, dict):
        mismatches_raw = list(getattr(raw, "mismatches", None) or [])
        if hasattr(raw, "to_dict"):
            try:
                raw = raw.to_dict()
            except Exception:
                raw = {
                    "is_reconciled": getattr(raw, "is_reconciled", getattr(raw, "passed", True)),
                    "opening_balance": getattr(raw, "opening_balance", None),
                    "closing_balance": getattr(raw, "closing_balance", None),
                    "total_credits": getattr(raw, "total_credits", None),
                    "total_debits": getattr(raw, "total_debits", None),
                    "calculated_closing": getattr(raw, "calculated_closing", None),
                    "final_difference": getattr(raw, "final_difference", None),
                    "transaction_count": getattr(raw, "transaction_count", None),
                }
        else:
            raw = {
                "is_reconciled": getattr(raw, "is_reconciled", getattr(raw, "passed", True)),
                "opening_balance": getattr(raw, "opening_balance", None),
                "closing_balance": getattr(raw, "closing_balance", None),
            }

    if not isinstance(raw, dict):
        return {"raw_type": type(raw).__name__, "mismatches": [], "mismatch_count": 0}

    if not mismatches_raw:
        mismatches_raw = list(raw.get("mismatches") or [])

    mismatches = [_mismatch_entry(m) for m in mismatches_raw]
    mismatch_count = int(
        raw.get("mismatch_count")
        if raw.get("mismatch_count") is not None
        else len(mismatches)
    )

    return {
        "is_reconciled": bool(raw.get("is_reconciled", raw.get("passed", True))),
        "opening_balance": _float_or_none(raw.get("opening_balance")),
        "closing_balance": _float_or_none(raw.get("closing_balance")),
        "calculated_closing": _float_or_none(
            raw.get("calculated_closing") or raw.get("computed_closing")
        ),
        "total_credits": _float_or_none(raw.get("total_credits")),
        "total_debits": _float_or_none(raw.get("total_debits")),
        "mismatch_count": mismatch_count,
        "final_difference": _float_or_none(raw.get("final_difference")),
        "transaction_count": (
            int(raw["transaction_count"])
            if raw.get("transaction_count") is not None
            else None
        ),
        "mismatches": mismatches,
        "source": str(raw.get("source") or "reconciler"),
        "message": raw.get("message"),
    }


def infer_opening_closing(transactions: Sequence[Dict[str, Any]]) -> Dict[str, Optional[float]]:
    """Infer statement opening/closing from first/last balances when metadata missing."""
    if not transactions:
        return {"opening_balance": None, "closing_balance": None}
    first = transactions[0]
    last = transactions[-1]
    first_bal = _float_or_none(first.get("balance"))
    last_bal = _float_or_none(last.get("balance"))
    first_debit = _float_or_none(first.get("debit")) or 0.0
    first_credit = _float_or_none(first.get("credit")) or 0.0
    opening = None
    if first_bal is not None:
        # opening ≈ first_balance - credit + debit
        opening = round(first_bal - first_credit + first_debit, 2)
    return {"opening_balance": opening, "closing_balance": last_bal}


def run_bank_reconciliation(
    bank_key: str,
    transactions: Sequence[Dict[str, Any]],
    *,
    expected_opening: Optional[float] = None,
    expected_closing: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Deterministic running-balance reconciliation for golden snapshots.

    Uses pure math on the final transaction list so capture and regression
    always agree. Bank-specific reconciler quirks are intentionally NOT used
    here (they caused non-deterministic golden diffs when re-instantiated).
    bank_key is retained for metadata / future config only.
    """
    _ = bank_key  # reserved for per-bank tolerance config later
    inferred = infer_opening_closing(list(transactions))
    opening = expected_opening if expected_opening is not None else inferred["opening_balance"]
    closing = expected_closing if expected_closing is not None else inferred["closing_balance"]

    mismatches: List[Dict[str, Any]] = []
    total_credits = 0.0
    total_debits = 0.0
    prev = opening
    for idx, txn in enumerate(transactions):
        debit = _float_or_none(txn.get("debit")) or 0.0
        credit = _float_or_none(txn.get("credit")) or 0.0
        bal = _float_or_none(txn.get("balance"))
        total_debits += debit
        total_credits += credit
        if prev is not None and bal is not None:
            expected = round(prev + credit - debit, 2)
            if abs(expected - bal) > 0.02:
                mismatches.append(
                    {
                        "transaction_index": idx,
                        "expected_balance": expected,
                        "actual_balance": bal,
                        "difference": round(bal - expected, 2),
                        "previous_balance": prev,
                        "transaction_amount": debit or credit,
                        "is_debit": debit > 0,
                    }
                )
        if bal is not None:
            prev = bal

    calculated = None
    if opening is not None:
        calculated = round(opening + total_credits - total_debits, 2)
    final_diff = None
    if calculated is not None and closing is not None:
        final_diff = round(calculated - closing, 2)

    raw = {
        "is_reconciled": len(mismatches) == 0
        and (final_diff is None or abs(final_diff) <= 0.02),
        "opening_balance": opening,
        "closing_balance": closing,
        "calculated_closing": calculated,
        "total_credits": round(total_credits, 2),
        "total_debits": round(total_debits, 2),
        "final_difference": final_diff,
        "transaction_count": len(transactions),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "source": "running_balance",
    }
    return _normalize_reconciliation(raw)


def extract_reconciliation_from_result(
    result: Any,
    transactions: Sequence[Dict[str, Any]],
    bank_key: str,
) -> Dict[str, Any]:
    """
    Build Phase-3-ready recon from final transactions (deterministic math)
    plus pipeline status string for cross-check.
    """
    aggregation = getattr(result, "aggregation", None)
    expected_opening = None
    expected_closing = None
    if isinstance(aggregation, dict):
        expected_opening = _float_or_none(aggregation.get("opening_balance"))
        expected_closing = _float_or_none(aggregation.get("closing_balance"))
    elif aggregation is not None:
        expected_opening = _float_or_none(getattr(aggregation, "opening_balance", None))
        expected_closing = _float_or_none(getattr(aggregation, "closing_balance", None))

    recon = run_bank_reconciliation(
        bank_key,
        transactions,
        expected_opening=expected_opening,
        expected_closing=expected_closing,
    )

    # Cross-check pipeline status string (does not override real mismatch_count)
    recon_status = getattr(result, "reconciliation_status", None)
    if recon_status is not None:
        recon["pipeline_reconciliation_status"] = str(recon_status)
    return recon


def _aggregation_summary(aggregation: Any) -> Dict[str, Any]:
    if aggregation is None:
        return {}
    if hasattr(aggregation, "to_dict"):
        try:
            aggregation = aggregation.to_dict()
        except Exception:
            pass
    if not isinstance(aggregation, dict):
        return {
            "total_credits": _float_or_none(getattr(aggregation, "total_credits", None)),
            "total_debits": _float_or_none(getattr(aggregation, "total_debits", None)),
            "opening_balance": _float_or_none(getattr(aggregation, "opening_balance", None)),
            "closing_balance": _float_or_none(getattr(aggregation, "closing_balance", None)),
        }
    return {
        "total_credits": _float_or_none(aggregation.get("total_credits")),
        "total_debits": _float_or_none(aggregation.get("total_debits")),
        "opening_balance": _float_or_none(aggregation.get("opening_balance")),
        "closing_balance": _float_or_none(aggregation.get("closing_balance")),
    }


def build_snapshot_payload(
    *,
    bank_key: str,
    sample_name: str,
    mode: str,
    process_result: Dict[str, Any],
    transactions: Sequence[Dict[str, Any]],
    reconciliation: Any = None,
    aggregation: Any = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a commit-safe golden snapshot from pipeline outputs."""
    meta = dict(metadata or {})
    # Mask account identifiers
    for key in ("account_number", "account_no", "accountNumber"):
        if key in meta:
            meta[key] = mask_account_number(meta[key])

    txn_rows = [_txn_row(t if isinstance(t, dict) else {}) for t in transactions]
    # Prefer reconciliation from process_result if present
    recon = reconciliation
    if recon is None and isinstance(process_result, dict):
        recon = {
            "is_reconciled": process_result.get("reconciliation_status") == "passed"
            or process_result.get("validation", {}).get("reconciliation_passed"),
            "opening_balance": None,
            "closing_balance": None,
            "mismatch_count": 0,
        }

    lite_meta = {
        "name": meta.get("account_holder") or meta.get("name") or meta.get("full_name") or "",
        "account_no": mask_account_number(
            meta.get("account_number") or meta.get("account_no") or meta.get("accountNumber")
        ),
        "account_type": meta.get("account_type") or "",
        "bank_name": meta.get("bank_name") or bank_key,
        "opening_balance": meta.get("opening_balance"),
        "closing_balance": meta.get("closing_balance"),
        "statement_from": meta.get("statement_from"),
        "statement_to": meta.get("statement_to"),
    }
    try:
        lite_model = build_lite_report_model(txn_rows, lite_meta)
    except Exception as exc:
        lite_model = {"error": str(exc)}

    summary_stats = {}
    monthly_analysis = {}
    if isinstance(lite_model, dict) and "error" not in lite_model:
        summary_stats = lite_model.get("summary_stats") or {}
        monthly_analysis = lite_model.get("monthly_analysis") or {}

    return {
        "schema_version": 1,
        "bank_key": bank_key,
        "sample_name": sample_name,
        "mode": mode,
        "status": process_result.get("status") if isinstance(process_result, dict) else "unknown",
        "transaction_count": len(txn_rows),
        "transactions": txn_rows,
        "categories": [t["category"] for t in txn_rows],
        "category_totals": category_totals(txn_rows),
        "reconciliation": _normalize_reconciliation(recon),
        "aggregation": _aggregation_summary(aggregation),
        "summary_stats": summary_stats,
        "monthly_analysis": monthly_analysis,
        "pipeline_stats": (process_result.get("stats") if isinstance(process_result, dict) else {}) or {},
        "data_quality": (process_result.get("data_quality") if isinstance(process_result, dict) else None),
        "reconciliation_status": (
            process_result.get("reconciliation_status") if isinstance(process_result, dict) else None
        ),
        "metadata": {
            "bank_name": meta.get("bank_name") or bank_key,
            "account_number": mask_account_number(
                meta.get("account_number") or meta.get("account_no")
            ),
            "account_holder": meta.get("account_holder") or meta.get("name") or "",
            "statement_from": meta.get("statement_from") or "",
            "statement_to": meta.get("statement_to") or "",
        },
    }


def almost_equal(a: Any, b: Any, tol: float = 0.02) -> bool:
    if a is None and b is None:
        return True
    try:
        return abs(float(a) - float(b)) <= tol
    except Exception:
        return a == b


def assert_snapshot_match(expected: Dict[str, Any], actual: Dict[str, Any]) -> None:
    """Raise AssertionError with detail if golden fields diverge."""
    assert expected.get("transaction_count") == actual.get("transaction_count"), (
        f"transaction_count: expected {expected.get('transaction_count')} "
        f"got {actual.get('transaction_count')}"
    )
    assert expected.get("categories") == actual.get("categories"), (
        "category assignment mismatch"
    )
    assert expected.get("category_totals") == actual.get("category_totals"), (
        f"category_totals mismatch:\n expected={expected.get('category_totals')}\n"
        f" actual={actual.get('category_totals')}"
    )

    exp_recon = expected.get("reconciliation") or {}
    act_recon = actual.get("reconciliation") or {}
    assert bool(exp_recon.get("is_reconciled")) == bool(act_recon.get("is_reconciled")), (
        f"reconciliation status: expected {exp_recon.get('is_reconciled')} "
        f"got {act_recon.get('is_reconciled')}"
    )
    assert int(exp_recon.get("mismatch_count") or 0) == int(act_recon.get("mismatch_count") or 0), (
        f"reconciliation mismatch_count: expected {exp_recon.get('mismatch_count')} "
        f"got {act_recon.get('mismatch_count')}"
    )
    for field in (
        "opening_balance",
        "closing_balance",
        "calculated_closing",
        "total_credits",
        "total_debits",
        "final_difference",
    ):
        if exp_recon.get(field) is None and act_recon.get(field) is None:
            continue
        assert almost_equal(exp_recon.get(field), act_recon.get(field)), (
            f"reconciliation.{field}: expected {exp_recon.get(field)} got {act_recon.get(field)}"
        )
    if exp_recon.get("mismatches") is not None:
        assert len(exp_recon.get("mismatches") or []) == len(act_recon.get("mismatches") or []), (
            f"reconciliation mismatches length: expected {len(exp_recon.get('mismatches') or [])} "
            f"got {len(act_recon.get('mismatches') or [])}"
        )

    # Summary stats: compare keys present in expected
    exp_summary = expected.get("summary_stats") or {}
    act_summary = actual.get("summary_stats") or {}
    for key, exp_val in exp_summary.items():
        if isinstance(exp_val, dict):
            act_val = act_summary.get(key) or {}
            for month, month_val in exp_val.items():
                assert almost_equal(month_val, act_val.get(month)), (
                    f"summary_stats[{key}][{month}]: expected {month_val} got {act_val.get(month)}"
                )
        else:
            assert almost_equal(exp_val, act_summary.get(key)), (
                f"summary_stats[{key}]: expected {exp_val} got {act_summary.get(key)}"
            )

    exp_monthly = expected.get("monthly_analysis") or {}
    act_monthly = actual.get("monthly_analysis") or {}
    for metric, month_map in exp_monthly.items():
        if not isinstance(month_map, dict):
            continue
        act_map = act_monthly.get(metric) or {}
        for month, exp_val in month_map.items():
            assert almost_equal(exp_val, act_map.get(month)), (
                f"monthly_analysis[{metric}][{month}]: expected {exp_val} got {act_map.get(month)}"
            )


# Display folder names under samples/ → pipeline bank_key
FOLDER_TO_BANK_KEY = {
    "hdfc": "hdfc",
    "hdfc bank": "hdfc",
    "axis": "axis",
    "axis bank": "axis",
    "sbi": "sbi",
    "state bank": "sbi",
    "icici": "icici",
    "icici bank": "icici",
    "canara": "canara",
    "canara bank": "canara",
    "kotak": "kotak",
    "kotak bank": "kotak",
    "indian bank": "indian_bank",
    "indian_bank": "indian_bank",
    "bank of india": "bank_of_india",
    "bank_of_india": "bank_of_india",
    "idfc": "idfc",
    "idfc bank": "idfc",
    "idfc first bank": "idfc",
    "karnataka": "karnataka",
    "karnataka bank": "karnataka",
    "paytm": "paytm",
    "paytm bank": "paytm",
    "union": "union",
    "union bank": "union",
    "union bank of india": "union",
    "bank of baroda": "bank_of_baroda",
    "bank_of_baroda": "bank_of_baroda",
    "unknown": "unknown",
    "others": "unknown",
}


def folder_to_bank_key(folder_name: str) -> Optional[str]:
    key = str(folder_name or "").strip().lower()
    if key in FOLDER_TO_BANK_KEY:
        return FOLDER_TO_BANK_KEY[key]
    # Try pipeline normalizer if available
    try:
        from app.services.pipeline_orchestrator import _normalize_bank_name

        return _normalize_bank_name(folder_name)
    except Exception:
        return None


def sanitize_sample_name(name: str) -> str:
    """Filesystem-safe sample stem for golden JSON filenames."""
    text = str(name or "sample").strip()
    text = re.sub(r"[^\w.\-]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("._")
    return text[:120] or "sample"


def discover_samples(samples_dir: Path) -> List[Dict[str, str]]:
    """
    Discover PDFs under samples_dir.

    Preferred layout: samples/{bank_key|Display Name}/*.pdf
    Flat layout: samples/*.pdf with bank_key inferred from filename prefix
      e.g. hdfc_stmt.pdf → bank_key=hdfc
    """
    samples_dir = Path(samples_dir)
    found: List[Dict[str, str]] = []
    if not samples_dir.is_dir():
        return found

    # Nested by bank folder (display name or bank_key)
    for bank_dir in sorted(p for p in samples_dir.iterdir() if p.is_dir()):
        if bank_dir.name.startswith(".") or bank_dir.name == "__pycache__":
            continue
        bank_key = folder_to_bank_key(bank_dir.name)
        if not bank_key:
            continue
        for pdf in sorted(bank_dir.glob("*.pdf")):
            found.append(
                {
                    "bank_key": bank_key,
                    "sample_name": sanitize_sample_name(pdf.stem),
                    "path": str(pdf.resolve()),
                }
            )

    # Flat PDFs at root
    for pdf in sorted(samples_dir.glob("*.pdf")):
        stem = pdf.stem.lower()
        bank_key = folder_to_bank_key(stem.split("_")[0] if "_" in stem else stem)
        if not bank_key:
            bank_key = stem.split("_")[0] if "_" in stem else stem
        found.append(
            {
                "bank_key": bank_key,
                "sample_name": sanitize_sample_name(pdf.stem),
                "path": str(pdf.resolve()),
            }
        )
    return found


def bank_display_name(bank_key: str) -> str:
    mapping = {
        "hdfc": "HDFC Bank",
        "axis": "Axis Bank",
        "sbi": "SBI",
        "icici": "ICICI Bank",
        "canara": "Canara Bank",
        "kotak": "Kotak Bank",
        "indian_bank": "Indian Bank",
        "bank_of_india": "Bank of India",
        "idfc": "IDFC Bank",
        "karnataka": "Karnataka Bank",
        "paytm": "Paytm Bank",
        "union": "Union Bank of India",
        "bank_of_baroda": "Bank of Baroda",
        "unknown": "Unknown",
    }
    return mapping.get(bank_key.lower(), bank_key)
