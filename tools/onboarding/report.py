# report.py — build docs/onboarding/TRIAGE.md + ONBOARDING_QUEUE.csv from .local artifacts.
import os, csv, json

HERE = os.path.dirname(__file__)
LOCAL = os.path.join(HERE, ".local")
DOCS = os.path.abspath(os.path.join(HERE, "..", "..", "docs", "onboarding"))

stats = json.load(open(os.path.join(LOCAL, "bank_stats.json")))
samples = json.load(open(os.path.join(LOCAL, "samples.json")))
folders = json.load(open(os.path.join(LOCAL, "folders.json")))
nonbank = json.load(open(os.path.join(LOCAL, "nonbank_stats.json"))) \
    if os.path.exists(os.path.join(LOCAL, "nonbank_stats.json")) else {}

ALIASES = {bid: [k for k, v in folders.items() if v["bank_id"] == bid]
           for bid in {v["bank_id"] for v in folders.values() if v["bank_id"]}}

def difficulty(r):
    """low = layout + strong anchors + few fps; high = scanned-heavy/no anchors/no coverage."""
    if r["text_n"] == 0: return ("high", "no usable text layer")
    if r["scanned_n"] > r["text_n"]: return ("high", "majority scanned/image-only")
    if r["anchor_pct"] < 30 and r["run_bal_pct"] < 30:
        return ("high", "no printed balances - VERIFIED unreachable")
    if not r["coverage"]["registry_json"]:
        return ("high", "no detector markers/registration")
    if r.get("det_ok_pct") is not None and r["det_ok_pct"] < 50:
        return ("medium", "detection currently fails for most files")
    if r["coverage"]["layoutspec"] and r["top_fingerprint_share"] >= 60 and r["anchor_pct"] >= 70:
        return ("low", "layout exists, dominant fingerprint, anchored")
    if r["coverage"]["extractor_pkg"] or r["coverage"]["registry_json"]:
        return ("medium", "partial coverage or layout diversity")
    return ("high", "no coverage")

for r in stats:
    d, why = difficulty(r)
    r["difficulty"], r["why"] = d, why
    bl = []
    if r["scanned_n"] > r["text_n"]: bl.append("mostly scanned")
    if r["locked_n"] > 0.3 * r["total"]: bl.append("many locked")
    if r["anchor_pct"] < 50: bl.append("weak balance anchors")
    if r["run_bal_pct"] < 50: bl.append("no running balance column")
    if r["multiline_pct"] > 40: bl.append("heavy multi-line narration")
    if r["fingerprints_n"] > 3: bl.append(f"{r['fingerprints_n']} layout families")
    if r["nonascii_pct"] > 10: bl.append("non-English text present")
    if r["multi_cur"]: bl.append(f"multi-currency x{r['multi_cur']}")
    r["blockers"] = "; ".join(bl) or "-"
    r["samples"] = samples.get(r["bank_id"], {}).get("samples", [])
    r["holdout_n"] = samples.get(r["bank_id"], {}).get("holdout_n", r["text_n"])

rank_key = {"low": 0, "medium": 1, "high": 2}
order = sorted(stats, key=lambda r: (rank_key[r["difficulty"]], -r["text_n"], -r["anchor_pct"]))
for i, r in enumerate(order, 1):
    r["order"] = i

never_verified = [r for r in stats
                  if r["text_n"] > 0 and r["anchor_pct"] < 30 and r["run_bal_pct"] < 30]
tiny = [r for r in stats if 0 < r["text_n"] < 5]
multifp = [r for r in stats if r["fingerprints_n"] > 1]
misattr = [r for r in stats if r.get("det_wrong_n", 0) > 0]

EXT_ALIAS = {"bank_of_baroda": "bob", "bank_of_maharashtra": "bom",
             "equitas_sfb": "equitas", "standard_chartered": "scb",
             "ujjivan_sfb": "ujjivan"}

def cov_label(c, bid):
    ext = EXT_ALIAS.get(bid, bid)
    out = []
    if c["registry_json"]: out.append(f"banks/{bid}.json")
    if c["layoutspec"]: out.append(f"extractors/{ext}/layout_spec.py")
    if c["extractor_pkg"]: out.append(f"extractors/{ext}/")
    if c["legacy_processor"]: out.append("legacy processor")
    return ", ".join(out) or "none"

def mix_str(m, skip_null=True):
    return " ".join(f"{k}:{n}" for k, n in sorted(m.items())
                    if k and (k != "null" or not skip_null)) or "-"

