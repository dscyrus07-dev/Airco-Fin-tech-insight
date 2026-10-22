"""Pure scoring for the OCR evaluation (no backend imports; plain dict rows).

A row is {"date": "YYYY-MM-DD", "debit": str|None, "credit": str|None, "balance": str}.
Ground truth rows have unique dates (the synthetic corpus guarantees it), so pairing is by date.

Definitions (these back the release gates in docs/ocr/UNIVERSAL_OCR_PHASE1.md Part F; thresholds live in GATES
and are never changed silently):
  amounts_total   non-null ground-truth debit + credit + balance values
  amounts_exact   of those, values read back identical on the paired row (a missing row counts as wrong)
  side_flips      a ground-truth debit read as a credit of the same amount, or the reverse
  invented        extracted rows whose date matches no ground-truth row
  missing_rows    ground-truth rows with no extracted row
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, List, Optional

GATES = {
    "exact_amount_rate_min": 0.995,
    "side_flip_rate_max": 0.001,
    "invented_in_chain_passing_max": 0,
    "chain_and_reference_pass_rate_min": 0.80,   # evaluated on the 200-dpi synthetic category only
    "p95_seconds_per_page_max": 4.0,
}


def _d(v: Any) -> Optional[Decimal]:
    if v is None or v == "":
        return None
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError):
        return None


def _eq(a: Any, b: Any) -> bool:
    x, y = _d(a), _d(b)
    if x in (None, Decimal(0)) and y in (None, Decimal(0)):
        return True
    return x is not None and y is not None and x == y


def score_statement(gt: List[Dict], ext: List[Dict]) -> Dict[str, int]:
    by_date: Dict[str, List[int]] = {}
    for i, r in enumerate(gt):
        by_date.setdefault(r["date"], []).append(i)
    claimed = set()
    out = dict(gt_rows=len(gt), ext_rows=len(ext), amounts_total=0, amounts_exact=0, side_flips=0,
               invented=0, missing_rows=0)
    for r in gt:
        out["amounts_total"] += sum(1 for k in ("debit", "credit") if _d(r.get(k)) not in (None, Decimal(0)))
        out["amounts_total"] += 1                                   # balance
    for e in ext:
        cands = [i for i in by_date.get(e["date"], []) if i not in claimed]
        if not cands:
            out["invented"] += 1
            continue
        i = cands[0]
        claimed.add(i)
        g = gt[i]
        for k, other in (("debit", "credit"), ("credit", "debit")):
            gv = _d(g.get(k))
            if gv in (None, Decimal(0)):
                continue
            if _eq(e.get(k), gv):
                out["amounts_exact"] += 1
            elif _eq(e.get(other), gv) and not _eq(e.get(k), gv):
                out["side_flips"] += 1
        if _eq(e.get("balance"), g.get("balance")):
            out["amounts_exact"] += 1
    out["missing_rows"] = len(gt) - len(claimed)
    return out


def percentile(values: Iterable[float], p: float) -> Optional[float]:
    v = sorted(values)
    if not v:
        return None
    k = (len(v) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


def aggregate(items: List[Dict]) -> Dict[str, Any]:
    """items: per-statement dicts = score_statement fields + chain_pass, reference_pass, served (bool),
    verdict, page_seconds (list), failed_pages (int)."""
    n = len(items)
    tot = sum(i["amounts_total"] for i in items)
    ex = sum(i["amounts_exact"] for i in items)
    flips = sum(i["side_flips"] for i in items)
    served = [i for i in items if i.get("served")]
    chain_ok = [i for i in items if i.get("chain_pass")]
    both = [i for i in items if i.get("chain_pass") and i.get("reference_pass")]
    secs = [s for i in items for s in i.get("page_seconds", [])]
    return {
        "statements": n,
        "served": len(served),
        "amounts_total": tot,
        "exact_amount_rate": (ex / tot) if tot else None,
        "side_flip_rate": (flips / tot) if tot else None,
        "side_flips": flips,
        "invented_rows_total": sum(i["invented"] for i in items),
        "invented_in_chain_passing": sum(i["invented"] for i in chain_ok),
        "missing_rows_total": sum(i["missing_rows"] for i in items),
        "chain_pass_rate": (len(chain_ok) / n) if n else None,
        "chain_and_reference_pass_rate": (len(both) / n) if n else None,
        "failed_pages": sum(i.get("failed_pages", 0) for i in items),
        "pages_timed": len(secs),
        "seconds_per_page_p50": percentile(secs, 0.5),
        "seconds_per_page_p95": percentile(secs, 0.95),
        "never_verified": all(i.get("verdict") != "VERIFIED" for i in items),
    }


def gate_report(agg: Dict[str, Any], is_reference_category: bool) -> Dict[str, Dict[str, Any]]:
    """PASS/FAIL per gate for one category. A gate with no data is NO_DATA, never PASS."""
    def g(name, value, ok):
        return {"value": value, "threshold": GATES[name], "result": "NO_DATA" if value is None else ("PASS" if ok else "FAIL")}
    r = {
        "exact_amounts": g("exact_amount_rate_min", agg["exact_amount_rate"],
                           (agg["exact_amount_rate"] or 0) >= GATES["exact_amount_rate_min"]),
        "side_flips": g("side_flip_rate_max", agg["side_flip_rate"],
                        (agg["side_flip_rate"] if agg["side_flip_rate"] is not None else 1) <= GATES["side_flip_rate_max"]),
        "invented_in_chain_passing": g("invented_in_chain_passing_max", agg["invented_in_chain_passing"],
                                       agg["invented_in_chain_passing"] <= GATES["invented_in_chain_passing_max"]),
        "p95_seconds_per_page": g("p95_seconds_per_page_max", agg["seconds_per_page_p95"],
                                  (agg["seconds_per_page_p95"] or 1e9) <= GATES["p95_seconds_per_page_max"]),
    }
    if is_reference_category:
        r["chain_and_reference_pass_rate"] = g("chain_and_reference_pass_rate_min", agg["chain_and_reference_pass_rate"],
                                               (agg["chain_and_reference_pass_rate"] or 0) >= GATES["chain_and_reference_pass_rate_min"])
    return r
