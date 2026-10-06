"""Verification v1: independent checks on RAW parser output (observe-only).

Contract
--------
* Input is the parser's rows BEFORE `repair_transaction_sides`. The engine never
  mutates its input and never sees repaired rows, so a repair cannot make a bad
  parse look good.
* Observe-only: the result is attached to the pipeline result; no behaviour changes.
* Pure stdlib. Money is compared in integer paise to avoid float noise.

State rules (v1, to be tuned from the baseline):
  FAILED   any of balance_check / opening_closing_check / printed_totals_check fails
  REVIEW   no hard failure, but schema/duplicate/period failed, or balance_check
           could not run (nothing independent to verify against)
  VERIFIED no failures and balance_check passed
repair_stats are recorded on the report and do NOT influence the state in v1.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .models import (
    BALANCE_CHECK,
    DUPLICATE_CHECK,
    HARD_CHECKS,
    HEADER_PERIOD_CHECK,
    OPENING_CLOSING_CHECK,
    PRINTED_TOTALS_CHECK,
    SCHEMA_CHECK,
    CheckResult,
    HeaderPeriod,
    PrintedTotals,
    VerificationReport,
)

TOLERANCE_PAISE = 1  # 1 paisa
MAX_EXAMPLES = 5

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%d/%m/%y",
    "%d-%m-%y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d %b %Y",
    "%d %b %y",
    "%d/%b/%Y",
    "%d %B %Y",
    "%d-%B-%Y",
    "%b %d, %Y",
)


# ── helpers ────────────────────────────────────────────────────────────────
def parse_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    text = text.split(" 00:00")[0]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def to_paise(value: Any) -> Optional[int]:
    """Money -> integer paise. None/''/non-numeric -> None. Zero stays 0."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(round(float(str(value).replace(",", "")) * 100))
    except (TypeError, ValueError):
        return None


def _amount(row: Mapping[str, Any], key: str) -> int:
    """Amount in paise; absent / None counts as 0 (side not used)."""
    p = to_paise(row.get(key))
    return p or 0


def _side(row: Mapping[str, Any]) -> str:
    d, c = _amount(row, "debit"), _amount(row, "credit")
    if d and c:
        return "both"
    if d:
        return "debit"
    if c:
        return "credit"
    return "none"


def _close(a: int, b: int) -> bool:
    return abs(a - b) <= TOLERANCE_PAISE


