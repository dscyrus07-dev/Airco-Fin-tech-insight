"""N9 cross-check: join the five sources of truth per bank id -> markdown table.
bank_status.json (shipped) | live API | UI semantics | PRODUCT_STATUS | measured evidence.
"""
import collections, glob, json, re

ROOT = "X:/Airco Projects/wt-n9"
LOCAL = f"{ROOT}/tools/final/.local"

status_json = json.load(open(f"{ROOT}/backend/app/services/statement_engine/bank_status.json"))["banks"]
api = json.load(open(f"{LOCAL}/rc_banks.json"))
api_all = {b["id"]: b for b in api["all_banks"]}
served_ids = {b["id"] for b in api["banks"] if b.get("v2_served")}

recs = [json.loads(l) for f in glob.glob(f"{LOCAL}/n9_shard*.jsonl") for l in open(f, encoding="utf-8")]
ev = collections.defaultdict(lambda: collections.Counter())
for r in recs:
    ev[r["folder_bank"]][r.get("verdict") or r.get("status") or "?"] += 1
    ev[r["folder_bank"]]["N"] += 1

N7_GO = {"bob", "canara", "icici", "indian_bank", "karnataka", "kotak"}
ps = open(f"{ROOT}/docs/PRODUCT_STATUS.md", encoding="utf-8").read().lower()

def ps_state(bid, name):
    """Coarse PRODUCT_STATUS truth: does the doc claim the bank is served/verified?"""
    for row in ps.splitlines():
        if row.startswith("|") and (bid.replace("_", " ") in row or name.lower() in row):
            if "not supported" in row:
                return "not_supported(claim)"
            if "review" in row and "serve review" in row:
                return "serve_review_only"
            if "serve" in row or "verified" in row:
                return "serve/verified(claim)"
            if "legacy" in row:
                return "legacy(claim)"
    return "not_listed"

UI = {
    "verified": "Verified group, selectable",
    "review_required": "Review-required group, selectable, review tag",
    "legacy": "Legacy-parser group, selectable",
    "coming_soon": "Coming-soon group, greyed + reason",
    "unsupported": "Not-supported group, greyed + reason",
}

rows = []
for bid in sorted(api_all):
    b = api_all[bid]
    shipped = status_json.get(bid, {})
    shipped_state = shipped.get("state") or ("served(derived)" if bid in served_ids else "absent")
    api_state = b["support_state"]
    evidence = ev.get(bid)
    ev_s = "-"
    if evidence:
        ev_s = f"N={evidence['N']} V={evidence.get('VERIFIED', 0)} R={evidence.get('REVIEW', 0)} F={evidence.get('FAILED', 0)}"
    if bid in N7_GO or bid == "bank_of_baroda":
        ev_s += " | N7 GO"
    agree = "ok"
    # agreement rule: shipped review_required must equal api review_required; served must be verified|review_required|legacy
    if shipped_state in ("review_required", "coming_soon", "unsupported") and shipped_state != api_state:
        agree = "DISAGREE"
    if bid in served_ids and api_state not in ("verified", "review_required", "legacy"):
        agree = "DISAGREE"
    rows.append((bid, shipped_state, api_state, UI[api_state], ev_s, agree))

print(f"| bank | shipped bank_status | API support_state | UI | evidence (n9 reg / N7) | agree |")
print(f"|---|---|---|---|---|---|")
for r in rows:
    print("| " + " | ".join(r) + " |")
