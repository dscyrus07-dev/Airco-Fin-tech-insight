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
    # sparse-print layouts leave balance=None on some rows: the derived opening is the first printed balance minus
    # every flow up to and including that row; the derived closing is the last printed balance plus every flow after it.
    opening = closing = None
    pre = _ZERO          # flows before the first printed balance (excluding that row's own flow)
    post = _ZERO         # flows after the last printed balance
    for i, r in enumerate(rows):
        if i > 0 and getattr(r, 'segment', 0) != getattr(rows[i - 1], 'segment', 0):
            pre, post = _ZERO, _ZERO   # a new segment restarts its own balance derivation
        t = r.txn
        signed = (t.credit or _ZERO) - (t.debit or _ZERO)
        if t.balance is None:
            if opening is None:
                pre += signed
            else:
                post += signed
            continue
        if opening is None:
            opening = t.balance - signed - pre
        closing = t.balance
        post = _ZERO
    if closing is not None:
        closing += post
    return {
        "opening": opening,
        "closing": closing if closing is not None else rows[-1].txn.balance,
        "debit_rows": sum(1 for r in rows if r.txn.debit is not None),
        "credit_rows": sum(1 for r in rows if r.txn.credit is not None),
        "sum_debits": sum((r.txn.debit or _ZERO for r in rows), _ZERO),
        "sum_credits": sum((r.txn.credit or _ZERO for r in rows), _ZERO),
    }


def _same_date_repair(rows: Sequence[NormalizedRow], bad: Sequence[int]) -> List[int]:
    """Window starts where a break is honestly explained by the bank printing same-date rows out of balance
    order. Walks the segment once, keeping an effective running balance; inside a maximal same-date window a
    depth-first search over rows (each step must satisfy balance - cur == signed flow) finds the forced chain
    order and yields the corrected exit balance. Returns [] when any break is left unexplained."""
    bad_set = set(bad)
    explained: List[int] = []
    ok = True
    n = len(rows)
    i = 0
    cur = None                           # effective running balance in print order with windows repaired
    carried = _ZERO
    prev_seg = None
    budget = [40000]
    while i < n:
        if getattr(rows[i], 'segment', 0) != prev_seg:
            cur, carried = None, _ZERO   # a new account segment restarts the running balance
            prev_seg = getattr(rows[i], 'segment', 0)
        j = i + 1
        while j < n and getattr(rows[j], 'segment', 0) == getattr(rows[i], 'segment', 0)                 and rows[j].txn.date == rows[i].txn.date:
            j += 1
        if j - i <= 1 or any(rows[k].txn.balance is None for k in range(i, j)):
            for k in range(i, j):        # single row or unprovable window: plain chain step
                t = rows[k].txn
                if t.balance is None:
                    carried += (t.credit or _ZERO) - (t.debit or _ZERO)
                    continue
                if cur is not None and t.balance - cur != carried + (t.credit or _ZERO) - (t.debit or _ZERO):
                    if k in bad_set:
                        ok = False
                cur, carried = t.balance, _ZERO
            i = j
            continue
        if cur is None:                  # no provable base: only breaks inside this window stay unexplained
            if any(i <= b < j for b in bad_set):
                ok = False
            cur = rows[j - 1].txn.balance
            i = j
            continue
        flows = {k: (rows[k].txn.credit or _ZERO) - (rows[k].txn.debit or _ZERO) for k in range(i, j)}
        memo: set = set()
        end_bal = [None]

        def dfs(c, remaining):
            if not remaining:
                end_bal[0] = c
                return True
            budget[0] -= 1
            if budget[0] <= 0:
                return False
            key = (c, remaining)
            if key in memo:
                return False
            for k in remaining:
                if rows[k].txn.balance - c == flows[k] and dfs(rows[k].txn.balance, remaining - {k}):
                    return True
            memo.add(key)
            return False

        if dfs(cur, frozenset(range(i, j))):
            explained.append(i)
            cur = end_bal[0]
        else:
            cur = rows[j - 1].txn.balance
            if any(i <= b < j for b in bad_set):
                ok = False
        carried = _ZERO
        i = j
    return explained if ok else []


