"""n7: build per-candidate verification manifests from N6 h2h + integrated-tip shards.
usage: python tools/n7/picks.py <backend_dir>
Writes tools/n7/.local/picks_<bank>.json with named groups; counts+sha8 only."""
import json, glob, os, sys
sys.path.insert(0, sys.argv[1])

N6 = r"X:/Airco Projects/wt-n6/tools/n6/.local"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, ".local")
CANDS = ["bank_of_baroda", "canara", "icici", "indian_bank", "karnataka", "kotak"]

def load_h2h(bank):
    recs = {}
    for l in open(os.path.join(N6, bank + ".h2h.jsonl"), encoding="utf-8"):
        r = json.loads(l); recs[r["sha8"]] = r
    return recs

shards = {}
for f in glob.glob(os.path.join(OUT, "integ_shard*.jsonl")):
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); shards[r["sha8"]] = r

def pages_of(sha8):
    import glob as g
    for m in g.glob(os.path.join(HERE, "..", "verify2", ".local", "manifest_*.jsonl")):
        for l in open(m, encoding="utf-8"):
            d = json.loads(l)
            if d["sha8"] == sha8:
                try:
                    import pikepdf
                    with pikepdf.open(d["path"]) as pdf:
                        return len(pdf.pages)
                except Exception:
                    return -1
    return -1

mani = {}
for m in glob.glob(os.path.join(HERE, "..", "verify2", ".local", "manifest_*.jsonl")):
    for l in open(m, encoding="utf-8"):
        d = json.loads(l); mani[d["sha8"]] = d["path"]

def npages(sha8):
    try:
        import pikepdf
        with pikepdf.open(mani[sha8]) as pdf:
            return len(pdf.pages)
    except Exception:
        return -1

byfold = {}
for s8, r in shards.items():
    byfold.setdefault(r["folder_bank"], []).append(r)

summary = {}
for bank in CANDS:
    h2h = load_h2h(bank)
    v2_verified = sorted(s for s, r in h2h.items() if (r.get("v2") or {}).get("verdict") == "VERIFIED")
    v2_review   = sorted(s for s, r in h2h.items() if (r.get("v2") or {}).get("verdict") == "REVIEW")
    v2_failed   = sorted(s for s, r in h2h.items() if (r.get("v2") or {}).get("verdict") == "FAILED")
    def _leg_bad(r):
        leg = r.get("leg") or {}
        if leg.get("error"): return True
        if leg.get("chain_breaks"): return True
        if leg.get("integrity_passed") is False: return True
        return False
    def _rows_differ(r):
        leg, v2 = r.get("leg") or {}, r.get("v2") or {}
        return leg.get("rows") is not None and v2.get("rows") is not None and leg["rows"] != v2["rows"]
    disagree    = sorted(s for s, r in h2h.items()
                         if (r.get("v2") or {}).get("verdict") == "VERIFIED" and (_leg_bad(r) or _rows_differ(r)))
    leg_right   = sorted(s for s, r in h2h.items()
                         if not (r.get("leg") or {}).get("error") and not (r.get("v2") or {}).get("verdict"))
    # prefer multi-page VERIFIED for anchors
    main = v2_verified[:8]
    locked  = [r["sha8"] for r in byfold.get(bank, []) if r["status"] == "unsupported" and r["fallback_reason"] == "locked"]
    scanned = [r["sha8"] for r in byfold.get(bank, []) if r["status"] == "unsupported" and r["fallback_reason"] == "scanned_no_text"]
    pg = {s: npages(s) for s in (main + v2_review[:3] + leg_right[:2])}
    pick = {
        "bank": bank,
        "main": main, "review": v2_review[:4], "fallback": leg_right[:3],
        "disagree10": disagree[:10],
        "locked": locked[:2], "scanned": scanned[:2],
        "pages": pg,
        "all_verified": v2_verified,
        "counts": {"v2V": len(v2_verified), "v2R": len(v2_review), "v2F": len(v2_failed),
                   "disagree": len(disagree), "leg_right": len(leg_right),
                   "locked": len(locked), "scanned": len(scanned)},
    }
    json.dump(pick, open(os.path.join(OUT, "picks_" + bank + ".json"), "w"), indent=1)
    summary[bank] = pick["counts"]

print(json.dumps(summary, indent=1))
