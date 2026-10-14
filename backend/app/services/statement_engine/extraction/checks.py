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


def check_chain(rows: Sequence[NormalizedRow], side_flip_policy: str = "fail") -> Tuple[CheckResult, CheckResult]:
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
    flips_only = bool(bad) and not amount_errors and side_flip_policy == "review"
    c1 = CheckResult("chain", (WARN if flips_only else FAIL) if bad else PASS, {"rows_checked": max(len(rows) - 1, 0), "breaks": len(bad), "examples": bad[:5]})
    c2 = CheckResult("side", (WARN if flips_only else FAIL) if bad else PASS, {"side_flips": len(side_flips), "amount_errors": len(amount_errors), "examples": (side_flips + amount_errors)[:5]})
    return c1, c2


def check_reference(derived: Dict[str, Any], summary: Optional[PrintedSummary]) -> CheckResult:
    if summary is None:
        return CheckResult("reference", SKIPPED, {"reason": "no parseable printed summary"})
    if summary.opening is None and summary.closing is None:
        return CheckResult("reference", SKIPPED, {"reason": "summary prints neither opening nor closing"})
    open_ok = summary.opening is None or derived["opening"] == summary.opening
    close_ok = summary.closing is None or derived["closing"] == summary.closing
    return CheckResult("reference", PASS if (open_ok and close_ok) else FAIL, {
        "opening_matches": open_ok, "closing_matches": close_ok,
        "derived_opening": str(derived["opening"]), "printed_opening": str(summary.opening),
        "derived_closing": str(derived["closing"]), "printed_closing": str(summary.closing),
    })


def check_totals(rows: Sequence[NormalizedRow], derived: Dict[str, Any], summary: Optional[PrintedSummary]) -> CheckResult:
    if summary is None:
        return CheckResult("totals", SKIPPED, {"reason": "no parseable printed summary"})
    printed = (summary.dr_count, summary.cr_count, summary.debits, summary.credits)
    if all(v is None for v in printed):
        return CheckResult("totals", SKIPPED, {"reason": "summary prints no counts or totals"})
    if any(v is None for v in printed):
        # partial summary: compare the printed fields as they are (no reversal reasoning without all four)
        pairs = [(summary.dr_count, derived["debit_rows"]), (summary.cr_count, derived["credit_rows"]),
                 (summary.debits, derived["sum_debits"]), (summary.credits, derived["sum_credits"])]
        ok = all(a is None or a == b for a, b in pairs)
        return CheckResult("totals", PASS if ok else FAIL, {"outcome": "MATCH" if ok else "MISMATCH", "partial_summary": True})
    nw = sum(1 for r in rows if r.reversal and r.printed_kind == "debit")
    nd = sum(1 for r in rows if r.reversal and r.printed_kind == "credit")
    sw = sum((abs(r.txn.credit or _ZERO) for r in rows if r.reversal and r.printed_kind == "debit"), _ZERO)
    sd = sum((abs(r.txn.debit or _ZERO) for r in rows if r.reversal and r.printed_kind == "credit"), _ZERO)
    raw = (summary.dr_count == derived["debit_rows"] and summary.cr_count == derived["credit_rows"]
           and summary.debits == derived["sum_debits"] and summary.credits == derived["sum_credits"])
    adjusted = (summary.dr_count == derived["debit_rows"] + nw - nd and summary.cr_count == derived["credit_rows"] - nw + nd
                and summary.debits == derived["sum_debits"] - sw - sd and summary.credits == derived["sum_credits"] - sw - sd)
    d_dr = summary.dr_count - derived["debit_rows"]
    d_cr = summary.cr_count - derived["credit_rows"]
    d_deb = summary.debits - derived["sum_debits"]
    d_crd = summary.credits - derived["sum_credits"]
    detail: Dict[str, Any] = {"reversal_rows": {"printed_debit_column": nw, "printed_credit_column": nd}, "delta": {"dr": d_dr, "cr": d_cr, "debits": str(d_deb), "credits": str(d_crd)}}
    if raw:
        return CheckResult("totals", PASS, {**detail, "outcome": "MATCH"})
    if adjusted:
        return CheckResult("totals", PASS, {**detail, "outcome": "RECONCILED_VIA_REVERSALS"})
    if d_dr == -d_cr and d_deb == d_crd and (d_dr != 0 or d_deb != 0):
        return CheckResult("totals", WARN, {**detail, "outcome": "REVERSAL_SIGNATURE_ONLY"})
    return CheckResult("totals", FAIL, {**detail, "outcome": "MISMATCH"})


def check_dates(rows: Sequence[NormalizedRow], monotonic_expected: bool = True) -> CheckResult:
    backwards = [i for i in range(1, len(rows)) if rows[i].txn.date < rows[i - 1].txn.date]
    return CheckResult("dates", (WARN if monotonic_expected else INFO) if backwards else PASS, {"decreasing_at": backwards[:5], "count": len(backwards)})


_OUTLIER_GAP_DAYS = 62


