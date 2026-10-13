"""Aggregate a measure.py JSONL into per-bank stats. Independent implementation.

usage: python tools/verify/summarize.py <run.jsonl>
"""
import json, sys, collections

rows = [json.loads(ln) for ln in open(sys.argv[1], encoding="utf-8")]
by = collections.defaultdict(list)
for r in rows:
    by[r["exp"]].append(r)

def routed_bank(r):
    if r.get("spec_bank"):
        return r["spec_bank"]
    fb = r.get("fb", "")
    for pre in ("legacy_only:", "other_bank:"):
        if fb.startswith(pre):
            return fb.split(":", 1)[1]
    return ""

for b in sorted(by):
    rs = by[b]
    n = len(rs)
    v2 = [r for r in rs if r.get("status") == "v2"]
    det_ok = sum(1 for r in rs if r.get("det_bank") == b or routed_bank(r) == b)
    wrong = [(r["sha8"], routed_bank(r) or r.get("det_bank") or r.get("fb", "") or r["status"])
             for r in rs if (routed_bank(r) and routed_bank(r) != b
                             and not routed_bank(r).startswith("v2_failed"))]
    verdicts = collections.Counter(r.get("verdict") or "-" for r in v2)
    reasons = collections.Counter(x for r in v2 for x in (r.get("reasons") or []))
    fbs = collections.Counter(r.get("fb", "") for r in rs if r.get("status") == "fallback")
    ms = [r.get("ms", 0) for r in rs]
    print(f"{b}: n={n} det/routed-ok={det_ok} ({100*det_ok/n:.1f}%) v2={len(v2)} "
          f"verdicts={dict(verdicts)} rows={sum(r.get('rows',0) for r in v2)} "
          f"fb={dict(fbs.most_common(4))} reasons={dict(reasons.most_common(4))} "
          f"ms_med={sorted(ms)[len(ms)//2] if ms else 0}")
    if wrong:
        print(f"   WRONG-BANK ({len(wrong)}): {wrong[:10]}")
