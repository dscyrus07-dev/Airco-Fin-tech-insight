"""verify4 recount: aggregate v4_shard*.jsonl into per-bank gate table.
usage: python tools/verify4/recount.py <shard_glob>... [--json=path]"""
import json, sys, glob, collections
out = None; pats = []
for a in sys.argv[1:]:
    if a.startswith("--json="): out = a[7:]
    else: pats.append(a)
rows = [json.loads(l) for p in pats for g in glob.glob(p) for l in open(g)]
by = collections.defaultdict(list)
for r in rows: by[r.get("folder_bank") or "?"].append(r)
tbl = []
for b in sorted(by):
    fs = by[b]; n = len(fs)
    det = sum(1 for r in fs if r.get("status") == "v2")
    unsup = sum(1 for r in fs if r.get("status") == "unsupported")
    fb = sum(1 for r in fs if r.get("status") == "fallback")
    v = sum(1 for r in fs if r.get("verdict") == "VERIFIED")
    rv = sum(1 for r in fs if r.get("verdict") == "REVIEW")
    f = sum(1 for r in fs if r.get("verdict") == "FAILED")
    rows_ok = sum(1 for r in fs if r.get("verdict") in ("VERIFIED","REVIEW") and (r.get("rows") or 0) > 0)
    v2vr = v + rv
    tbl.append({"bank": b, "files": n, "det": det, "unsup": unsup, "fb": fb,
                "V": v, "R": rv, "F": f,
                "det_pct": round(100*det/n,1), "yield_pct": round(100*rows_ok/n,1),
                "vshare_pct": round(100*v/v2vr,1) if v2vr else None})
for t in tbl:
    print(f"{t['bank']:<18} n={t['files']:<4} det={t['det']}({t['det_pct']}%) "
          f"unsup={t['unsup']} fb={t['fb']} V={t['V']} R={t['R']} F={t['F']} "
          f"yield={t['yield_pct']}% vshare={t['vshare_pct']}%")
print("TOTAL files:", sum(t['files'] for t in tbl))
if out: json.dump(tbl, open(out,"w"), indent=1)
