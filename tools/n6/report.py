"""n6 report: per-bank quadrant table + disagreement classification from
<bank>.h2h.jsonl. PII-free: sha8s and counts only.

Semantics:
- leg "right": legacy parsed, rows>0, independent chain recompute clean,
  row count within tolerance of dated amount-lines, and no failed
  DataIntegrityGuard checks (production runs non-strict, so a failed guard
  check = workbook shipped anyway = customer-facing defect).
- v2 "right": routed to a v2 layout AND verdict VERIFIED AND independent
  chain recompute clean.  (Generic-scan anchor/rows_gt flags on VERIFIED
  files are auditor-precision artifacts — documented separately.)
- serve simulation (decide_serve, if allowlisted): v2 output iff VERIFIED,
  else legacy output.

usage: python tools/n6/report.py <bank_id>...
"""
import json, os, sys
from collections import Counter

here = os.path.dirname(os.path.abspath(__file__))
local = os.path.join(here, ".local")

TOL = 3  # dated-line count tolerance (header/total lines can look dated)


def leg_right(r):
    leg = r.get("leg") or {}
    if leg.get("error") or not (leg.get("rows") or 0):
        return False
    if any("chain_break" in f for f in leg.get("flags") or []):
        return False
    dated = r.get("dated_amt_lines")
    if dated is not None and leg["rows"] > dated + TOL:
        # undated/glued-date families break the heuristic; accept when v2 VERIFIED
        # independently produced the same row count
        v2 = r.get("v2") or {}
        if not (v2.get("verdict") == "VERIFIED" and v2.get("rows") == leg["rows"]):
            return False
    if leg.get("integrity_failed_checks"):
        return False
    return True


def leg_output(r):
    """legacy produced a workbook (non-strict production behaviour)."""
    leg = r.get("leg") or {}
    return not leg.get("error") and (leg.get("rows") or 0) > 0


def v2_right(r):
    v2 = r.get("v2") or {}
    return (v2.get("status") == "v2" and v2.get("verdict") == "VERIFIED"
            and not any("chain_break" in f for f in v2.get("flags") or []))


def v2_served(r):
    """under decide_serve-with-allowlist: v2 output is what ships."""
    v2 = r.get("v2") or {}
    return v2.get("status") == "v2" and v2.get("verdict") == "VERIFIED"


for bank in sys.argv[1:]:
    path = os.path.join(local, f"{bank}.h2h.jsonl")
    if not os.path.exists(path):
        print(f"== {bank}: no data"); continue
    recs = [json.loads(l) for l in open(path)]
    recs = [r for r in recs if "v2" in r]
    n = len(recs)
    qs = Counter()
    leg_defects, v2_worse, v2_bad = [], [], []
    served_better = served_worse = 0
    for r in recs:
        lr, lo, vr, vs = leg_right(r), leg_output(r), v2_right(r), v2_served(r)
        if lr and vr: q = "both_right"
        elif lr and not vr: q = "legacy_right_v2_not"
        elif not lr and vr: q = "v2_right_legacy_not"
        else: q = "both_wrong_or_none"
        qs[q] += 1
        if lo and not lr:
            leg_defects.append(r)
        if vs and not vr and lr:
            v2_worse.append(r)
            served_worse += 1
        if vs and vr and not lr:
            served_better += 1
        if not vr:
            v2_bad.append(r)
    print(f"== {bank} ({n} files)")
    for q, c in qs.most_common():
        print(f"   {q:22} {c:4}  ({round(100*c/n,1)}%)")
    print(f"   leg: parsed={sum(1 for r in recs if leg_output(r))} "
          f"err={sum(1 for r in recs if (r.get('leg') or {}).get('error'))} "
          f"integrity_fail={sum(1 for r in recs if (r.get('leg') or {}).get('integrity_failed_checks'))} "
          f"chain_bad={sum(1 for r in recs if any('chain' in f for f in (r.get('leg') or {}).get('flags') or []))}")
    print(f"   v2: {dict(Counter((r.get('v2') or {}).get('status') for r in recs))} "
          f"verdicts={dict(Counter((r.get('v2') or {}).get('verdict') for r in recs if (r.get('v2') or {}).get('status')=='v2'))}")
    print(f"   serve sim: v2_better={served_better} v2_worse={served_worse} (of {n})")
    if leg_defects:
        c = Counter()
        for r in leg_defects:
            lg = r["leg"]
            cause = ("chain_breaks" if any("chain" in f for f in lg.get("flags", []))
                     else ("rows_gt_dated" if any("rows_gt" in f for f in lg.get("flags", []))
                           else ("integrity:" + ",".join(lg.get("integrity_failed_checks", [])) if lg.get("integrity_failed_checks")
                                 else "rowcount_vs_dated")))
            c[cause] += 1
        print(f"   legacy defects ({len(leg_defects)}):", dict(c))
        print("     ", [(r["sha8"], r["leg"].get("rows"), r.get("dated_amt_lines"),
                          r["leg"].get("flags"), r["leg"].get("integrity_failed_checks")) for r in leg_defects[:8]])
    if v2_worse:
        print(f"   v2-worse sha8s:", [(r["sha8"], r["v2"].get("verdict"), r["v2"].get("flags")) for r in v2_worse])
    v2fb = Counter((r.get("v2") or {}).get("fallback") for r in recs if (r.get("v2") or {}).get("status") == "fallback")
    if v2fb:
        print("   v2 fallback reasons:", dict(v2fb))
