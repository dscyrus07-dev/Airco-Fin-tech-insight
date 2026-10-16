"""verify4 e2e selection: stratified pick per bank from recount shards.
usage: python tools/verify4/select4.py <bank> <n_v> <shard_glob>...
prints sha8s: all R/F/fb/unsup + first n_v VERIFIED."""
import json, sys, collections
bank, n_v, globs = sys.argv[1], int(sys.argv[2]), sys.argv[3:]
fs = [json.loads(l) for g in globs for l in open(g) if json.loads(l).get("folder_bank") == bank]
v = [r["sha8"] for r in fs if r.get("verdict") == "VERIFIED" and r.get("status") == "v2"][:n_v]
o = [r["sha8"] for r in fs if not (r.get("verdict") == "VERIFIED" and r.get("status") == "v2")]
for s in v + o: print(s, end=" ")
print()
