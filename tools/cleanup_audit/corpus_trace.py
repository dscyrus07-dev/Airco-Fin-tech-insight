# Corpus runtime trace: which backend modules execute during route_pdf on a corpus sample.
# sys.settrace records file names only (no content). Resumable via out file. Counts only.
import sys, os, json, glob, random, time

BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
sys.path.insert(0, BACKEND)

MODE = sys.argv[1] if len(sys.argv) > 1 else "shadow"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 600
os.environ["STATEMENT_ENGINE_V2_MODE"] = MODE
os.environ.setdefault("STATEMENT_ENGINE_V2_SERVE_BANKS", "hdfc,sbi,axis,idfc,paytm,citibank,city_union")
os.environ.setdefault("STATEMENT_ENGINE_MISMATCH_GUARD", "1")
os.environ.setdefault("STATEMENT_ENGINE_UNIVERSAL_MODE", "off")

from app.services.statement_engine.v2_router import route_pdf
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY as REG

paths = []
for f in glob.glob(r"X:\Airco Projects\wt-guard\comparison\guard\in_*.jsonl"):
    paths += [json.loads(l) for l in open(f, encoding="utf-8")]
random.seed(7)
random.shuffle(paths)

OUT = os.path.join(os.path.dirname(__file__), f"corpus_trace_{MODE}.jsonl")
done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        try:
            done.add(json.loads(l)["sha"])
        except Exception:
            pass

hit = set()
def tracer(frame, event, arg):
    fn = frame.f_code.co_filename
    if "\\app\\" in fn or "/app/" in fn:
        hit.add(fn)
    return tracer

out = open(OUT, "a", buffering=1, encoding="utf-8")
n = 0
for it in paths:
    if it["sha"][:8] in done or n >= N:
        continue
    n += 1
    sys.settrace(tracer)
    try:
        r = route_pdf(it["path"], REG)
        rec = {"sha": it["sha"][:8], "folder": it["folder"], "status": r.status,
               "layout": r.layout_id, "fb": r.fallback_reason,
               "mods": sorted(hit)}
    except Exception as e:
        rec = {"sha": it["sha"][:8], "folder": it["folder"], "err": type(e).__name__, "mods": sorted(hit)}
    finally:
        sys.settrace(None)
    print(json.dumps(rec), file=out)
print("done", n)