# ── individual checks ──────────────────────────────────────────────────────
def _chain_mismatches(
    rows: Sequence[Mapping[str, Any]], opening: Optional[int]
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """Return (checked, mismatches, examples) for prev_balance + credit - debit == balance."""
    checked = 0
    mismatches = 0
    examples: List[Dict[str, Any]] = []
    prev: Optional[int] = opening
    for i, row in enumerate(rows):
        bal = to_paise(row.get("balance"))
        if bal is None:
            prev = None  # chain broken; cannot judge the next row
            continue
        if prev is not None:
            expected = prev + _amount(row, "credit") - _amount(row, "debit")
            checked += 1
            if not _close(expected, bal):
                mismatches += 1
                if len(examples) < MAX_EXAMPLES:
                    examples.append(
                        {
                            "row": i,
                            "expected_balance": expected / 100,
                            "actual_balance": bal / 100,
                            "diff": (bal - expected) / 100,
                        }
                    )
        prev = bal
    return checked, mismatches, examples


def check_balance(rows: Sequence[Mapping[str, Any]], opening: Optional[float]) -> CheckResult:
    opening_p = to_paise(opening)
    with_balance = sum(1 for r in rows if to_paise(r.get("balance")) is not None)
    if len(rows) == 0 or with_balance < 2:
        return CheckResult(
            BALANCE_CHECK,
            "skip",
            {"reason": "fewer than 2 rows carry a running balance", "rows_with_balance": with_balance},
        )

    asc = _chain_mismatches(rows, opening_p)
    # Some banks list newest first. Try the reversed order too and keep the better reading.
    desc_rows = list(reversed(rows))
    desc = _chain_mismatches(desc_rows, None)
    order = "as_parsed"
    checked, mismatches, examples = asc
    if desc[0] > 0 and (desc[1] / desc[0]) < (mismatches / max(checked, 1)) and mismatches > 0:
        order = "reversed"
        checked, mismatches, examples = desc

    return CheckResult(
        BALANCE_CHECK,
        "pass" if mismatches == 0 else "fail",
        {
            "rows_checked": checked,
            "mismatches": mismatches,
            "order_used": order,
            "opening_used": opening_p / 100 if opening_p is not None else None,
            "examples": examples,
        },
    )


def check_opening_closing(
    rows: Sequence[Mapping[str, Any]], opening: Optional[float], closing: Optional[float]
) -> CheckResult:
    o, c = to_paise(opening), to_paise(closing)
    if o is None or c is None:
        return CheckResult(
            OPENING_CLOSING_CHECK,
            "skip",
            {"reason": "opening and/or closing balance not available", "opening": opening, "closing": closing},
        )
    credits = sum(_amount(r, "credit") for r in rows)
    debits = sum(_amount(r, "debit") for r in rows)
    calc = o + credits - debits

    # Where do the declared figures sit relative to the rows' own running balances?
    # (Diagnosis only: it explains a failure, it never turns a failure into a pass.)
    chain_open: Optional[int] = None
    chain_close: Optional[int] = None
    if rows:
        first_bal = to_paise(rows[0].get("balance"))
        if first_bal is not None:
            chain_open = first_bal - _amount(rows[0], "credit") + _amount(rows[0], "debit")
        chain_close = to_paise(rows[-1].get("balance"))
    return CheckResult(
        OPENING_CLOSING_CHECK,
        "pass" if _close(calc, c) else "fail",
        {
            "opening": o / 100,
            "closing": c / 100,
            "sum_credits": credits / 100,
            "sum_debits": debits / 100,
            "calculated_closing": calc / 100,
            "difference": (c - calc) / 100,
            "chain_implied_opening": chain_open / 100 if chain_open is not None else None,
            "last_row_balance": chain_close / 100 if chain_close is not None else None,
            "declared_opening_matches_chain": _close(o, chain_open) if chain_open is not None else None,
            "declared_closing_matches_last_row": _close(c, chain_close) if chain_close is not None else None,
        },
    )


def check_printed_totals(
    rows: Sequence[Mapping[str, Any]], printed: Optional[PrintedTotals]
) -> CheckResult:
    if printed is None or printed.is_empty():
        return CheckResult(PRINTED_TOTALS_CHECK, "skip", {"reason": "statement prints no totals/counts we could read"})
    dr_n = sum(1 for r in rows if _amount(r, "debit"))
    cr_n = sum(1 for r in rows if _amount(r, "credit"))
    dr_sum = sum(_amount(r, "debit") for r in rows)
    cr_sum = sum(_amount(r, "credit") for r in rows)
    diffs: Dict[str, Any] = {}
    compared = 0
    if printed.debit_count is not None:
        compared += 1
        if printed.debit_count != dr_n:
            diffs["debit_count"] = {"printed": printed.debit_count, "raw": dr_n}
    if printed.credit_count is not None:
        compared += 1
        if printed.credit_count != cr_n:
            diffs["credit_count"] = {"printed": printed.credit_count, "raw": cr_n}
    p = to_paise(printed.total_debits)
    if p is not None:
        compared += 1
        if not _close(p, dr_sum):
            diffs["total_debits"] = {"printed": p / 100, "raw": dr_sum / 100}
    p = to_paise(printed.total_credits)
    if p is not None:
        compared += 1
        if not _close(p, cr_sum):
            diffs["total_credits"] = {"printed": p / 100, "raw": cr_sum / 100}
    return CheckResult(
        PRINTED_TOTALS_CHECK,
        "pass" if not diffs else "fail",
        {"compared": compared, "differences": diffs},
    )


def check_duplicates(rows: Sequence[Mapping[str, Any]]) -> CheckResult:
    """Rows identical on date, description, debit, credit AND balance are almost surely one row parsed twice."""
    keys: Counter = Counter()
    unverifiable = 0
    for r in rows:
        if to_paise(r.get("balance")) is None:
            unverifiable += 1
            continue
        keys[
            (
                str(r.get("date")),
                str(r.get("description", "")).strip(),
                _amount(r, "debit"),
                _amount(r, "credit"),
                to_paise(r.get("balance")),
            )
        ] += 1
    dupes = {k: n for k, n in keys.items() if n > 1}
    extra = sum(n - 1 for n in dupes.values())
    examples = [
        {
            "date": k[0],
            "description": k[1][:60],
            "debit": k[2] / 100,
            "credit": k[3] / 100,
            "balance": k[4] / 100,
            "count": n,
        }
        for k, n in list(dupes.items())[:MAX_EXAMPLES]
    ]
    zero_amount_groups = sum(1 for k in dupes if k[2] == 0 and k[3] == 0)
    return CheckResult(
        DUPLICATE_CHECK,
        "pass" if not dupes else "fail",
        {
            "duplicate_groups": len(dupes),
            "extra_rows": extra,
            "groups_with_zero_amounts": zero_amount_groups,
            "rows_without_balance": unverifiable,
            "examples": examples,
        },
    )


def check_schema(rows: Sequence[Mapping[str, Any]]) -> CheckResult:
    bad_date: List[int] = []
    bad_side: List[Dict[str, Any]] = []
    no_desc: List[int] = []
    bad_balance = 0
    for i, r in enumerate(rows):
        if parse_date(r.get("date")) is None:
            bad_date.append(i)
        side = _side(r)
        if side in ("both", "none"):
            bad_side.append({"row": i, "side": side})
        if not str(r.get("description") or "").strip():
            no_desc.append(i)
        if r.get("balance") not in (None, "") and to_paise(r.get("balance")) is None:
            bad_balance += 1
    problems = len(bad_date) + len(bad_side) + len(no_desc) + bad_balance
    return CheckResult(
        SCHEMA_CHECK,
        "pass" if problems == 0 else "fail",
        {
            "unparseable_dates": len(bad_date),
            "rows_with_both_or_no_amount": len(bad_side),
            "empty_descriptions": len(no_desc),
            "non_numeric_balances": bad_balance,
            "examples": {
                "date_rows": bad_date[:MAX_EXAMPLES],
                "side_rows": bad_side[:MAX_EXAMPLES],
                # What are the rows without exactly one amount? (opening-balance line, wrapped text, zero-amount fee ...)
                "side_row_samples": [
                    {
                        "row": x["row"],
                        "date": str(rows[x["row"]].get("date")),
                        "description": str(rows[x["row"]].get("description") or "")[:60],
                        "debit": rows[x["row"]].get("debit"),
                        "credit": rows[x["row"]].get("credit"),
                        "balance": rows[x["row"]].get("balance"),
                    }
                    for x in bad_side[:MAX_EXAMPLES]
                ],
            },
        },
    )


def check_header_period(
    rows: Sequence[Mapping[str, Any]], header_period: Optional[HeaderPeriod]
) -> CheckResult:
    if not header_period:
        return CheckResult(HEADER_PERIOD_CHECK, "skip", {"reason": "no header period available"})
    start, end = parse_date(header_period[0]), parse_date(header_period[1])
    if start is None and end is None:
        return CheckResult(
            HEADER_PERIOD_CHECK,
            "skip",
            {"reason": "header period could not be parsed", "header_period": [str(header_period[0]), str(header_period[1])]},
        )
    dates = [d for d in (parse_date(r.get("date")) for r in rows) if d is not None]
    if not dates:
        return CheckResult(HEADER_PERIOD_CHECK, "skip", {"reason": "no parseable transaction dates"})
    outside = [
        d for d in dates if (start is not None and d < start) or (end is not None and d > end)
    ]
    return CheckResult(
        HEADER_PERIOD_CHECK,
        "pass" if not outside else "fail",
        {
            "header_from": start.isoformat() if start else None,
            "header_to": end.isoformat() if end else None,
            "first_txn_date": min(dates).isoformat(),
            "last_txn_date": max(dates).isoformat(),
            "rows_outside_period": len(outside),
        },
    )


# ── explanation ────────────────────────────────────────────────────────────
def explain(by_name: Mapping[str, CheckResult], state: str) -> Tuple[List[str], List[str], Optional[str]]:
    """Machine-readable reasons for a non-VERIFIED state, plus a coarse failure class.

    reasons: why the state is not VERIFIED (a missing check is a reason only if it kept the
             state from being VERIFIED; it is never a failure by itself).
    notes:   evidence that was unavailable but did not decide the state on its own.
    class:   ROWS_SUSPECT            the extracted rows themselves look wrong
             REFERENCE_MISMATCH_ONLY rows are internally consistent (balance chain intact) but a
                                     declared/printed figure disagrees: either rows were lost at the
                                     ends or the figure was mis-extracted; needs a human or a
                                     per-bank fix, and v1 does not guess which
             DATA_QUALITY            only descriptions/dates/period look off
             INSUFFICIENT_EVIDENCE   no running balance to verify against
    """
    reasons: List[str] = []
    notes: List[str] = []

    sc, bc, oc, pt, dp, hp = (
        by_name[SCHEMA_CHECK],
        by_name[BALANCE_CHECK],
        by_name[OPENING_CLOSING_CHECK],
        by_name[PRINTED_TOTALS_CHECK],
        by_name[DUPLICATE_CHECK],
        by_name[HEADER_PERIOD_CHECK],
    )
    rows_suspect = False
    reference_only = False
    quality_only = False

    if sc.status == "fail":
        d = sc.detail
        if d.get("unparseable_dates"):
            reasons.append("schema_unparseable_dates")
            rows_suspect = True
        if d.get("rows_with_both_or_no_amount"):
            reasons.append("schema_rows_without_single_amount")
            rows_suspect = True
        if d.get("empty_descriptions"):
            reasons.append("schema_empty_descriptions")
            quality_only = True
        if d.get("non_numeric_balances"):
            reasons.append("schema_non_numeric_balance")
            rows_suspect = True
    if bc.status == "fail":
        reasons.append("balance_chain_broken")
        rows_suspect = True
    elif bc.status == "skip":
        reasons.append("no_running_balance")
    if oc.status == "fail":
        reasons.append("opening_closing_mismatch")
        d = oc.detail
        if d.get("declared_closing_matches_last_row") is False:
            reasons.append("declared_closing_differs_from_last_row_balance")
        if d.get("declared_opening_matches_chain") is False:
            reasons.append("declared_opening_differs_from_chain_opening")
        reference_only = True
    elif oc.status == "skip":
        notes.append("opening_or_closing_unavailable")
    if pt.status == "fail":
        for k in pt.detail.get("differences", {}):
            reasons.append(f"printed_{k}_mismatch")
        reference_only = True
    elif pt.status == "skip":
        notes.append("printed_totals_unavailable")
    if dp.status == "fail":
        reasons.append("duplicate_rows")
        rows_suspect = True
    if hp.status == "fail":
        reasons.append("rows_outside_header_period")
        quality_only = True
    elif hp.status == "skip":
        notes.append("header_period_unavailable")

    if state == "VERIFIED":
        return [], notes, None
    if bc.status == "skip":
        cls: Optional[str] = "ROWS_SUSPECT" if rows_suspect else "INSUFFICIENT_EVIDENCE"
    elif rows_suspect:
        cls = "ROWS_SUSPECT"
    elif reference_only:
        cls = "REFERENCE_MISMATCH_ONLY"
    elif quality_only:
        cls = "DATA_QUALITY"
    else:
        cls = None
    return reasons, notes, cls


# ── public API ─────────────────────────────────────────────────────────────
def verify(
    raw_rows: Sequence[Mapping[str, Any]],
    *,
    opening: Optional[float] = None,
    closing: Optional[float] = None,
    printed: Optional[PrintedTotals] = None,
    header_period: Optional[HeaderPeriod] = None,
    repair_stats: Optional[Mapping[str, int]] = None,
    validated_count: Optional[int] = None,
) -> VerificationReport:
    """Run all v1 checks on raw parser rows. Never mutates `raw_rows`."""
    rows = list(raw_rows)
    checks = [
        check_schema(rows),
        check_balance(rows, opening),
        check_opening_closing(rows, opening, closing),
        check_printed_totals(rows, printed),
        check_duplicates(rows),
        check_header_period(rows, header_period),
    ]
    by_name = {c.name: c for c in checks}

    if any(by_name[n].status == "fail" for n in HARD_CHECKS):
        state = "FAILED"
    elif any(c.status == "fail" for c in checks) or by_name[BALANCE_CHECK].status != "pass":
        state = "REVIEW"
    else:
        state = "VERIFIED"

    reasons, notes, failure_class = explain(by_name, state)

    return VerificationReport(
        state=state,  # type: ignore[arg-type]
        checks=checks,
        reasons=reasons,
        notes=notes,
        failure_class=failure_class,
        raw_transaction_count=len(rows),
        raw_debit_count=sum(1 for r in rows if _amount(r, "debit")),
        raw_credit_count=sum(1 for r in rows if _amount(r, "credit")),
        raw_total_debits=sum(_amount(r, "debit") for r in rows) / 100,
        raw_total_credits=sum(_amount(r, "credit") for r in rows) / 100,
        repairs=dict(repair_stats or {}),
        validated_transaction_count=validated_count,
    )


# ── adapters for the existing pipeline objects ─────────────────────────────
def printed_from_metadata(meta: Any) -> Optional[PrintedTotals]:
    """Read printed counts/totals from a bank's StatementMetadata (attrs vary by bank)."""
    if meta is None:
        return None
    pt = PrintedTotals(
        debit_count=getattr(meta, "dr_count", None),
        credit_count=getattr(meta, "cr_count", None),
        total_debits=getattr(meta, "total_debits", None),
        total_credits=getattr(meta, "total_credits", None),
    )
    return None if pt.is_empty() else pt


def header_period_from_metadata(meta: Any) -> Optional[HeaderPeriod]:
    if meta is None:
        return None
    a, b = getattr(meta, "statement_from", None), getattr(meta, "statement_to", None)
    return (a, b) if (a or b) else None


def verify_from_pipeline(
    raw_transactions: Sequence[Any],
    *,
    structure_metadata: Any,
    opening: Optional[float],
    closing: Optional[float],
    validated_count: Optional[int] = None,
) -> VerificationReport:
    """Convenience for BaseBankProcessor: accepts parser txn objects or dicts."""
    rows = [t.to_dict() if hasattr(t, "to_dict") else dict(t) for t in raw_transactions]
    return verify(
        rows,
        opening=opening,
        closing=closing,
        printed=printed_from_metadata(structure_metadata),
        header_period=header_period_from_metadata(structure_metadata),
        validated_count=validated_count,
    )
