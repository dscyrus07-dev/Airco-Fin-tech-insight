"""Independent checks C1-C5 plus schema and period. All Decimal, zero tolerance.

C1 chain       prev balance + credit - debit == balance, for every row after the first
C2 side        classifies C1 failures: pure side flip (|delta| == amount) vs amount error
C3 reference   printed opening/closing vs values derived from rows
C4 totals      printed Dr/Cr counts and sums vs derived, with the reversal rule (negative printed amounts)
C5 dates       transaction dates non-decreasing
period         rows outside the printed From/To (bidirectional; <= 1 day is informational)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .normalize import NormalizedRow
from .summary import PrintedSummary

PASS, FAIL, WARN, INFO, SKIPPED = "pass", "fail", "warn", "info", "skipped"
VERIFIED, REVIEW, FAILED = "VERIFIED", "REVIEW", "FAILED"
_PERIOD_TOLERANCE_DAYS = 1
_ZERO = Decimal("0")


@dataclass
class CheckResult:
    name: str
    status: str
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Checks:
    results: Dict[str, CheckResult]
    verdict: str
    reasons: List[str]
    derived: Dict[str, Any]


def derive(rows: Sequence[NormalizedRow]) -> Dict[str, Any]:
    if not rows:
        return {"opening": None, "closing": None, "debit_rows": 0, "credit_rows": 0, "sum_debits": _ZERO, "sum_credits": _ZERO}
    first = rows[0].txn
    opening = first.balance - (first.credit or _ZERO) + (first.debit or _ZERO)
    return {
        "opening": opening,
        "closing": rows[-1].txn.balance,
        "debit_rows": sum(1 for r in rows if r.txn.debit is not None),
        "credit_rows": sum(1 for r in rows if r.txn.credit is not None),
        "sum_debits": sum((r.txn.debit or _ZERO for r in rows), _ZERO),
        "sum_credits": sum((r.txn.credit or _ZERO for r in rows), _ZERO),
    }


def check_chain(rows: Sequence[NormalizedRow]) -> Tuple[CheckResult, CheckResult]:
    bad: List[int] = []
    side_flips: List[int] = []
    amount_errors: List[int] = []
    for i in range(1, len(rows)):
        prev, cur = rows[i - 1].txn, rows[i].txn
        delta = cur.balance - prev.balance
        signed = (cur.credit or _ZERO) - (cur.debit or _ZERO)
        if delta != signed:
            bad.append(i)
            (side_flips if abs(delta) == abs(signed) else amount_errors).append(i)
    c1 = CheckResult("chain", FAIL if bad else PASS, {"rows_checked": max(len(rows) - 1, 0), "breaks": len(bad), "examples": bad[:5]})
    c2 = CheckResult("side", FAIL if bad else PASS, {"side_flips": len(side_flips), "amount_errors": len(amount_errors), "examples": (side_flips + amount_errors)[:5]})
    return c1, c2


def check_reference(derived: Dict[str, Any], summary: Optional[PrintedSummary]) -> CheckResult:
    if summary is None:
        return CheckResult("reference", SKIPPED, {"reason": "no parseable printed summary"})
    open_ok = derived["opening"] == summary.opening
    close_ok = derived["closing"] == summary.closing
    return CheckResult("reference", PASS if (open_ok and close_ok) else FAIL, {
        "opening_matches": open_ok, "closing_matches": close_ok,
        "derived_opening": str(derived["opening"]), "printed_opening": str(summary.opening),
        "derived_closing": str(derived["closing"]), "printed_closing": str(summary.closing),
    })


def check_totals(rows: Sequence[NormalizedRow], derived: Dict[str, Any], summary: Optional[PrintedSummary]) -> CheckResult:
    if summary is None:
        return CheckResult("totals", SKIPPED, {"reason": "no parseable printed summary"})
    nw = sum(1 for r in rows if r.reversal and r.printed_side == "withdrawal")
    nd = sum(1 for r in rows if r.reversal and r.printed_side == "deposit")
    sw = sum((abs(r.txn.credit or _ZERO) for r in rows if r.reversal and r.printed_side == "withdrawal"), _ZERO)
    sd = sum((abs(r.txn.debit or _ZERO) for r in rows if r.reversal and r.printed_side == "deposit"), _ZERO)
    raw = (summary.dr_count == derived["debit_rows"] and summary.cr_count == derived["credit_rows"]
           and summary.debits == derived["sum_debits"] and summary.credits == derived["sum_credits"])
    adjusted = (summary.dr_count == derived["debit_rows"] + nw - nd and summary.cr_count == derived["credit_rows"] - nw + nd
                and summary.debits == derived["sum_debits"] - sw - sd and summary.credits == derived["sum_credits"] - sw - sd)
    d_dr = summary.dr_count - derived["debit_rows"]
    d_cr = summary.cr_count - derived["credit_rows"]
    d_deb = summary.debits - derived["sum_debits"]
    d_crd = summary.credits - derived["sum_credits"]
    detail: Dict[str, Any] = {"reversal_rows": {"withdrawal": nw, "deposit": nd}, "delta": {"dr": d_dr, "cr": d_cr, "debits": str(d_deb), "credits": str(d_crd)}}
    if raw:
        return CheckResult("totals", PASS, {**detail, "outcome": "MATCH"})
    if adjusted:
        return CheckResult("totals", PASS, {**detail, "outcome": "RECONCILED_VIA_REVERSALS"})
    if d_dr == -d_cr and d_deb == d_crd and (d_dr != 0 or d_deb != 0):
        return CheckResult("totals", WARN, {**detail, "outcome": "REVERSAL_SIGNATURE_ONLY"})
    return CheckResult("totals", FAIL, {**detail, "outcome": "MISMATCH"})


def check_dates(rows: Sequence[NormalizedRow]) -> CheckResult:
    backwards = [i for i in range(1, len(rows)) if rows[i].txn.date < rows[i - 1].txn.date]
    return CheckResult("dates", WARN if backwards else PASS, {"decreasing_at": backwards[:5], "count": len(backwards)})


def _d(text: str) -> date:
    return datetime.strptime(text, "%d/%m/%Y").date()


def check_period(rows: Sequence[NormalizedRow], period: Optional[Tuple[str, str]]) -> CheckResult:
    if period is None or not rows:
        return CheckResult("period", SKIPPED, {"reason": "no printed period or no rows"})
    try:
        start, end = _d(period[0]), _d(period[1])
    except ValueError:
        return CheckResult("period", WARN, {"reason": "unparseable printed period", "printed": list(period)})
    first = date.fromisoformat(rows[0].txn.date)
    last = date.fromisoformat(rows[-1].txn.date)
    before = [(start - date.fromisoformat(r.txn.date)).days for r in rows if date.fromisoformat(r.txn.date) < start]
    after = [(date.fromisoformat(r.txn.date) - end).days for r in rows if date.fromisoformat(r.txn.date) > end]
    worst = max(before + after, default=0)
    status = PASS if not (before or after) else (INFO if worst <= _PERIOD_TOLERANCE_DAYS else WARN)
    return CheckResult("period", status, {
        "rows_before_from": len(before), "rows_after_to": len(after), "max_days_outside": worst,
        "first_row": first.isoformat(), "last_row": last.isoformat(), "printed": list(period),
    })


def decide(results: Dict[str, CheckResult], schema_errors: Sequence[str], warnings: Sequence[str], has_rows: bool) -> Tuple[str, List[str]]:
    reasons: List[str] = []
    if schema_errors:
        reasons.append(f"schema errors: {len(schema_errors)}")
    for name in ("chain", "side", "reference"):
        if results[name].status == FAIL:
            reasons.append(f"{name} failed")
    if results["totals"].status == FAIL:
        reasons.append("totals mismatch")
    if reasons:
        return FAILED, reasons
    if results["reference"].status == SKIPPED and has_rows:
        reasons.append("no printed summary to verify against")
    if results["totals"].status == WARN:
        reasons.append("printed counts/sums differ with reversal signature but no proof")
    if results["dates"].status == WARN:
        reasons.append("dates not monotonic")
    if results["period"].status == WARN:
        reasons.append("rows more than 1 day outside printed period")
    if warnings:
        reasons.append(f"extraction warnings: {len(warnings)}")
    return (REVIEW if reasons else VERIFIED), reasons


def run_checks(rows: Sequence[NormalizedRow], period: Optional[Tuple[str, str]], summary: Optional[PrintedSummary],
               schema_errors: Sequence[str], warnings: Sequence[str]) -> Checks:
    derived = derive(rows)
    c1, c2 = check_chain(rows)
    results = {
        "schema": CheckResult("schema", FAIL if schema_errors else PASS, {"errors": list(schema_errors)[:5], "count": len(schema_errors)}),
        "chain": c1,
        "side": c2,
        "reference": check_reference(derived, summary) if rows else CheckResult("reference", SKIPPED, {"reason": "no rows"}),
        "totals": check_totals(rows, derived, summary) if rows else CheckResult("totals", SKIPPED, {"reason": "no rows"}),
        "dates": check_dates(rows),
        "period": check_period(rows, period),
    }
    verdict, reasons = decide(results, schema_errors, warnings, bool(rows))
    return Checks(results=results, verdict=verdict, reasons=reasons, derived=derived)
