# analyze.py — join scan_meta + probe results + coverage map -> per-bank rows.
# Emits docs/onboarding/ONBOARDING_QUEUE.csv and .local/bank_stats.json.
import os, sys, json, csv, glob
from collections import Counter, defaultdict

HERE = os.path.dirname(__file__)
LOCAL = os.path.join(HERE, ".local")
DOCS = os.path.abspath(os.path.join(HERE, "..", "..", "docs", "onboarding"))

def load_jsonl(pat):
    rows = []
    for f in glob.glob(os.path.join(LOCAL, pat)):
        for l in open(f, encoding="utf-8"):
            try: rows.append(json.loads(l))
            except Exception: pass
    return rows

folders = json.load(open(os.path.join(LOCAL, "folders.json")))
scans = load_jsonl("scan_meta*.jsonl")

# manifest -> top-level folder (immediate parent may be a nested subdir like
# "<Bank>/Locked PDFs/")
man = {}
for f in glob.glob(os.path.join(LOCAL, "manifest*.jsonl")):
    for l in open(f, encoding="utf-8"):
        try:
            j = json.loads(l); man[j["sha8"]] = j["path"]
        except Exception: pass
ROOT_PREFIX = "unified all statements"
def top_folder(s):
    p = man.get(s["sha8"], "")
    low = p.lower().replace("/", "\\")
    i = low.find(ROOT_PREFIX)
    if i < 0: return s["folder"]
    rest = p[i + len(ROOT_PREFIX):].lstrip("\\/")
    return rest.split("\\")[0].split("/")[0] or "(root)"
for s in scans:
    s["top_folder"] = top_folder(s)
probes = {r["sha8"]: r for r in load_jsonl("probe_shadow.jsonl") if "sha8" in r}
probes_u = {r["sha8"]: r for r in load_jsonl("probe_universal.jsonl") if "sha8" in r}

by_bank = defaultdict(list)   # bank_id -> scan rows
nonbank = defaultdict(list)
unmapped = defaultdict(list)
for s in scans:
    f = folders.get(s["top_folder"])
    if f is None:
        unmapped[s["top_folder"]].append(s)
    elif f["class"] == "nonbank":
        nonbank[s["top_folder"]].append(s)
    else:
        by_bank[f["bank_id"]].append(s)

# layout_id -> bank_key via the shipped registry (detected bank for v2-served files)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "backend")))
try:
    from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY as _REG
    LAYOUT2BANK = {s.layout_id: s.bank_key for s in _REG.specs()}
except Exception:
    LAYOUT2BANK = {}

# engine ids that differ from folder bank ids
ID_ALIAS = {"bob": "bank_of_baroda", "bom": "bank_of_maharashtra",
            "equitas": "equitas_sfb", "scb": "standard_chartered",
            "ujjivan": "ujjivan_sfb"}

def detected_bank(p):
    """bank the engine attributed the file to: v2 layout bank, detector-routed
    fallback (other_bank/legacy_only), or raw detector note."""
    if not p: return None
    d = None
    if p.get("status") == "v2" and p.get("layout") in LAYOUT2BANK:
        d = LAYOUT2BANK[p["layout"]]
    else:
        fb = p.get("fb") or ""
        for pre in ("other_bank:", "legacy_only:"):
            if fb.startswith(pre): d = fb[len(pre):]
        if d is None: d = p.get("detected")
    return ID_ALIAS.get(d, d)

# canonical name match: detected bank id vs folder bank id (loose normalization)
def det_ok(p, bid):
    d = detected_bank(p)
    if not d: return None
    dd = d.lower().replace(" ", "_").replace("-", "_")
    bb = bid.lower()
    aliases = {bb, bb.replace("_", " "), bb.replace("_bank", ""), bb.replace("_", "")}
    return dd in aliases or any(dd.startswith(a) or a in dd for a in aliases if len(a) > 3)

