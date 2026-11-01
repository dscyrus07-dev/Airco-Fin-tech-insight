"""Probe: for each bank sample PDF, extract via v2 route_for_serve,
measure description usability + classification coverage (same chain as production).
Run inside backend image with /samples mounted read-only.
"""
import json, os, re, sys, glob

sys.path.insert(0, "/app")
os.environ.setdefault("STATEMENT_ENGINE_V2_MODE", "serve")

from app.services.statement_engine import serve as _serve
from app.services.pipeline.classification.rule_engine import JsonRuleEngine

SAMPLES = "/samples"
BANKS_DIR = "/app/app/services/banks"

# spec_key -> display folder name via registry bank_name
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
name_by_spec = {}
for s in DEFAULT_REGISTRY._specs.values():
    name_by_spec.setdefault(s.bank_key, s.bank_name)

serve_keys = sorted(_serve.spec_bank_keys())
engines = {}

def engine_for(spec_key):
    pk = _serve.pipeline_key_for(spec_key)
    key = pk if os.path.isfile(f"{BANKS_DIR}/{pk}/rules.json") else "unknown"
    if key not in engines:
        engines[key] = JsonRuleEngine(bank_key=key)
    return engines[key], key

results = []
for spec_key in serve_keys:
    disp = name_by_spec.get(spec_key, spec_key)
    folder = os.path.join(SAMPLES, disp)
    pdfs = sorted(glob.glob(os.path.join(folder, "*.pdf"))) if os.path.isdir(folder) else []
    if not pdfs:
        results.append((spec_key, disp, "NO_PDF", 0, 0, 0, ""))
        continue
    pdf = pdfs[0]
    try:
        routed, det, ms = _serve.route_for_serve(pdf, spec_key, timeout_s=60)
    except Exception as e:
        results.append((spec_key, disp, f"ROUTE_ERR:{type(e).__name__}", 0, 0, 0, ""))
        continue
    src = _serve.row_source_from_routed(routed)
    if src is None:
        verdict = _serve.v2_verdict(routed)
        results.append((spec_key, disp, f"NO_ROWS verdict={verdict}", 0, 0, 0, ""))
        continue
    rows = src.transactions
    n = len(rows)
    usable = sum(1 for r in rows if len(re.findall(r"[A-Za-z]", str(r.get("description") or ""))) >= 3)
    eng, eng_key = engine_for(spec_key)
    classified, unclassified = eng.classify(rows)
    cov = round(len(classified) / max(n, 1) * 100, 1)
    sample_desc = next((str(r.get("description") or "")[:45] for r in rows), "")
    results.append((spec_key, disp, eng_key, n, usable, cov, sample_desc))

print(f"{'spec_key':22} {'engine':10} {'rows':>4} {'usable_desc':>11} {'cov%':>6}  sample")
for spec_key, disp, eng_key, n, usable, cov, sd in results:
    print(f"{spec_key:22} {eng_key:10} {n:>4} {usable:>11} {cov:>6}  {sd}")
