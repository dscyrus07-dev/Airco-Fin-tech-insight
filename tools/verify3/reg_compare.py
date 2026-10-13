"""verify3: compare two measure runs field-by-field (status,bank,layout,tier,rows,verdict).
usage: python tools/verify3/reg_compare.py <base_dir_prefix> <now_dir_prefix>
Reads <p>_a|b|c.jsonl or explicit files passed on argv."""
import json, sys, glob

base, now = {}, {}
for f in sys.argv[1:-1] or []:
    pass
pat_b, pat_n = sys.argv[1], sys.argv[2]
for ln in [l for g in glob.glob(pat_b) for l in open(g, encoding='utf-8')]:
    r = json.loads(ln); base[r['sha8']] = r
for ln in [l for g in glob.glob(pat_n) for l in open(g, encoding='utf-8')]:
    r = json.loads(ln); now[r['sha8']] = r

FIELDS = ['status', 'folder_bank', 'layout', 'verdict', 'rows']
diffs = []
for s8 in sorted(set(base) & set(now)):
    a, b = base[s8], now[s8]
    d = {f: (a.get(f), b.get(f)) for f in FIELDS if a.get(f) != b.get(f)}
    # detector tier/confidence inside notes
    ta = next((n.split(':')[1] for n in a.get('notes', []) if n.startswith('detector:')), '')
    tb = next((n.split(':')[1] for n in b.get('notes', []) if n.startswith('detector:')), '')
    if ta != tb:
        d['detect_tier'] = (ta, tb)
    if d:
        diffs.append((s8, d))
missing = sorted(set(base) - set(now) | set(now) - set(base))
print(f"compared={len(set(base) & set(now))} diffs={len(diffs)} missing={missing}")
for s8, d in diffs:
    print(s8, json.dumps(d))
