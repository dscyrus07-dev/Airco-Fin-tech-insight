# Wave11 E1: candidate table from phase8c data (recompute, no re-run).
import json, collections, os, sys

P8 = r"X:\Airco Projects\Airco Insights fintech\wt-p8c\comparison\phase8c"
sys.path.insert(0, r"X:\Airco Projects\Airco Insights fintech\wt-w11\backend")
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.v2_router import DETECTOR_TO_SPEC_BANK as _D2S

LAYOUT2SPEC = {lid: s.bank_key for lid, s in DEFAULT_REGISTRY._specs.items()}

FOLDER_TO_DET = {
    "HDFC Bank": "hdfc", "SBI": "sbi", "ICICI Bank": "icici", "Axis Bank": "axis",
    "Kotak Mahindra Bank": "kotak", "Kotak Bank": "kotak",
    "Union Bank of India": "union", "Federal Bank": "federal", "Canara Bank": "canara",
    "Bank of Baroda": "bank_of_baroda", "IDFC First Bank": "idfc",
    "Paytm Bank": "paytm", "Paytm Payments Bank": "paytm",
    "Indian Bank": "indian_bank", "Karnataka Bank": "karnataka", "IndusInd Bank": "indusind",
    "Yes Bank": "yes", "DBS Bank": "dbs", "Punjab National Bank": "pnb",
    "Bank of India": "bank_of_india", "APGB Bank": "apgb", "APGV Bank": "apgv",
    "AU Small Finance Bank": "au_sfb", "Airtel Payments Bank": "airtel_pb",
    "Bandhan Bank": "bandhan", "Bank of Maharashtra": "bank_of_maharashtra",
    "CSB Bank": "csb", "Central Bank of India": "central_bank", "Citibank": "citibank",
    "City Union Bank": "city_union", "DBS Bank ": "dbs", "DCB Bank": "dcb",
    "Dhanlaxmi Bank": "dhanlaxmi", "Equitas Small Finance Bank": "equitas_sfb",
    "Fincare SFB Bank": "fincare", "Fino Payments Bank": "fino_pb", "HSBC": "hsbc",
    "IDBI Bank": "idbi", "India Post Payments Bank": "ippb", "Indian Overseas Bank": "iob",
    "Karur Vysya Bank": "kvb", "South Indian Bank": "south_indian",
    "Standard Chartered Bank": "standard_chartered",
    "Tamilnad Mercantile Bank": "tmb", "UCO Bank": "uco",
    "Ujjivan Small Finance Bank": "ujjivan_sfb", "Cosmos Bank": "cosmos",
}
DET_TO_SPEC = {
    "hdfc": "hdfc", "sbi": "sbi", "canara": "canara", "axis": "axis", "idfc": "idfc",
    "kotak": "kotak", "federal": "federal", "bank_of_baroda": "bob", "icici": "icici",
    "union": "union", "paytm": "paytm", "standard_chartered": "scb",
    "indian_bank": "indian_bank", "karnataka": "karnataka", "dbs": "dbs",
    "citibank": "citibank", "kvb": "kvb", "hsbc": "hsbc", "indusind": "indusind",
    "idbi": "idbi", "pnb": "pnb", "yes": "yes", "iob": "iob",
    "south_indian": "south_indian", "central_bank": "central_bank",
    "equitas_sfb": "equitas_sfb", "ujjivan_sfb": "ujjivan_sfb",
    "bank_of_maharashtra": "bank_of_maharashtra", "bandhan": "bandhan",
    "au_sfb": "au_sfb", "dcb": "dcb", "city_union": "city_union",
}
LEGACY_KEYS = {"hdfc", "axis", "icici", "bank_of_india", "indian_bank", "kotak", "sbi",
               "canara", "idfc", "karnataka", "paytm", "union", "bank_of_baroda", "bob"}
# demo acceptance: legacy job outcome per folder (from results_a/b/c)
DEMO_OK = {"HDFC Bank", "SBI", "ICICI Bank", "Axis Bank", "Kotak Mahindra Bank", "Kotak Bank",
           "IDFC First Bank", "Karnataka Bank", "Paytm Bank", "Paytm Payments Bank", "Bank of India"}

def load(f):
    return [json.loads(l) for l in open(os.path.join(P8, f), encoding="utf-8")]

