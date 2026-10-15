"""n7 confusion matrix: folder bank vs routed spec bank on the integrated tip.
A "wrong accept" = status v2 whose layout belongs to a different bank than the folder.
usage: python tools/n7/confusion.py [--max-per-folder=10]
Reads tools/n7/.local/integ_shard*.jsonl. Prints matrix counts + any wrong accepts."""
import json, glob, sys, re
from collections import Counter, defaultdict

cap = None
for a in sys.argv[1:]:
    if a.startswith("--max-per-folder="): cap = int(a[17:])

LAYOUT_BANK = {"indianbank": "indian_bank", "bankofindia": "bank_of_india", "bom": "bank_of_maharashtra",
               "au": "au_sfb", "citi": "citibank", "scb": "standard_chartered",
               "airtelpb": "airtel_pb", "city_union": "city_union", "south_indian": "south_indian",
               "bank_of_baroda": "bob", "bank_of_india": "bank_of_india", "bank_of_maharashtra": "bank_of_maharashtra"}
KNOWN = sorted(LAYOUT_BANK, key=len, reverse=True)

def spec_of_layout(layout):
    if not layout: return None
    for k in KNOWN:
        if layout.startswith(k): return LAYOUT_BANK[k]
    return layout.split("_")[0]

recs = defaultdict(list)
for f in glob.glob("tools/n7/.local/integ_shard*.jsonl"):
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); recs[r["folder_bank"]].append(r)

wrong, mat = [], Counter()
for folder, rs in sorted(recs.items()):
    if cap: rs = rs[:cap]
    for r in rs:
        if r["status"] == "v2":
            routed = spec_of_layout(r.get("layout") or "")
            mat[(folder, routed)] += 1
            if routed != folder and not (folder == "bank_of_baroda" and routed == "bob"):
                wrong.append((r["sha8"], folder, routed, r.get("layout")))
        elif r["status"] == "fallback" and r.get("fallback_reason") == "foreign_bank":
            mat[(folder, "<foreign_refused>")] += 1
        else:
            mat[(folder, "<" + r["status"] + ">" + (r.get("fallback_reason") or "")[:22])] += 1

print("folder -> routed")
for (f, t), n in sorted(mat.items()):
    flag = "  <-- WRONG" if t not in (f, "bob") and not t.startswith("<") else ""
    if t == f or t == "bob" and f == "bank_of_baroda" or t.startswith("<"):
        pass
    print(f"  {f:20s} -> {t:38s} {n}{flag}")
print(f"\nwrong_accepts={len(wrong)}")
for w in wrong: print("  ", w)
