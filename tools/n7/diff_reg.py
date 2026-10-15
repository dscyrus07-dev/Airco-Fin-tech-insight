"""n7 regression diff: base-tip shards vs integrated-tip shards.
Fields compared: status, fallback_reason, layout, rows, verdict, folder_bank.
usage: python tools/n7/diff_reg.py --base=<dir> --integ=<dir>
prints per-sha8 diffs + summary counts."""
import json, glob, sys

base_dir, integ_dir = None, None
for a in sys.argv[1:]:
    if a.startswith("--base="): base_dir = a[7:]
    elif a.startswith("--integ="): integ_dir = a[8:]

def load(d):
    pat = d if d.rstrip("/").endswith(".jsonl") else d.rstrip("/") + "/*shard*.jsonl"
    out = {}
    for f in glob.glob(pat):
        for l in open(f, encoding="utf-8"):
            r = json.loads(l); out[r["sha8"]] = r
    return out

B, I = load(base_dir), load(integ_dir)
FIELDS = ("status", "fallback_reason", "layout", "rows", "verdict")
only_b = sorted(set(B) - set(I)); only_i = sorted(set(I) - set(B))
diffs = []
for s8 in sorted(set(B) & set(I)):
    b, i = B[s8], I[s8]
    d = {f: (b.get(f), i.get(f)) for f in FIELDS if b.get(f) != i.get(f)}
    if d:
        diffs.append((s8, i.get("folder_bank"), d))
print(f"base={len(B)} integ={len(I)} common={len(set(B)&set(I))} only_base={len(only_b)} only_integ={len(only_i)} diffs={len(diffs)}")
from collections import Counter
bank_c = Counter(x[1] for x in diffs)
print("diff banks:", dict(bank_c))
for s8, fb, d in diffs:
    print(" ", s8, fb, json.dumps(d))
