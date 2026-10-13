# pool_xcheck.py — cross-bank false-accept pool.
# Builds a seeded pool of <=N text files per corpus folder (incl. the 15 existing
# banks and non-bank folders), runs each through route_pdf once in shadow mode,
# and records (sha8, folder, status, layout-bank, detected). One pooled pass
# answers every bank's cross-bank question: "did a file from another folder get
# attributed to me?". Resumable; re-run after detector/spec changes.
import os, sys, json, glob, random

HERE = os.path.dirname(__file__)
LOCAL = os.path.join(HERE, ".local")
BACKEND = os.path.abspath(os.path.join(HERE, "..", "..", "backend"))
sys.path.insert(0, BACKEND)

os.environ.setdefault("STATEMENT_ENGINE_V2_MODE", "shadow")
os.environ.setdefault("STATEMENT_ENGINE_MISMATCH_GUARD", "1")
os.environ["STATEMENT_ENGINE_UNIVERSAL_MODE"] = "off"

from app.services.statement_engine.v2_router import route_pdf
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY as REG

PER_FOLDER = int(sys.argv[1]) if len(sys.argv) > 1 else 10
SEED = 20250628

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

folders = json.load(open(os.path.join(LOCAL, "folders.json")))
ROOT_PREFIX = "unified all statements"
def top_folder(s):
    p = manifest.get(s["sha8"], "")
    low = p.lower().replace("/", "\\")
    i = low.find(ROOT_PREFIX)
    if i < 0: return s["folder"]
    rest = p[i + len(ROOT_PREFIX):].lstrip("\\/")
    return rest.split("\\")[0].split("/")[0] or "(root)"

by_folder = {}
for s in scans:
    if not (s.get("has_text") and not s.get("locked") and not s.get("corrupt")):
        continue
    if s["sha8"] not in manifest: continue
    by_folder.setdefault(top_folder(s), []).append(s["sha8"])

rng = random.Random(SEED)
pool = []
for fold, shas in sorted(by_folder.items()):
    pick = sorted(shas)[:]
    rng.shuffle(pick)
    for sha in pick[:PER_FOLDER]:
        pool.append((sha, fold))

OUT = os.path.join(LOCAL, "xcheck.jsonl")
done = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        try: done.add(json.loads(l)["sha8"])
        except Exception: pass

LAYOUT2BANK = {s.layout_id: s.bank_key for s in REG.specs()}
n = 0
with open(OUT, "a", buffering=1, encoding="utf-8") as out:
    for sha, fold in pool:
        if sha in done: continue
        try:
            r = route_pdf(manifest[sha], REG)
            det = None
            for nt in (r.notes or []):
                if nt.startswith("detector:"):
                    det = nt.split(":")[1] or None
                    if det in ("None", "none"): det = None
            rec = {"sha8": sha, "folder": fold, "status": r.status,
                   "layout": r.layout_id,
                   "layout_bank": LAYOUT2BANK.get(r.layout_id),
                   "fb": r.fallback_reason, "detected": det}
        except Exception as e:
            rec = {"sha8": sha, "folder": fold, "err": type(e).__name__}
        print(json.dumps(rec), file=out)
        done.add(sha)
        n += 1
        if n % 50 == 0:
            print(f"...{n}/{len(pool)}", file=sys.stderr)
print("xchecked", n, "of", len(pool))