def check_chain(rows: Sequence[NormalizedRow], side_flip_policy: str = "fail",
                reorder_same_date: bool = False) -> Tuple[CheckResult, CheckResult]:
    bad: List[int] = []
    bad_segments: List[int] = []
    side_flips: List[int] = []
    amount_errors: List[int] = []
    last_bal: Optional[int] = None            # index of the previous balance-bearing row in this segment
    carried = _ZERO                            # signed flow accumulated since that row
    for i, r in enumerate(rows):
        cur = r.txn
        if i > 0 and getattr(rows[i], 'segment', 0) != getattr(rows[i - 1], 'segment', 0):
            last_bal, carried = None, _ZERO   # a new account segment restarts the running balance
        if cur.balance is None:
            carried += (cur.credit or _ZERO) - (cur.debit or _ZERO)
            continue
        if last_bal is not None:
            delta = cur.balance - rows[last_bal].txn.balance
            signed = carried + (cur.credit or _ZERO) - (cur.debit or _ZERO)
            if delta != signed:
                bad.append(i)
                if getattr(rows[i], 'segment', 0) not in bad_segments:
                    bad_segments.append(getattr(rows[i], 'segment', 0))
                (side_flips if abs(delta) == abs(signed) else amount_errors).append(i)
        last_bal, carried = i, _ZERO
    flips_only = bool(bad) and not amount_errors and side_flip_policy == "review"
    disordered: List[int] = []
    if bad and reorder_same_date:
        # a bank that prints same-date rows out of balance order trips the chain without any row being wrong:
        # downgrade only when every break is provably explained by a reorderable same-date window
        disordered = _same_date_repair(rows, bad)
        flips_only = flips_only or bool(disordered)
    c1 = CheckResult("chain", (WARN if flips_only else FAIL) if bad else PASS,
                     {"rows_checked": max(len(rows) - 1, 0), "breaks": len(bad), "examples": bad[:5],
                      **({"same_date_disorder": disordered} if disordered else {}),
                      **({"segments": bad_segments} if bad_segments else {})})
    c2 = CheckResult("side", (WARN if flips_only else FAIL) if bad else PASS, {"side_flips": len(side_flips), "amount_errors": len(amount_errors), "examples": (side_flips + amount_errors)[:5]})
    return c1, c2


def check_segments(rows: Sequence[NormalizedRow], segment_counts: Optional[Dict[int, int]],
                   side_counts: Optional[Dict[int, Tuple[int, int]]] = None) -> CheckResult:
    """Per-account segments: compare each printed transaction count with the rows read in that segment.
    A line that prints two counts is compared per side (debit count, credit count)."""
    if not segment_counts and not side_counts:
        return CheckResult("segments", SKIPPED, {"reason": "no segment counts printed"})
    segs = sorted(set(segment_counts or {}) | set(side_counts or {}))
    mismatched: List[int] = []
    for s in segs:
        seg_rows = [r for r in rows if getattr(r, 'segment', 0) == s]
        if segment_counts and s in segment_counts and segment_counts[s] != len(seg_rows):
            mismatched.append(s)
            continue
        if side_counts and s in side_counts:
            dr, cr = side_counts[s]
            if dr != sum(1 for r in seg_rows if r.txn.debit is not None) \
                    or cr != sum(1 for r in seg_rows if r.txn.credit is not None):
                mismatched.append(s)
    return CheckResult("segments", WARN if mismatched else PASS, {
        "segments": segs,
        "printed": {s: segment_counts[s] for s in (segment_counts or {}) if s in segs},
        "side_printed": {s: list(side_counts[s]) for s in (side_counts or {}) if s in segs},
        "read": {s: sum(1 for r in rows if getattr(r, 'segment', 0) == s) for s in segs},
        "mismatched": mismatched,
    })