rows = []
for bid, files in sorted(by_bank.items()):
    total = len(files)
    locked = sum(1 for f in files if f.get("locked"))
    corrupt = sum(1 for f in files if f.get("corrupt"))
    text = [f for f in files if f.get("has_text") and not f.get("locked") and not f.get("corrupt")]
    scanned = sum(1 for f in files if not f.get("has_text") and not f.get("locked") and not f.get("corrupt"))
    # fingerprints
    fps = Counter(tuple(f.get("header_sig") or ["<none>"]) for f in text)
    top_share = round(100 * fps.most_common(1)[0][1] / len(text), 1) if text else 0
    # balance anchors
    anchors = [f for f in text if f.get("open_bal") or f.get("close_bal")]
    anchor_pct = round(100 * len(anchors) / len(text), 1) if text else 0
    run_bal_pct = round(100 * sum(1 for f in text
                                  if f.get("dated_lines") and f.get("dated_multi_amt", 0) / max(f["dated_lines"], 1) > 0.5)
                        / len(text), 1) if text else 0
    # probes
    pr = [probes.get(f["sha8"]) for f in text if f["sha8"] in probes]
    det_ok_n = sum(1 for p in pr if det_ok(p, bid))
    det_wrong = sum(1 for p in pr if det_ok(p, bid) is False)
    det_targets = Counter(detected_bank(p) for p in pr if det_ok(p, bid) is False)
    det_pct = round(100 * det_ok_n / len(pr), 1) if pr else None
    tier = Counter((p or {}).get("status") for p in pr)
    verdicts = Counter((p or {}).get("verdict") for p in pr)
    fb_mix = Counter((p or {}).get("fb") for p in pr if (p or {}).get("fb"))
    # universal
    pru = [probes_u.get(f["sha8"]) for f in text if f["sha8"] in probes_u]
    tier_u = Counter((p or {}).get("status") for p in pru)
    verdicts_u = Counter((p or {}).get("verdict") for p in pru)
    codes_u = Counter((p or {}).get("code") for p in pru if (p or {}).get("code"))
    errs = Counter((p or {}).get("err") for p in (pr + pru) if (p or {}).get("err"))
    # multi-line narration: continuation/dated ratio > 0.3
    multiline_pct = round(100 * sum(1 for f in text
                                    if f.get("dated_lines") and f.get("continuation_lines", 0) / f["dated_lines"] > 0.3)
                          / len(text), 1) if text else 0
    nonascii_pct = round(100 * sum(1 for f in text if (f.get("nonascii_share") or 0) > 0.02) / len(text), 1) if text else 0
    # currency groups: {₹,rs,inr}=INR is one group; multi-currency only if a foreign
    # group co-occurs. multi_account_hint in scan data is unreliable (label-per-page
    # false positives) and is intentionally not reported.
    CUR_GROUPS = [{"₹", "rs", "inr"}, {"$", "usd"}, {"€"}, {"£"}, {"¥"}]
    def n_cur_groups(f):
        toks = set(f.get("currencies") or [])
        return sum(1 for g in CUR_GROUPS if toks & g)
    multi_cur = sum(1 for f in text if n_cur_groups(f) > 1)
    cov = next(v for k, v in folders.items() if v["bank_id"] == bid)
    rows.append({
        "bank_id": bid, "folder_n": sum(1 for k, v in folders.items() if v["bank_id"] == bid),
        "total": total, "text_n": len(text), "scanned_n": scanned, "locked_n": locked, "corrupt_n": corrupt,
        "fingerprints_n": len(fps), "top_fingerprint_share": top_share,
        "anchor_pct": anchor_pct, "run_bal_pct": run_bal_pct,
        "multiline_pct": multiline_pct, "nonascii_pct": nonascii_pct,
        "multi_cur": multi_cur,
        "probed_n": len(pr), "det_ok_pct": det_pct, "det_wrong_n": det_wrong,
        "det_targets": {k: v for k, v in det_targets.items() if k},
        "tier_mix": dict(tier), "verdict_mix": dict(verdicts), "fb_mix": dict(fb_mix),
        "tier_mix_u": dict(tier_u), "verdict_mix_u": dict(verdicts_u),
        "codes_u": dict(codes_u), "probe_errs": dict(errs),
        "coverage": {"registry_json": cov["registry_json"], "extractor_pkg": cov["extractor_pkg"],
                     "layoutspec": cov["layoutspec"], "legacy_processor": cov["legacy_processor"]},
        "_fps": {"/".join(k): v for k, v in fps.most_common()},
    })

nb_rows = {}
for name, files in nonbank.items():
    text_nb = [f for f in files if f.get("has_text") and not f.get("locked") and not f.get("corrupt")]
    pru_nb = [probes_u.get(f["sha8"]) for f in text_nb if f["sha8"] in probes_u]
    pr_nb = [probes.get(f["sha8"]) for f in text_nb if f["sha8"] in probes]
    nb_rows[name] = {
        "total": len(files), "text_n": len(text_nb),
        "scanned_n": sum(1 for f in files if not f.get("has_text") and not f.get("locked") and not f.get("corrupt")),
        "locked_n": sum(1 for f in files if f.get("locked")),
        "det": Counter(detected_bank(p) or "none" for p in pr_nb),
        "tier": Counter((p or {}).get("status") for p in pr_nb),
        "u_verdict": Counter((p or {}).get("verdict") for p in pru_nb),
    }
json.dump(nb_rows, open(os.path.join(LOCAL, "nonbank_stats.json"), "w"), indent=1)
json.dump(rows, open(os.path.join(LOCAL, "bank_stats.json"), "w"), indent=1)
os.makedirs(DOCS, exist_ok=True)
with open(os.path.join(DOCS, "ONBOARDING_QUEUE.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["bank_id","folders","total","text_n","scanned_n","locked_n","corrupt_n",
                "fingerprints_n","top_fp_share","anchor_pct","run_bal_pct","multiline_pct",
                "nonascii_pct","probed_n","det_ok_pct","det_wrong_n","tier_mix","verdict_mix",
                "coverage"])
    for r in rows:
        w.writerow([r["bank_id"], r["folder_n"], r["total"], r["text_n"], r["scanned_n"],
                    r["locked_n"], r["corrupt_n"], r["fingerprints_n"], r["top_fingerprint_share"],
                    r["anchor_pct"], r["run_bal_pct"], r["multiline_pct"], r["nonascii_pct"],
                    r["probed_n"], r["det_ok_pct"], r["det_wrong_n"],
                    json.dumps(r["tier_mix"]), json.dumps(r["verdict_mix"]), json.dumps(r["coverage"])])
print(f"banks={len(rows)} nonbank_groups={len(nonbank)} files={sum(len(v) for v in by_bank.values())}")
for k, v in nonbank.items(): print("nonbank:", k, len(v))
for k, v in unmapped.items(): print("UNMAPPED FOLDER:", k, len(v))
