"""n7 perf: p50/p95 analyze + process time per candidate from e2e records.
usage: python tools/n7/perf.py"""
import json, glob, statistics

def pct(v, p):
    if not v: return None
    v = sorted(v); k = (len(v) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 1)

per = {}
for f in glob.glob("tools/n7/.local/e2e_*.jsonl") + glob.glob("tools/n7/.local/neg_*.jsonl"):
    bank = f.split("e2e_")[-1].split("neg_")[-1].split(".jsonl")[0]
    for l in open(f, encoding="utf-8"):
        r = json.loads(l)
        d = per.setdefault(bank, {"an": [], "pr": [], "over120": []})
        if r.get("t_analyze_s") is not None: d["an"].append(r["t_analyze_s"])
        if r.get("t_process_s") is not None:
            d["pr"].append(r["t_process_s"])
            if r["t_process_s"] > 120: d["over120"].append((r["sha8"], r["t_process_s"]))
for b, d in sorted(per.items()):
    print(f"{b:16s} analyze p50={pct(d['an'],50)} p95={pct(d['an'],95)} n={len(d['an'])} | "
          f"process p50={pct(d['pr'],50)} p95={pct(d['pr'],95)} n={len(d['pr'])} | >120s: {d['over120']}")
