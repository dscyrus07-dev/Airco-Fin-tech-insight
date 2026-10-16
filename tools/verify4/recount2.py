"""verify4 gates: readable-only det + yield + vshare, per bank.
unreadable = fallback_reason in (locked, scanned_no_text)."""
import json, sys, glob, collections
rows = [json.loads(l) for p in sys.argv[1:] for g in glob.glob(p) for l in open(g)]
by = collections.defaultdict(list)
for r in rows: by[r.get("folder_bank") or "?"].append(r)
UNREAD = ("locked","scanned_no_text")
print(f"{'bank':<18}{'n':>5}{'unrd':>5}{'detR':>6}{'ylR':>6}{'ylAll':>6}{'V':>4}{'R':>4}{'F':>4}{'vsh':>6}")
for b in sorted(by):
    fs = by[b]; n = len(fs)
    unrd = [r for r in fs if (r.get("fallback_reason") or "") in UNREAD]
    rd = [r for r in fs if (r.get("fallback_reason") or "") not in UNREAD]
    det = sum(1 for r in rd if r.get("status")=="v2")
    v = sum(1 for r in rd if r.get("verdict")=="VERIFIED")
    rv = sum(1 for r in rd if r.get("verdict")=="REVIEW")
    f = sum(1 for r in rd if r.get("verdict")=="FAILED")
    ylr = sum(1 for r in rd if r.get("verdict") in ("VERIFIED","REVIEW") and (r.get("rows") or 0)>0)
    yla = sum(1 for r in fs if r.get("verdict") in ("VERIFIED","REVIEW") and (r.get("rows") or 0)>0)
    vsh = round(100*v/(v+rv),1) if v+rv else None
    print(f"{b:<18}{n:>5}{len(unrd):>5}{round(100*det/max(len(rd),1),1):>6}{round(100*ylr/max(len(rd),1),1):>6}{round(100*yla/n,1):>6}{v:>4}{rv:>4}{f:>4}{vsh!s:>6}")
