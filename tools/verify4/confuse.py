"""pick n files per OTHER bank folder for candidate-confusion runs.
usage: python tools/verify4/confuse.py <manifest_glob> <n_per_bank>
prints <folder_bank>:<sha8,sha8,...>"""
import json, sys, glob, collections, re
n = int(sys.argv[2])
mani = {}
for m in glob.glob(sys.argv[1]):
    for l in open(m, encoding="utf-8"):
        d = json.loads(l); mani[d["sha8"]] = d["path"]
by = collections.defaultdict(list)
for s8, p in mani.items():
    m = re.search(r"Unified All Statements[\/]([^\/]+)", p.replace("\\", "/"))
    if m: by[m.group(1).strip().lower().replace(" ", "_")].append(s8)
for b in sorted(by):
    print(f"{b}:{','.join(by[b][:n])}")
