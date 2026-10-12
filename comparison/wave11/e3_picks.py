# Wave11 E3: deterministic file picks per eligible spec (2 VERIFIED + 2 REVIEW + 1 any),
# sha-sorted; plus sha8->path index for the corpus.
import json, collections, hashlib, os, sys

P8 = r"X:\Airco Projects\Airco Insights fintech\wt-p8c\comparison\phase8c"
CORPUS = r"X:\Airco Projects\Airco Insights fintech\Unified All Statements"
OUT = r"X:\Airco Projects\Airco Insights fintech\wt-w11\comparison\wave11"
sys.path.insert(0, r"X:\Airco Projects\Airco Insights fintech\wt-w11\backend")
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
L2S = {lid: s.bank_key for lid, s in DEFAULT_REGISTRY._specs.items()}

ELIGIBLE = ["hdfc", "sbi", "axis", "idfc", "paytm", "indusind", "citibank", "city_union"]

after = [json.loads(l) for f in ("after_0.jsonl", "after_1.jsonl", "after_2.jsonl")
         for l in open(os.path.join(P8, f), encoding="utf-8")]

# v2 records per spec
by_spec = collections.defaultdict(list)
for r in after:
    if r["status"] == "v2":
        by_spec[L2S.get(r["layout"])].append(r)

# sha8 -> full pdf path (index the corpus once; cache to disk)
IDX = os.path.join(OUT, "sha8_index.json")
if os.path.exists(IDX):
    idx = json.load(open(IDX))
else:
    idx = {}
    for root, _, files in os.walk(CORPUS):
        for fn in files:
            if not fn.lower().endswith(".pdf"):
                continue
            p = os.path.join(root, fn)
            try:
                h = hashlib.sha256()
                with open(p, "rb") as fh:
                    for c in iter(lambda: fh.read(1 << 20), b""):
                        h.update(c)
                idx[h.hexdigest()[:8]] = p
            except OSError:
                pass
    json.dump(idx, open(IDX, "w"))

picks = {}
for spec in ELIGIBLE:
    recs = sorted(by_spec[spec], key=lambda r: r["sha"])
    ver = [r for r in recs if r["verdict"] == "VERIFIED"]
    rev = [r for r in recs if r["verdict"] == "REVIEW"]
    rest = [r for r in recs if r["verdict"] not in ("VERIFIED", "REVIEW")]
    sel = (ver[:2] + rev[:2] + (ver[2:3] + rev[2:3] + rest)[:1])[:5]
    if len(sel) < 5:  # top up with next sha-sorted files of any verdict
        have = {r["sha"] for r in sel}
        sel += [r for r in recs if r["sha"] not in have][:5 - len(sel)]
    for r in sel:
        r["path"] = idx.get(r["sha"])
    picks[spec] = sel
    miss = [r["sha"] for r in sel if not r["path"]]
    print(f"{spec}: {len(sel)} picks ({sum(1 for r in sel if r['verdict']=='VERIFIED')}V "
          f"{sum(1 for r in sel if r['verdict']=='REVIEW')}R) missing_paths={miss}")

json.dump({s: [{"sha": r["sha"], "verdict": r["verdict"], "folder": r["folder"],
               "layout": r["layout"], "rows": r.get("rows"), "path": r["path"]}
              for r in sel] for s, sel in picks.items()},
          open(os.path.join(OUT, "e3_picks.json"), "w"), indent=1)
