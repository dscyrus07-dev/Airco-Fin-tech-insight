"""tip vs bedc4bf baseline diff on identical fields; downward = verdict/regression."""
import json, glob, collections
base = {}
for f in glob.glob("../wt-n9/tools/final/.local/base_only/base_shard*.jsonl"):
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); base[r["sha8"]] = r
tip = {}
for f in glob.glob("tools/verify4/.local/reg_shard*.jsonl"):
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); tip[r["sha8"]] = r
print("base:", len(base), "tip:", len(tip))
RANK = {"VERIFIED": 3, "REVIEW": 2, "FAILED": 1, None: 0}
down, up, lat = [], [], []
for s8 in sorted(set(base) & set(tip)):
    b, t = base[s8], tip[s8]
    if all(b.get(k) == t.get(k) for k in ("status","folder_bank","layout","verdict","rows","fallback_reason")): continue
    bv, tv = RANK.get(b.get("verdict")), RANK.get(t.get("verdict"))
    rec = (s8, b.get("folder_bank"), {k: (b.get(k), t.get(k)) for k in ("status","verdict","layout","rows","fallback_reason") if b.get(k)!=t.get(k)})
    (down if tv < bv else up if tv > bv else lat).append(rec)
print("diffs:", len(down)+len(up)+len(lat), "| downward:", len(down), "up:", len(up), "lateral:", len(lat))
for r in down[:15]: print(" DOWN", r)
for r in lat[:10]: print(" LAT", r)
