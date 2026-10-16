"""stratified pick: nV verified-v2 + nR review + nF failed + nFB fallback + nU unsupported."""
import json, sys, glob, collections
bank, globs = sys.argv[1], sys.argv[2:]
fs = [json.loads(l) for g in globs for p in glob.glob(g) for l in open(p) if json.loads(l).get("folder_bank")==bank]
buckets = collections.defaultdict(list)
for r in fs:
    if r.get("status")=="v2":
        buckets[r.get("verdict") or "none"].append(r["sha8"])
    else:
        buckets[r.get("status")].append(r["sha8"])
out = buckets["VERIFIED"][:5] + buckets["REVIEW"][:3] + buckets["FAILED"][:3] + \
      buckets["fallback"][:3] + buckets["unsupported"][:3]
print(",".join(out))
