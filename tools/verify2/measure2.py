"""verify2 measure: fresh shadow-mode router pass over manifest files.
usage: python tools/verify2/measure2.py <backend_dir> <out.jsonl> --sha8-file=<list> [--banks=a,b]
Own implementation for prompt-28 verification; not shared with earlier tooling."""
import json, os, sys, glob

backend, out_path = sys.argv[1], sys.argv[2]
sha8_file, banks = None, set()
for a in sys.argv[3:]:
    if a.startswith("--sha8-file="):
        sha8_file = a[12:]
    elif a.startswith("--banks="):
        banks = set(a[8:].split(","))

sys.path.insert(0, backend)
os.environ.setdefault("STATEMENT_ENGINE_V2_MODE", "shadow")

from app.services.statement_engine.v2_router import route_pdf
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY

here = os.path.dirname(os.path.abspath(__file__))
mani = {}
for m in glob.glob(os.path.join(here, ".local", "manifest_*.jsonl")):
    for ln in open(m, encoding="utf-8"):
        d = json.loads(ln)
        mani[d["sha8"]] = d["path"]

folders = json.load(open(os.path.join(here, ".local", "folders.json"), encoding="utf-8"))
fol2bank = {fol.lower(): info["bank_id"] for fol, info in folders.items()}

def exp_bank(path):
    p = path.replace("\\", "/").lower()
    for fol, b in fol2bank.items():
        if "/" + fol + "/" in p:
            return b
    return "unknown"

sel = set(open(sha8_file, encoding="utf-8").read().split()) if sha8_file else set(mani)
done = set()
if os.path.exists(out_path):
    for ln in open(out_path, encoding="utf-8"):
        done.add(json.loads(ln)["sha8"])

out = open(out_path, "a", encoding="utf-8")
for s8 in sorted(sel - done):
    path = mani.get(s8)
    if not path:
        continue
    bank = exp_bank(path)
    if banks and bank not in banks:
        continue
    try:
        res = route_pdf(path, DEFAULT_REGISTRY)
        ex = res.result
        rec = {
            "sha8": s8, "folder_bank": bank, "status": res.status,
            "layout": res.layout_id or "", "fallback_reason": getattr(res, "fallback_reason", "") or "",
            "verdict": getattr(ex, "verification_status", None) if ex else None,
            "rows": len(ex.transactions or []) if ex else 0,
            "warnings": [str(w) for w in (ex.warnings or [])] if ex else [],
            "notes": list(getattr(res, "notes", []) or []),
        }
    except Exception as e:
        rec = {"sha8": s8, "folder_bank": bank, "status": "error", "error": type(e).__name__}
    out.write(json.dumps(rec) + "\n")
    out.flush()
out.close()
print("done")
