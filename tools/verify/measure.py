"""Resumable per-file V2-shadow measurement. Independent of tools/onboarding.

usage: python tools/verify/measure.py <backend_dir> <manifest_dir> <out.jsonl>
           [--banks b1,b2] [--folders-only] [--start N] [--count N] [--sample K:SEED]

Reads manifest_*.jsonl (sha8 + path) and folders.json (folder -> bank_id) from
manifest_dir. Emits one JSONL record per file; resumable by sha8.
"""
import json, os, random, re, sys, time

backend, manifest_dir, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
args = sys.argv[4:]
banks = set()
start, count, sample, sha8_file = 0, None, None, None
for a in args:
    if a.startswith("--banks="):
        banks = set(a[8:].split(","))
    elif a.startswith("--start="):
        start = int(a[8:])
    elif a.startswith("--count="):
        count = int(a[8:])
    elif a.startswith("--sha8-file="):
        sha8_file = a[12:]
    elif a.startswith("--sample="):
        k, seed = a[9:].split(":")
        sample = (int(k), int(seed))

sys.path.insert(0, backend)
os.environ.setdefault("STATEMENT_ENGINE_V2_MODE", "shadow")

folders = json.load(open(os.path.join(manifest_dir, "folders.json")))
f2b = {f: m["bank_id"] for f, m in folders.items() if isinstance(m, dict) and m.get("bank_id")}

files = {}
for mf in ("manifest_0.jsonl", "manifest_1.jsonl"):
    fp = os.path.join(manifest_dir, mf)
    if not os.path.exists(fp):
        continue
    for ln in open(fp, encoding="utf-8"):
        d = json.loads(ln)
        p = d.get("path", "")
        if not p.lower().endswith(".pdf"):
            continue
        rel = p.replace(os.sep, "/")
        top = rel.split("Unified All Statements/")[-1].split("/")[0]
        exp = f2b.get(top)
        if exp and (not banks or exp in banks):
            files[d["sha8"]] = (p, exp, top)

items = sorted(files.items())
if sha8_file:
    keep = set(open(sha8_file).read().split())
    items = [(s, v) for s, v in items if s in keep]
if sample:
    random.seed(sample[1])
    items = random.sample(items, min(sample[0], len(items)))
items = items[start:start + count if count else None]

done = set()
if os.path.exists(out_path):
    for ln in open(out_path, encoding="utf-8"):
        done.add(json.loads(ln)["sha8"])

from app.services.statement_engine.v2_router import route_pdf
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
spec_by_layout = dict(getattr(DEFAULT_REGISTRY, "_specs", {}))
if not spec_by_layout:
    for spec in DEFAULT_REGISTRY.specs():
        spec_by_layout[spec.layout_id] = spec

_DET = re.compile(r"detector:([a-z_]+):([A-Z_]+)")

n = 0
with open(out_path, "a", encoding="utf-8") as out:
    for sha, (path, exp, folder) in items:
        if sha in done:
            continue
        rec = {"sha8": sha, "folder": folder, "exp": exp}
        t0 = time.time()
        try:
            r = route_pdf(path, DEFAULT_REGISTRY)
            ex = (r.result.metadata.extras or {}) if r.result else {}
            det = [m.groups() for n_ in r.notes for m in [_DET.search(n_)] if m]
            rec.update({
                "status": r.status,
                "fb": r.fallback_reason or "",
                "layout": ex.get("layout_id") or r.layout_id or "",
                "spec_bank": (spec_by_layout.get(ex.get("layout_id") or r.layout_id or "")
                              and getattr(spec_by_layout[ex.get("layout_id") or r.layout_id], "bank_key", "")) or "",
                "det_bank": det[0][0] if det else "",
                "det_conf": det[0][1] if det else "",
                "verdict": ex.get("verdict"),
                "reasons": ex.get("verdict_reasons") or [],
                "rows": len(r.result.transactions) if r.result else 0,
                "ms": round((time.time() - t0) * 1000),
            })
        except Exception as e:
            rec.update({"status": "err", "err": str(e)[:120], "ms": round((time.time() - t0) * 1000)})
        out.write(json.dumps(rec) + "\n")
        out.flush()
        n += 1
        if n % 25 == 0:
            print("done", n, flush=True)
print("TOTAL", n)
