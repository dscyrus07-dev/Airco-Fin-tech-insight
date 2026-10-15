"""n6 sampler: stratified seeded sample per legacy-only bank, by page-1 header
fingerprint. Writes tools/n6/.local/<bank>.sample.txt (sha8 list) and
<bank>.fp.jsonl (sha8, fingerprint, kind).

usage: python tools/n6/sample.py <backend_dir> <bank_id> [per_fp_max]
Resumable: fingerprints append to fp.jsonl; re-run skips done sha8s.
"""
import json, os, re, sys, glob, random
from collections import Counter, defaultdict

backend, bank_id = sys.argv[1], sys.argv[2]
per_fp_max = int(sys.argv[3]) if len(sys.argv) > 3 else 8
sys.path.insert(0, backend)

from app.services.statement_engine.extraction.pdf_extractor import read_pages
from app.services.statement_engine.extraction.words import group_lines, squash

here = os.path.dirname(os.path.abspath(__file__))
local = os.path.join(here, ".local")
os.makedirs(local, exist_ok=True)

mani = {}
for m in glob.glob(os.path.join(here, "..", "verify2", ".local", "manifest_*.jsonl")):
    for ln in open(m, encoding="utf-8"):
        d = json.loads(ln)
        mani[d["sha8"]] = d["path"]

folders = json.load(open(os.path.join(here, "..", "verify2", ".local", "folders.json"), encoding="utf-8"))
fol2bank = {f.lower(): i["bank_id"] for f, i in folders.items()}

COL_WORDS = re.compile(r"(?i)^(date|debit|credit|balance|withdrawal|withdrawals|deposit|deposits|description|particulars|narration|amount|txn|transaction|cheque|ref|value|details|dr|cr)$")

def header_sig(path):
    try:
        pages = read_pages(path)
    except Exception as e:
        return ("<unreadable>", type(e).__name__)
    if not pages:
        return ("<empty>",)
    lines = [squash(l) for l in group_lines(pages[0].words)]
    for ln in lines[:40]:
        toks = [t for t in re.split(r"[| ]+", ln) if t]
        hits = sum(1 for t in toks if COL_WORDS.match(t))
        if hits >= 2:
            return ("hdr", ln[:80])
    return ("nohdr", lines[0][:60] if lines else "<blank>")

shas = sorted(s for s, p in mani.items()
              if fol2bank.get(next((f for f in fol2bank
                                    if "/" + f + "/" in p.replace("\\", "/").lower()), "")) == bank_id)

fp_path = os.path.join(local, f"{bank_id}.fp.jsonl")
done = set()
if os.path.exists(fp_path):
    for ln in open(fp_path, encoding="utf-8"):
        done.add(json.loads(ln)["sha8"])

out = open(fp_path, "a", encoding="utf-8")
for i, s8 in enumerate(shas):
    if s8 in done:
        continue
    try:
        sig = header_sig(mani[s8])
    except Exception as e:
        sig = ("<err>", type(e).__name__)
    out.write(json.dumps({"sha8": s8, "fp": sig}) + "\n")
    out.flush()
    if (i + 1) % 100 == 0:
        print(f"{bank_id} fp {i+1}/{len(shas)}", flush=True)

fps = defaultdict(list)
for ln in open(fp_path, encoding="utf-8"):
    d = json.loads(ln)
    fps[json.dumps(d["fp"])].append(d["sha8"])

random.seed(29)
sample = []
for k, members in fps.items():
    random.shuffle(members)
    take = max(1, min(per_fp_max, round(150 * len(members) / len(shas))))
    sample.extend(members[:take])
# fill to 150 round-robin from leftovers so small-fp banks still reach the cap
pool = [s for k, m in fps.items() for s in m if s not in set(sample)]
random.shuffle(pool)
i = 0
while len(sample) < min(150, len(shas)) and i < len(pool):
    sample.append(pool[i]); i += 1
sample = sorted(set(sample))[:150]

samp_path = os.path.join(local, f"{bank_id}.sample.txt")
open(samp_path, "w").write("\n".join(sample))
print(f"{bank_id}: {len(shas)} files, {len(fps)} fingerprints, sample {len(sample)}")
for k, m in sorted(fps.items(), key=lambda kv: -len(kv[1]))[:12]:
    print(f"  {len(m):5} {k[:100]}")
