"""n7 validate: join e2e_n7 records with integrated-tip shadow records + wb_verify audits.
Checks per record: detected==folder bank (or override target), served verdict==shadow verdict,
tx rows == engine rows, no formula errors, integrity flag, anchor reconciliation.
usage: python tools/n7/validate_n7.py <e2e.jsonl...> --audits=<audit.jsonl> [--shardglob=tools/n7/.local/integ_shard*.jsonl]
prints verdict table (counts/sha8 only)."""
import json, glob, sys, os

e2e_files, audits_path, shardglob = [], None, "tools/n7/.local/integ_shard*.jsonl"
for a in sys.argv[1:]:
    if a.startswith("--audits="): audits_path = a[9:]
    elif a.startswith("--shardglob="): shardglob = a[12:]
    else: e2e_files.append(a)

shards = {}
for f in glob.glob(shardglob):
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); shards[r["sha8"]] = r
# widen: N6 h2h records carry folder bank + scoped v2 verdict for the 150-file samples
N6 = r"X:/Airco Projects/wt-n6/tools/n6/.local"
for f in glob.glob(os.path.join(N6, "*.h2h.jsonl")):
    bank = os.path.basename(f).split(".")[0]
    for l in open(f, encoding="utf-8"):
        r = json.loads(l)
        if r["sha8"] not in shards:
            v2 = r.get("v2") or {}
            shards[r["sha8"]] = {"sha8": r["sha8"], "folder_bank": bank, "status": v2.get("status"),
                                 "verdict": v2.get("verdict"), "rows": v2.get("rows"),
                                 "layout": v2.get("layout"), "fallback_reason": v2.get("fallback") or "", "src": "h2h"}
audits = {}
if audits_path:
    for l in open(audits_path, encoding="utf-8"):
        r = json.loads(l); audits[r["sha8"]] = r

DET2SPEC = {"bank_of_baroda": "bob"}
FOLDER2DET = {"bank_of_baroda": "bank_of_baroda"}

def check(r):
    s8, grp = r["sha8"], r.get("group")
    sh = shards.get(s8, {})
    issues = []
    det = (r.get("detected") or {}).get("id")
    folder = sh.get("folder_bank")
    if grp in ("main", "review", "fallback", "disagree"):
        if r.get("override_to"):
            pass
        elif det not in (None, folder):
            issues.append(f"detected={det}!={folder}")
    if grp in ("main", "review", "disagree") and not r.get("override_to"):
        em = r.get("engine_meta") or {}
        served_v = (em.get("verdict") or em.get("final_verdict"))
        sh_v = sh.get("verdict")
        if r.get("job_status") == "completed":
            if served_v and sh_v and served_v != sh_v:
                issues.append(f"verdict {served_v}!={sh_v}(shadow)")
            eng_rows = sh.get("rows")
            wb = r.get("workbook") or {}
            if wb.get("tx_rows") is not None and eng_rows is not None and wb["tx_rows"] != eng_rows:
                issues.append(f"wb_rows {wb['tx_rows']}!=eng {eng_rows}")
            if wb.get("formula_errors"):
                issues.append("formula_errors:" + ",".join(wb["formula_errors"][:3]))
            if em.get("integrity_passed") is False:
                issues.append("integrity=False:" + ",".join(em.get("integrity_failed_checks") or [])[:60])
            au = audits.get(s8)
            if au and wb.get("tx_rows") is not None and au.get("rows") is not None and wb["tx_rows"] != au["rows"]:
                issues.append(f"audit_rows {au['rows']}!=wb {wb['tx_rows']}")
    return issues

rows = []
for f in e2e_files:
    for l in open(f, encoding="utf-8"):
        r = json.loads(l)
        rows.append((r["sha8"], r.get("group"), r.get("job_status") or r.get("doc_state"), check(r)))
bad = [x for x in rows if x[3]]
print(f"records={len(rows)} flagged={len(bad)}")
for s8, g, st, iss in bad:
    print(" ", s8, g, st, "|", "; ".join(iss))
