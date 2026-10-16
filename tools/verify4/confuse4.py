"""verify4 confusion: pick n files per *other* folder_bank to route at candidate.
usage: python tools/verify4/confuse4.py <candidate_bank> <n> <shard_glob>...
prints "otherbank:sha8,sha8,..." lines — run each via e2e4 --override=<candidate>."""
import json, sys, collections
cand, n, globs = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
by = collections.defaultdict(list)
for g in globs:
    for l in open(g):
        d = json.loads(l)
        if d.get("folder_bank") and d["folder_bank"] != cand:
            by[d["folder_bank"]].append(d["sha8"])
for b in sorted(by):
    print(f"{b}:{','.join(by[b][:n])}")