after = load("after_0.jsonl") + load("after_1.jsonl") + load("after_2.jsonl")
forced = load("c5_forced.jsonl")

# spec key per record: file's TRUE bank
def spec_of(folder):
    det = FOLDER_TO_DET.get(folder)
    return DET_TO_SPEC.get(det) if det else None

by_spec = collections.defaultdict(list)
for r in after:
    k = spec_of(r["folder"])
    if k:
        by_spec[k].append(r)

# cross-bank forced sweep: files forced through each spec's layout
forced_by_spec = collections.defaultdict(list)
for r in forced:
    spec = r["layout"].split("_")[0]
    forced_by_spec[spec].append(r)
# spec prefix quirks: 'bob' layouts prefix 'bank_of_baroda'? check layout names
LAYOUT_PREFIX = {}
for spec in set(spec_of(f) for f in by_spec):
    LAYOUT_PREFIX[spec] = spec

rows = []
for spec in sorted(by_spec):
    recs = by_spec[spec]
    v2 = [r for r in recs if r["status"] == "v2"]
    ver = [r for r in v2 if r.get("verdict") == "VERIFIED"]
    rev = [r for r in v2 if r.get("verdict") == "REVIEW"]
    fail = [r for r in v2 if r.get("verdict") == "FAILED"]
    anchored = [r for r in v2 if (r.get("checks") or {}).get("reference") == "pass"]
    trusted = sum(1 for r in anchored if r.get("verdict") == "VERIFIED")
    ev = collections.Counter(
        n.split(":")[1] for r in v2 for n in r.get("notes") or [] if n.startswith("bank_evidence:")
    )
    # wrong-bank VERIFIED: the routed layout's spec contradicts the detector's
    # own HIGH/VERY_HIGH verdict (foreign-folder misfiles where detector agrees
    # are correct identifications, not acceptances)
    wrong = 0
    for r in recs:
        if r["status"] != "v2" or r.get("verdict") != "VERIFIED":
            continue
        det_note = next((n for n in (r.get("notes") or []) if n.startswith("detector:")), None)
        if not det_note:
            continue
        p = det_note.split(":")
        if p[2] in ("HIGH", "VERY_HIGH") and LAYOUT2SPEC.get(r["layout"]) != _D2S.get(p[1]):
            wrong += 1
    # cross-bank: files of OTHER banks VERIFIED under this spec's layouts
    fr = forced_by_spec.get(spec, [])
    xb = sum(1 for r in fr if r["verdict"] == "VERIFIED" and spec_of(r["folder"]) != spec)
    legacy = spec in LEGACY_KEYS or spec == "bob"
    folders = sorted(set(r["folder"] for r in recs))
    legacy_ok = any(f in DEMO_OK for f in folders)
    rows.append({
        "spec": spec, "folders": folders, "corpus": len(recs), "v2": len(v2),
        "verified": len(ver), "review": len(rev), "failed": len(fail),
        "anchored": len(anchored),
        "anchored_share": round(len(anchored) / len(v2) * 100, 1) if v2 else 0,
        "trusted": round(trusted / len(anchored) * 100, 1) if anchored else None,
        "fail_share": round(len(fail) / len(v2) * 100, 1) if v2 else 0,
        "wrong_bank": wrong, "cross_bank": xb, "evidence": dict(ev),
        "legacy": legacy, "legacy_ok": legacy_ok,
    })

print(f"{'spec':18} {'v2':>4} {'VER':>4} {'REV':>4} {'FAIL':>4} {'anch%':>6} {'trust%':>7} {'fail%':>6} {'wb':>3} {'xb':>4} {'evidence':30} legacy")
for r in rows:
    print(f"{r['spec']:18} {r['v2']:>4} {r['verified']:>4} {r['review']:>4} {r['failed']:>4} "
          f"{r['anchored_share']:>5}% {str(r['trusted']):>7} {r['fail_share']:>5}% {r['wrong_bank']:>3} {r['cross_bank']:>4} "
          f"{json.dumps(r['evidence']):30} {'ok' if r['legacy_ok'] else 'yes' if r['legacy'] else 'no'}")

json.dump(rows, open(r"X:\Airco Projects\Airco Insights fintech\wt-w11\comparison\wave11\e1_table.json", "w"), indent=1)
