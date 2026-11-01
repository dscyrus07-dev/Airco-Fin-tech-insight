import json, os, re, sys, glob
sys.path.insert(0, "/app")
os.environ.setdefault("STATEMENT_ENGINE_V2_MODE", "serve")
from app.services.statement_engine import serve as _serve
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY

name_by_spec = {}
for s in DEFAULT_REGISTRY._specs.values():
    name_by_spec.setdefault(s.bank_key, s.bank_name)

for spec_key in ["sbi", "dhanlaxmi", "idbi", "pnb", "central_bank", "idfc"]:
    disp = name_by_spec.get(spec_key, spec_key)
    pdfs = sorted(glob.glob(f"/samples/{disp}/*.pdf"))
    if not pdfs:
        print(spec_key, "NO_PDF"); continue
    routed, det, ms = _serve.route_for_serve(pdfs[0], spec_key, timeout_s=60)
    lid = "?"
    try:
        lid = routed.result.layout_id
    except Exception:
        pass
    print(f"\n=== {spec_key} pdf={os.path.basename(pdfs[0])[:50]} layout={lid}")
    if routed is None or routed.result is None:
        continue
    import pdfplumber
    with pdfplumber.open(pdfs[0]) as p:
        txt = (p.pages[1].extract_text() or "")
    hdr = [ln for ln in txt.split("\n") if re.search(r"(?i)date|particular|narrat|descrip|detail", ln)][:3]
    print("  header:", hdr)
    src = _serve.row_source_from_routed(routed)
    for r in src.transactions[:3]:
        print("  row desc:", repr(str(r.get("description") or "")[:60]), "| ref:", repr(str(r.get("ref_no") or "")[:30]))
