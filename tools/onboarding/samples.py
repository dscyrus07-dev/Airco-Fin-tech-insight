# samples.py — pick up to 5 representative files per bank covering fingerprints.
# Largest fingerprint first, then most-different ones, then largest/smallest pages.
# Writes .local/samples.json; prints sha8-only summary.
import os, json, glob
from collections import defaultdict, Counter

HERE = os.path.dirname(__file__)
LOCAL = os.path.join(HERE, ".local")

def load_jsonl(pat):
    rows = []
    for f in glob.glob(os.path.join(LOCAL, pat)):
        for l in open(f, encoding="utf-8"):
            try: rows.append(json.loads(l))
            except Exception: pass
    return rows

folders = json.load(open(os.path.join(LOCAL, "folders.json")))
scans = load_jsonl("scan_meta*.jsonl")

manifest = {}
for f in glob.glob(os.path.join(LOCAL, "manifest*.jsonl")):
    for l in open(f, encoding="utf-8"):
        try:
            j = json.loads(l); manifest[j["sha8"]] = j["path"]
        except Exception: pass
ROOT_PREFIX = "unified all statements"
def top_folder(s):
    p = manifest.get(s["sha8"], "")
    low = p.lower().replace("/", "\\")
    i = low.find(ROOT_PREFIX)
    if i < 0: return s["folder"]
    rest = p[i + len(ROOT_PREFIX):].lstrip("\\/")
    return rest.split("\\")[0].split("/")[0] or "(root)"

by_bank = defaultdict(list)
for s in scans:
    f = folders.get(top_folder(s))
    if f and f["class"] in ("bank", "alias") and s.get("has_text") and not s.get("locked") and not s.get("corrupt"):
        by_bank[f["bank_id"]].append(s)

def fp_of(s): return tuple(s.get("header_sig") or ["<none>"])

out = {}
for bid, files in by_bank.items():
    groups = defaultdict(list)
    for s in files: groups[fp_of(s)].append(s)
    ordered = sorted(groups.items(), key=lambda kv: -len(kv[1]))
    picks = []
    seen_fp = set()
    # 1) largest fingerprint rep, then each distinct fingerprint rep
    for fp, grp in ordered:
        if len(picks) >= 4: break
        if fp in seen_fp: continue
        seen_fp.add(fp)
        picks.append(grp[0])
    # 2) largest + smallest by pages (if not already picked)
    by_pages = sorted(files, key=lambda s: s.get("pages") or 0)
    for cand in (by_pages[-1], by_pages[0]):
        if len(picks) >= 5: break
        if all(p["sha8"] != cand["sha8"] for p in picks): picks.append(cand)
    picks = picks[:5]
    picked = {p["sha8"] for p in picks}
    out[bid] = {"samples": [p["sha8"] for p in picks],
                "fingerprints": len(groups),
                "holdout_n": len(files) - len(picks)}

manifest = {}
for f in glob.glob(os.path.join(LOCAL, "manifest*.jsonl")):
    for l in open(f, encoding="utf-8"):
        try:
            j = json.loads(l); manifest[j["sha8"]] = j["path"]
        except Exception: pass
json.dump(out, open(os.path.join(LOCAL, "samples.json"), "w"), indent=1)
with open(os.path.join(LOCAL, "samples_local.jsonl"), "w", encoding="utf-8") as f:
    for bid, v in out.items():
        for sha in v["samples"]:
            if sha in manifest:
                f.write(json.dumps({"bank_id": bid, "sha8": sha, "path": manifest[sha]}) + "\n")
for bid, v in out.items():
    print(f"{bid:22s} samples={v['samples']} fps={v['fingerprints']} holdout={v['holdout_n']}")
