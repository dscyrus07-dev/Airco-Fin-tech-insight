"""verify2: count duplicate composite transaction keys per file — the trigger
for the base_processor order-rebuild row-leak defect.
usage: python tools/verify2/dupkeys.py <backend_dir> <manifest.jsonl> <out.jsonl>"""
import json, os, sys
sys.path.insert(0, sys.argv[1])
os.environ.setdefault("STATEMENT_ENGINE_V2_MODE", "shadow")
from app.services.statement_engine.v2_router import route_pdf
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY

def key(t):
    return (str(t.get("date")), str(t.get("description") or t.get("narration") or ""),
            str(t.get("reference") or t.get("ref") or ""),
            str(t.get("debit")), str(t.get("credit")), str(t.get("balance")))

mani = {json.loads(l)["sha8"]: json.loads(l)["path"] for l in open(sys.argv[2], encoding="utf-8")}
out = open(sys.argv[3], "w", encoding="utf-8")
for s8, p in sorted(mani.items()):
    rec = {"sha8": s8}
    try:
        r = route_pdf(p, DEFAULT_REGISTRY)
        ex = getattr(r, "result", None)
        rows = (getattr(ex, "transactions", None) or []) if ex else []
        rec["rows"] = len(rows)
        seen, dup = {}, 0
        for t in rows:
            k = key(t if isinstance(t, dict) else vars(t) if hasattr(t, "__dict__") else {})
            dup += seen.get(k, 0) > 0
            seen[k] = seen.get(k, 0) + 1
        rec["dup_keys"] = dup
        rec["verdict"] = getattr(ex, "verification_status", None) if ex else None
    except Exception as e:
        rec["error"] = str(e)[:120]
    out.write(json.dumps(rec) + "\n")
    print(s8, rec.get("rows"), "dup", rec.get("dup_keys"), rec.get("verdict"), rec.get("error", ""))
out.close()
