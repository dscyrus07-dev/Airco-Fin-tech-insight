import json, os, re, sys, glob
sys.path.insert(0, "/app")
os.environ.setdefault("STATEMENT_ENGINE_V2_MODE", "serve")
from app.services.statement_engine import serve as _serve
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY

name_by_spec = {}
for s in DEFAULT_REGISTRY._specs.values():
    name_by_spec.setdefault(s.bank_key, s.bank_name)

for spec_key in ["idfc", "sbi", "dhanlaxmi", "idbi", "pnb", "central_bank"]:
    disp = name_by_spec.get(spec_key, spec_key)
    pdfs = sorted(glob.glob(f"/samples/{disp}/*.pdf"))
    if not pdfs:
        print(spec_key, "NO_PDF"); continue
    routed, det, ms = _serve.route_for_serve(pdfs[0], spec_key, timeout_s=60)
    src = _serve.row_source_from_routed(routed)
    if src is None:
        print(spec_key, "NO_ROWS"); continue
    rows = src.transactions[:6]
    print(f"\n=== {spec_key} ({disp}) keys={sorted(rows[0].keys())}")
    for r in rows:
        short = {k: (str(v)[:38] if v is not None else None) for k, v in r.items() if v not in (None, "", 0)}
        print(" ", json.dumps(short, ensure_ascii=False))
