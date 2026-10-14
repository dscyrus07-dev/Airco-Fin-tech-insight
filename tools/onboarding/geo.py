# geo.py — sanitized word-geometry dump for spec authoring (N1).
# Prints ONLY generic column-label words / date shapes / amount shapes / the bank's
# own name, each with rounded x0-x1; everything else prints W@x0-x1.
# usage: python geo.py <sha8> [page] [top_from] [top_to]
import os, sys, json, glob, re

HERE = os.path.dirname(__file__)
LOCAL = os.path.join(HERE, ".local")
GENERIC = set("""date narration particulars description details remarks txn transaction
cheque chq ref reference no number value withdrawal withdrawals deposit deposits
debit debits credit credits amount balance opening openingbalance closing
closingbalance total totals dr cr statement period account customer ifsc ifsccode
branch page name address type mode transfer upto from to ason summary
broughtforward carriedforward forward brought sl sr sno serial sr.no s.no
instrument num code bank ltd limited india indian of and the a an inr rs rupees
charges charge interest payment paid received self post val dt tran cr/dr dr/cr d/c
""".split())
manifest = {}
for f in glob.glob(os.path.join(LOCAL, "manifest*.jsonl")):
    for ln in open(f, encoding="utf-8"):
        try:
            j = json.loads(ln); manifest[j["sha8"]] = j["path"]
        except Exception:
            pass
sha8 = sys.argv[1]
page_no = int(sys.argv[2]) if len(sys.argv) > 2 else 0
t0 = float(sys.argv[3]) if len(sys.argv) > 3 else 0
t1 = float(sys.argv[4]) if len(sys.argv) > 4 else 400
BANK = set(w.lower() for w in sys.argv[5:])
path = manifest.get(sha8)
if not path:
    print("sha8 not in manifest"); sys.exit(1)
import pdfplumber
AMT = re.compile(r"^-?[\d,]+\.\d{2}$|^-?\d[\d,]*\.\d{2}(?:\s?(?:Dr|Cr)\.?)?$", re.I)
DATE = re.compile(r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}$|^\d{1,2}[-\s][A-Za-z]{3,9}[-\s,]?\d{2,4}$|^\d{4}-\d{2}-\d{2}$")

def san(t):
    tl = t.lower().rstrip(".")
    if tl in GENERIC or tl in BANK: return tl
    if DATE.match(t): return "#DATE"
    if AMT.match(t): return "#AMT"
    if re.match(r"^[\d,]+$", t): return "#"
    return "W"

with pdfplumber.open(path) as pdf:
    ws = pdf.pages[page_no].extract_words()
lines = {}
for wd in ws:
    if t0 <= wd["top"] <= t1:
        key = round(wd["top"] / 3.0)
        lines.setdefault(key, []).append(wd)
for key in sorted(lines):
    ws2 = sorted(lines[key], key=lambda w: w["x0"])
    print(f"y={int(lines[key][0]['top'])}: " + "  ".join(f"{san(w['text'])}@{int(w['x0'])}-{int(w['x1'])}" for w in ws2))
