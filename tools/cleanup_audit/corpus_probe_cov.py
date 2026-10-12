# Corpus probe under coverage: route_pdf over a corpus sample, per-mode.
# usage: coverage run --data-file=... corpus_probe_cov.py <mode> <n>
import sys, os, json, glob, random
BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
sys.path.insert(0, BACKEND)
MODE = sys.argv[1]; N = int(sys.argv[2])
os.environ["STATEMENT_ENGINE_V2_MODE"] = MODE
os.environ.setdefault("STATEMENT_ENGINE_V2_SERVE_BANKS", "hdfc,sbi,axis,idfc,paytm,citibank,city_union")
os.environ.setdefault("STATEMENT_ENGINE_MISMATCH_GUARD", "1")
os.environ.setdefault("STATEMENT_ENGINE_UNIVERSAL_MODE", "off")
from app.services.statement_engine.v2_router import route_pdf
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY as REG
paths = []
for f in glob.glob(r"X:\Airco Projects\wt-guard\comparison\guard\in_*.jsonl"):
    paths += [json.loads(l) for l in open(f, encoding="utf-8")]
random.seed(7); random.shuffle(paths)
OUT = os.path.join(os.path.dirname(__file__), f"corpus_cov_{MODE}.jsonl")
done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        try: done.add(json.loads(l)["sha"])
        except Exception: pass
out = open(OUT, "a", buffering=1, encoding="utf-8")
n = 0
for it in paths:
    if it["sha"][:8] in done or n >= N: continue
    n += 1
    try:
        r = route_pdf(it["path"], REG)
        rec = {"sha": it["sha"][:8], "folder": it["folder"], "status": r.status,
               "layout": r.layout_id, "fb": r.fallback_reason,
               "rows": len(r.result.transactions or []) if r.result else 0,
               "verdict": (r.result.metadata.extras or {}).get("verdict") if r.result else None}
    except Exception as e:
        rec = {"sha": it["sha"][:8], "folder": it["folder"], "err": type(e).__name__}
    print(json.dumps(rec), file=out)
print("done", n)