def check_date_outliers(rows: Sequence[NormalizedRow]) -> CheckResult:
    """A row whose date is far from BOTH neighbours while the neighbours are close to each other was dated wrongly (a
    mis-read or shifted date). Needs no printed period, works for any row order, and ignores long quiet spells: a gap
    that separates two clusters of rows is not an isolated row."""
    try:
        ds = [date.fromisoformat(r.txn.date) for r in rows]
    except ValueError:
        return CheckResult("date_outliers", SKIPPED, {"reason": "unparseable row date"})
    n = len(ds)
    if n < 3:
        return CheckResult("date_outliers", SKIPPED, {"reason": "fewer than three rows"})
    far = lambda a, b: abs((a - b).days) > _OUTLIER_GAP_DAYS      # noqa: E731
    out = []
    for i in range(n):
        if i == 0:
            isolated = far(ds[0], ds[1]) and not far(ds[1], ds[2])
        elif i == n - 1:
            isolated = far(ds[i], ds[i - 1]) and not far(ds[i - 1], ds[i - 2])
        else:
            isolated = far(ds[i], ds[i - 1]) and far(ds[i], ds[i + 1]) and not far(ds[i - 1], ds[i + 1])
        if isolated:
            out.append(i)
    return CheckResult("date_outliers", WARN if out else PASS, {"rows": out[:5], "count": len(out)})


def parse_period_date(text: str, period_format: str) -> date:
    """strptime over the format's "|" alternates (same convention as normalize.parse_date)."""
    for fmt in period_format.split("|"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"period date {text!r} matches no format")


def check_period(rows: Sequence[NormalizedRow], period: Optional[Tuple[str, str]], period_format: str = "%d/%m/%Y",
                 tolerance_days: int = _PERIOD_TOLERANCE_DAYS) -> CheckResult:
    if period is None or not rows:
        return CheckResult("period", SKIPPED, {"reason": "no printed period or no rows"})
    try:
        start, end = (parse_period_date(period[i], period_format) for i in (0, 1))
    except ValueError:
        return CheckResult("period", WARN, {"reason": "unparseable printed period", "printed": list(period)})
    first = date.fromisoformat(rows[0].txn.date)
    last = date.fromisoformat(rows[-1].txn.date)
    before = [(start - date.fromisoformat(r.txn.date)).days for r in rows if date.fromisoformat(r.txn.date) < start]
    after = [(date.fromisoformat(r.txn.date) - end).days for r in rows if date.fromisoformat(r.txn.date) > end]
    worst = max(before + after, default=0)
    status = PASS if not (before or after) else (INFO if worst <= tolerance_days else WARN)
    return CheckResult("period", status, {
        "rows_before_from": len(before), "rows_after_to": len(after), "max_days_outside": worst,
        "first_row": first.isoformat(), "last_row": last.isoformat(), "printed": list(period),
    })


def decide(results: Dict[str, CheckResult], schema_errors: Sequence[str], warnings: Sequence[str], has_rows: bool,
           summary_expected: bool = True) -> Tuple[str, List[str]]:
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
        # No independent opening/closing anchor: the chain's opening is derived from row 0 itself, so a corrupted first
        # row shifts the whole chain in lockstep and cannot be detected. Such results are capped at REVIEW, whether or
        # not the layout is expected to print a summary (summary_expected only changes the wording of the reason).
        reasons.append("no printed summary to verify against" if summary_expected
                       else "no independent opening/closing anchor: balance chain is self-derived")
    if results["side"].status == WARN:
        reasons.append("printed side disagrees with the balance movement on some rows (possible reversals)")
    if results["totals"].status == WARN:
        reasons.append("printed counts/sums differ with reversal signature but no proof")
    if results["dates"].status == WARN:
        reasons.append("dates not monotonic")
    if results.get("date_outliers") is not None and results["date_outliers"].status == WARN:
        reasons.append("a row's date is out of line with its neighbouring rows")
    if results["period"].status == WARN:
        reasons.append("rows outside the printed period beyond the layout tolerance")
    if warnings:
        reasons.append(f"extraction warnings: {len(warnings)}")
    return (REVIEW if reasons else VERIFIED), reasons


def run_checks(rows: Sequence[NormalizedRow], period: Optional[Tuple[str, str]], summary: Optional[PrintedSummary],
               schema_errors: Sequence[str], warnings: Sequence[str], period_format: str = "%d/%m/%Y",
               summary_expected: bool = True, dates_monotonic_expected: bool = True, period_tolerance_days: int = _PERIOD_TOLERANCE_DAYS,
               side_flip_policy: str = "fail") -> Checks:
    derived = derive(rows)
    c1, c2 = check_chain(rows, side_flip_policy)
    results = {
        "schema": CheckResult("schema", FAIL if schema_errors else PASS, {"errors": list(schema_errors)[:5], "count": len(schema_errors)}),
        "chain": c1,
        "side": c2,
        "reference": check_reference(derived, summary) if rows else CheckResult("reference", SKIPPED, {"reason": "no rows"}),
        "totals": check_totals(rows, derived, summary) if rows else CheckResult("totals", SKIPPED, {"reason": "no rows"}),
        "dates": check_dates(rows, dates_monotonic_expected),
        "period": check_period(rows, period, period_format, period_tolerance_days),
        "date_outliers": check_date_outliers(rows) if rows else CheckResult("date_outliers", SKIPPED, {"reason": "no rows"}),
    }
    verdict, reasons = decide(results, schema_errors, warnings, bool(rows), summary_expected)
    return Checks(results=results, verdict=verdict, reasons=reasons, derived=derived)
