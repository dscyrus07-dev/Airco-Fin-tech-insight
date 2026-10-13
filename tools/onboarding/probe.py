# probe.py — route every text-readable corpus file through v2_router.
# usage: python probe.py <mode:shadow|universal> [limit]
# Resumable: appends to .local/probe_<mode>.jsonl, skips done sha8.
import os, sys, json

HERE = os.path.dirname(__file__)
LOCAL = os.path.join(HERE, ".local")
BACKEND = os.path.abspath(os.path.join(HERE, "..", "..", "backend"))
sys.path.insert(0, BACKEND)

MODE = sys.argv[1] if len(sys.argv) > 1 else "shadow"
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 10**9
SHARD = int(sys.argv[3]) if len(sys.argv) > 3 else 0
NSH = int(sys.argv[4]) if len(sys.argv) > 4 else 1

os.environ["STATEMENT_ENGINE_V2_MODE"] = "shadow" if MODE == "shadow" else "serve"
os.environ.setdefault("STATEMENT_ENGINE_V2_SERVE_BANKS", "hdfc,sbi,axis,idfc,paytm,citibank,city_union")
os.environ.setdefault("STATEMENT_ENGINE_MISMATCH_GUARD", "1")
os.environ["STATEMENT_ENGINE_UNIVERSAL_MODE"] = "on" if MODE == "universal" else "off"

from app.services.statement_engine.v2_router import route_pdf
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY as REG
if MODE == "universal":
    from app.services.statement_engine.universal.serve import attempt as u_attempt

OUT = os.path.join(LOCAL, f"probe_{MODE}.jsonl")
import glob
manifest = {}
for f in glob.glob(os.path.join(LOCAL, "manifest*.jsonl")):
    for l in open(f, encoding="utf-8"):
        try:
            j = json.loads(l); manifest[j["sha8"]] = j["path"]
        except Exception: pass
scans = []
for f in glob.glob(os.path.join(LOCAL, "scan_meta*.jsonl")):
    for l in open(f, encoding="utf-8"):
        try: scans.append(json.loads(l))
        except Exception: pass
todo = [s for s in scans if s.get("has_text") and not s.get("locked") and not s.get("corrupt")]
if MODE == "universal":
    # universal tier only engages where v2 did not serve
    sh = {}
    sp = os.path.join(LOCAL, "probe_shadow.jsonl")
    if os.path.exists(sp):
        for l in open(sp, encoding="utf-8"):
            try:
                j = json.loads(l); sh[j["sha8"]] = j
            except Exception: pass
    todo = [s for s in todo if sh.get(s["sha8"], {}).get("status") != "v2"]

done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        try: done.add(json.loads(l)["sha8"])
        except Exception: pass

n = 0
with open(OUT, "a", buffering=1, encoding="utf-8") as out:
    for s in todo:
        if n >= LIMIT: break
        sha = s["sha8"]
        try:
            if int(sha, 16) % NSH != SHARD: continue
        except ValueError:
            if SHARD != 0: continue
        if sha in done or sha not in manifest: continue
        try:
            if MODE == "universal":
                res, src = u_attempt(manifest[sha], bank_hint=s["folder"], isolated=False)
                rec = {"sha8": sha, "folder": s["folder"], "status": "universal",
                       "layout": (res.outcome.layout_id if getattr(res, "outcome", None) else None),
                       "rows": res.meta.get("rows", 0),
                       "verdict": res.verdict, "code": res.code}
            else:
                r = route_pdf(manifest[sha], REG)
                det = None
                for nt in (r.notes or []):
                    if nt.startswith("detector:"):
                        det = nt.split(":")[1] or None
                        if det in ("None", "none"): det = None
                        break
                rec = {"sha8": sha, "folder": s["folder"], "status": r.status,
                       "layout": r.layout_id, "fb": r.fallback_reason,
                       "detected": det,
                       "rows": len(r.result.transactions or []) if r.result else 0,
                       "verdict": (r.result.metadata.extras or {}).get("verdict") if r.result else None,
                       "warns": sorted((r.result.metadata.extras or {}).get("warnings", []))[:6] if r.result else []}
        except Exception as e:
            rec = {"sha8": sha, "folder": s["folder"], "err": type(e).__name__}
        print(json.dumps(rec), file=out)
        done.add(sha)
        n += 1
print("probed", n, "mode", MODE)
