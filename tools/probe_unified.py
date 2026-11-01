import json, os, re, sys, glob
sys.path.insert(0, "/app")
os.environ.setdefault("STATEMENT_ENGINE_V2_MODE", "serve")
from app.services.statement_engine import serve as _serve
from app.services.pipeline.classification.rule_engine import JsonRuleEngine

BANKS_DIR = "/app/app/services/banks"
engines = {}
def eng_for(spec_key):
    pk = _serve.pipeline_key_for(spec_key)
    key = pk if os.path.isfile(f"{BANKS_DIR}/{pk}/rules.json") else "unknown"
    if key not in engines:
        engines[key] = JsonRuleEngine(bank_key=key)
    return engines[key]

FOLDERS = {
    "idfc": "IDFC First Bank", "sbi": "State Bank of India",
    "dhanlaxmi": "Dhanlaxmi Bank", "idbi": "IDBI Bank",
    "pnb": "Punjab National Bank", "central_bank": "Central Bank of India",
}
for spec_key, folder in FOLDERS.items():
    pdfs = sorted(glob.glob(f"/samples/{folder}/**/*.pdf", recursive=True))
    print(f"\n=== {spec_key} ({len(pdfs)} pdfs)")
    for pdf in pdfs[:14]:
        try:
            routed, det, ms = _serve.route_for_serve(pdf, spec_key, timeout_s=90)
            lid = (routed.result.metadata.extras or {}).get("layout_id", "?") if routed and routed.result else "?"
            src = _serve.row_source_from_routed(routed)
            if src is None:
                print(f"  {os.path.basename(pdf)[:42]:44} {lid[:40]:42} NO_ROWS")
                continue
            rows = src.transactions
            usable = sum(1 for r in rows if len(re.findall(r"[A-Za-z]", str(r.get("description") or ""))) >= 3)
            c, u = eng_for(spec_key).classify(rows)
            print(f"  {os.path.basename(pdf)[:42]:44} {lid[:40]:42} rows={len(rows):4} usable={usable:4} cov={round(len(c)/max(len(rows),1)*100,1):5}%")
        except Exception as e:
            print(f"  {os.path.basename(pdf)[:42]:44} ERR {type(e).__name__}")