def check_checkpoints(rows: Sequence[NormalizedRow], checkpoints: Sequence[Tuple[int, Decimal]]) -> CheckResult:
    """Printed `balance carried/brought forward`-style assertions between rows.

    With per-row balances a checkpoint at row boundary k must equal the running balance after k rows (k = 0 is the
    derived opening). A checkpoint tagged "pre" (a segment's printed `Opening Balance`) instead asserts the
    opening implied by the segment's first row. Without a balance column the only honest check is the delta: the
    gap between two checkpoints must equal credits minus debits over the rows between them."""
    if not checkpoints:
        return CheckResult("checkpoints", SKIPPED, {"reason": "no printed balance checkpoints"})
    bad: List[Dict[str, Any]] = []
    verified = 0
    at_pos: Dict[Tuple[int, str], set] = {}
    for tup in checkpoints:
        at_pos.setdefault((tup[0], tup[2] if len(tup) > 2 else ""), set()).add(tup[1])
    for (k, tag), vals in at_pos.items():               # a carried-forward and the brought-forward at the same
        if len(vals) > 1:                               # boundary are two prints of one value: they must agree
            bad.append({"after_row": k, "conflicting_prints": [str(v) for v in sorted(vals)]})
    have_bal = rows and rows[0].txn.balance is not None
    if have_bal:
        for tup in checkpoints:
            k, printed = tup[0], tup[1]
            tag = tup[2] if len(tup) > 2 else ""
            if tag == "pre" or k == 0:
                # printed opening: derived from the next row's balance minus its own signed flow
                expected = None
                if k < len(rows):
                    expected = rows[k].txn.balance - (rows[k].txn.credit or _ZERO) + (rows[k].txn.debit or _ZERO)
            else:
                expected = rows[k - 1].txn.balance if 0 < k <= len(rows) else None
            if expected is None:
                continue
            if expected == printed:
                verified += 1
            else:
                bad.append({"after_row": k, "printed": str(printed), "derived": str(expected)})
    else:
        pts = [(t[0], t[1]) for t in checkpoints if 0 <= t[0] <= len(rows)]
        for (ka, va), (kb, vb) in zip(pts, pts[1:]):
            if kb <= ka:
                continue
            net = sum(((r.txn.credit or _ZERO) - (r.txn.debit or _ZERO) for r in rows[ka:kb]), _ZERO)
            if vb - va == net:
                verified += 1
            else:
                bad.append({"rows": [ka, kb], "printed_delta": str(vb - va), "derived_delta": str(net)})
    return CheckResult("checkpoints", FAIL if bad else PASS,
                       {"checkpoints": len(checkpoints), "verified": verified, "mismatched": bad[:5]})


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