lines = []
A = lines.append
A("# Corpus Triage - all-banks onboarding plan")
A("")
A("Base `8b57e0d` (`integration/v2-waves`). Read-only measurement; no product code changed.")
A("Shipped mode probed per file: `V2_MODE=shadow` + mismatch guard; then one pass with the")
A("universal tier on for files v2 did not serve. PII-free: bank ids, counts, sha8 only.")
A("Sample paths live in `tools/onboarding/.local/manifest*.jsonl` (gitignored).")
A("")
tot = lambda k: sum(r[k] for r in stats) + sum(v[k] for v in nonbank.values())
A(f"Corpus: {tot('total')} PDFs - {tot('text_n')} text-readable, {tot('scanned_n')} scanned/no-text,")
A(f"{tot('locked_n')} locked (counted, not opened), 0 corrupt. {len(stats)} bank ids,")
A(f"{len(nonbank)} non-bank folders with files (+1 empty: Others).")
A("")
A("## Summary (one row per bank)")
A("")
A("| bank | folders | pdf | text | scanned | locked | fps | top-fp% | anchors% | run-bal% | det-ok% | tier (shadow) | verdicts | univ. verdicts | coverage | diff | blockers |")
A("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in order:
    unrd = r["scanned_n"] + r["locked_n"] + r["corrupt_n"]
    tm = dict(r["tier_mix"])
    if unrd: tm["unreadable"] = unrd
    A(f"| {r['bank_id']} | {r['folder_n']} | {r['total']} | {r['text_n']} | "
      f"{r['scanned_n']} | {r['locked_n']} | {r['fingerprints_n']} | "
      f"{r['top_fingerprint_share']} | {r['anchor_pct']} | {r['run_bal_pct']} | "
      f"{r['det_ok_pct']} | {mix_str(tm)} | {mix_str(r['verdict_mix'])} | "
      f"{mix_str(r.get('verdict_mix_u', {}))} | {cov_label(r['coverage'], r['bank_id'])} | "
      f"{r['difficulty']} | {r['blockers']} |")
A("")
A("## Proposed onboarding order (recommendation)")
A("")
for r in order:
    A(f"{r['order']}. **{r['bank_id']}** — {r['text_n']} text, {r['fingerprints_n']} fp, "
      f"anchors {r['anchor_pct']}%, det-ok {r['det_ok_pct']}%, {r['difficulty']} — {r['why']}")
A("")
A("## Cannot reach VERIFIED (from data)")
A("")
if never_verified:
    for r in never_verified:
        A(f"- **{r['bank_id']}** — anchors {r['anchor_pct']}%, run-bal {r['run_bal_pct']}% ({r['why']})")
else:
    A("- none measured (all text-readable banks carry printed balances)")
A("")
A("## Banks detected as a different bank (surprising / review)")
A("")
if misattr:
    for r in misattr:
        tg = ", ".join(f"{k}x{v}" for k, v in sorted(r["det_targets"].items(),
                     key=lambda kv: -kv[1]))
        A(f"- **{r['bank_id']}** — {r['det_wrong_n']} file(s) attributed to: {tg}")
else:
    A("- none")
A("")
A("## What the data says about our approach")
A("")
A(f"- {len(multifp)} of {len(stats)} banks have >1 fingerprint — a 1–5-file sample is not")
A(f"  enough alone; hold-out sets must be re-checked after onboarding.")
A(f"- {len(tiny)} banks have <5 usable text files: "
  + (", ".join(f"{r['bank_id']}({r['text_n']})" for r in tiny) or "none"))
A(f"- Hold-out sizes: median {sorted(r['holdout_n'] for r in stats)[len(stats)//2]}, "
  f"largest {max(r['holdout_n'] for r in stats)}.")
A("")
A("## Not measured / limitations")
A("")
A("- Legacy-tier verdicts: shadow-mode routing produces no v2 verdict for fallback files;")
A("  the legacy engine's own verdict was not re-run per file (verdict columns cover")
A("  v2-served and universal-pass files only).")
A("- Multi-account statements: the scan heuristic was unreliable (per-page account-label")
A("  false positives); not reported. Needs distinct-account hashing in a later pass.")
A("- Locked PDFs counted only; never opened.")
A("- `detected-ok%` = share of probed text files the engine attributed to the folder's")
A("  bank (v2 layout bank or detector-routed fallback), not a detector-only score.")
A("")
A("## Non-bank folders")
A("")
A("| folder | total | text | scanned | locked | detected-as | shadow tier | universal verdict |")
A("|---|---|---|---|---|---|---|---|")
for name, v in sorted(nonbank.items()):
    A(f"| {name} | {v['total']} | {v['text_n']} | {v['scanned_n']} | {v['locked_n']} | "
      f"{mix_str(dict(v['det']), skip_null=False)} | {mix_str(dict(v['tier']))} | "
      f"{mix_str(dict(v['u_verdict']))} |")
A("")

os.makedirs(DOCS, exist_ok=True)
with open(os.path.join(DOCS, "TRIAGE.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

with open(os.path.join(DOCS, "ONBOARDING_QUEUE.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["bank_id","aliases","folder_count","text_n","scanned_n","locked_n","corrupt_n",
                "fingerprints_n","top_fingerprint_share","has_balance_anchors_pct",
                "current_detected_ok_pct","current_tier_mix","current_verdict_mix",
                "existing_coverage","sample_sha8s","holdout_n","difficulty","blockers",
                "proposed_order"])
    for r in order:
        w.writerow([r["bank_id"], "|".join(ALIASES.get(r["bank_id"], [])), r["folder_n"],
                    r["text_n"], r["scanned_n"], r["locked_n"], r["corrupt_n"],
                    r["fingerprints_n"], r["top_fingerprint_share"], r["anchor_pct"],
                    r["det_ok_pct"], json.dumps(r["tier_mix"]),
                    json.dumps(r["verdict_mix"]), cov_label(r["coverage"], r["bank_id"]),
                    "|".join(r["samples"]), r["holdout_n"], r["difficulty"],
                    r["blockers"], r["order"]])
print("wrote TRIAGE.md + ONBOARDING_QUEUE.csv;", len(stats), "banks")