def check_delta(derived: Dict[str, Any], summary: Optional[PrintedSummary]) -> CheckResult:
    """Balance-free analogue of the reference check: when no per-row balances print, the printed opening+closing pair
    still pins the net movement: closing - opening must equal printed-derived sum(credits) - sum(debits)."""
    if summary is None or summary.opening is None or summary.closing is None:
        return CheckResult("balance_delta", SKIPPED, {"reason": "summary prints no opening+closing pair"})
    net = derived["sum_credits"] - derived["sum_debits"]
    ok = summary.closing - summary.opening == net
    return CheckResult("balance_delta", PASS if ok else FAIL, {
        "printed_delta": str(summary.closing - summary.opening), "derived_delta": str(net)})


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
    backwards = [i for i in range(1, len(rows))
                 if getattr(rows[i], 'segment', 0) == getattr(rows[i - 1], 'segment', 0) and rows[i].txn.date < rows[i - 1].txn.date]
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
    same_seg = lambda a, b: getattr(rows[a], 'segment', 0) == getattr(rows[b], 'segment', 0)    # noqa: E731  date distance across account segments is meaningless
    out = []
    for i in range(n):
        if i == 0:
            isolated = same_seg(0, 1) and far(ds[0], ds[1]) and not far(ds[1], ds[2]) and same_seg(1, 2)
        elif i == n - 1:
            isolated = same_seg(i, i - 1) and far(ds[i], ds[i - 1]) and not far(ds[i - 1], ds[i - 2]) and same_seg(i - 1, i - 2)
        else:
            isolated = (same_seg(i, i - 1) and same_seg(i, i + 1)
                        and far(ds[i], ds[i - 1]) and far(ds[i], ds[i + 1]) and not far(ds[i - 1], ds[i + 1]))
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
           summary_expected: bool = True, no_running_balance: bool = False) -> Tuple[str, List[str]]:
    reasons: List[str] = []
    if schema_errors:
        reasons.append(f"schema errors: {len(schema_errors)}")
    for name in ("chain", "side", "reference", "checkpoints", "balance_delta"):
        if results.get(name) is not None and results[name].status == FAIL:
            seg = results[name].detail.get("segments")
            reasons.append(f"{name} failed" + (f" in segments {seg}" if seg else ""))
    if results["totals"].status == FAIL:
        reasons.append("totals mismatch")
    hard_fail = bool(reasons)
    anchor_conflicts = sorted({w.split(":", 1)[1] for w in warnings if w.startswith("anchor_conflict:")})
    if anchor_conflicts:
        reasons.append(f"conflicting printed anchor values ({', '.join(anchor_conflicts)})")
    if hard_fail:
        return FAILED, reasons
    if results["reference"].status == SKIPPED and has_rows:
        # No independent opening/closing anchor: the chain's opening is derived from row 0 itself, so a corrupted first
        # row shifts the whole chain in lockstep and cannot be detected. Such results are capped at REVIEW, whether or
        # not the layout is expected to print a summary (summary_expected only changes the wording of the reason).
        reasons.append("no printed summary to verify against" if summary_expected
                       else "no independent opening/closing anchor: balance chain is self-derived")
    if results["chain"].status == WARN and results["chain"].detail.get("same_date_disorder"):
        reasons.append("same-date rows print out of balance order (SAME_DATE_DISORDER)")
    elif results["side"].status == WARN:
        reasons.append("printed side disagrees with the balance movement on some rows (possible reversals)")
    if results["totals"].status == WARN:
        reasons.append("printed counts/sums differ with reversal signature but no proof")
    seg_res = results.get("segments")
    if seg_res is not None and seg_res.status == WARN:
        reasons.append(f"segment transaction counts differ (segments {seg_res.detail.get('mismatched')})")
    if no_running_balance and has_rows:
        # The balance chain cannot engage: row-level integrity rests on completeness and printed totals only.
        reasons.append("no running balance column: balance chain cannot engage (NO_RUNNING_BALANCE)")
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
               side_flip_policy: str = "fail", no_running_balance: bool = False,
               reorder_same_date: bool = False,
               segment_counts: Optional[Dict[int, int]] = None,
               segment_side_counts: Optional[Dict[int, Tuple[int, int]]] = None,
               checkpoints: Optional[Sequence[Tuple[int, Decimal]]] = None) -> Checks:
    derived = derive(rows)
    if no_running_balance:
        c1 = CheckResult("chain", SKIPPED, {"reason": "no running balance column"})
        c2 = CheckResult("side", SKIPPED, {"reason": "no running balance column"})
    else:
        c1, c2 = check_chain(rows, side_flip_policy, reorder_same_date)
    results = {
        "schema": CheckResult("schema", FAIL if schema_errors else PASS, {"errors": list(schema_errors)[:5], "count": len(schema_errors)}),
        "chain": c1,
        "side": c2,
        "reference": (CheckResult("reference", SKIPPED, {"reason": "no running balance column: nothing to verify against"})
                      if no_running_balance
                      else check_reference(derived, summary) if rows else CheckResult("reference", SKIPPED, {"reason": "no rows"})),
        "totals": check_totals(rows, derived, summary) if rows else CheckResult("totals", SKIPPED, {"reason": "no rows"}),
        "dates": check_dates(rows, dates_monotonic_expected),
        "period": check_period(rows, period, period_format, period_tolerance_days),
        "date_outliers": check_date_outliers(rows) if rows else CheckResult("date_outliers", SKIPPED, {"reason": "no rows"}),
        "segments": check_segments(rows, segment_counts, segment_side_counts),
        "checkpoints": check_checkpoints(rows, checkpoints or ()),
        "balance_delta": check_delta(derived, summary) if (no_running_balance and rows) else CheckResult("balance_delta", SKIPPED, {"reason": "not a balance-less layout"}),
    }
    verdict, reasons = decide(results, schema_errors, warnings, bool(rows), summary_expected, no_running_balance)
    return Checks(results=results, verdict=verdict, reasons=reasons, derived=derived)
