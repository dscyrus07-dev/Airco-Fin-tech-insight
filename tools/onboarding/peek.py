# peek.py — sanitized structural skeleton of a corpus PDF for spec authoring.
# Prints ONLY: generic column-label words (fixed vocabulary), the bank's own
# name, date shapes (dd/mm/yyyy), amount shapes (#,###.##), and W placeholders
# for everything else. No statement content is emitted.
# usage: python peek.py <sha8> [page_count]
import os, sys, json, glob, re

HERE = os.path.dirname(__file__)
LOCAL = os.path.join(HERE, ".local")

# generic vocabulary that may print verbatim (bank names handled separately)
GENERIC = set("""date narration particulars description details remarks txn transaction
cheque chq ref reference no number value withdrawal withdrawals deposit deposits
debit debitdebits credit credits amount balance opening openingbalance closing
closingbalance total totals dr cr statement period account customer ifsc ifsccode
branch page name address type mode transfer upto from to ason summary
brougforward carriedforward forward brought sl sr sno serial particulars
instrument num code bank ltd limited india indian of and the a an
inr rs rupees charges charge interest payment paid received self
""".split())

manifest = {}
for f in glob.glob(os.path.join(LOCAL, "manifest*.jsonl")):
    for l in open(f, encoding="utf-8"):
        try:
            j = json.loads(l); manifest[j["sha8"]] = j["path"]
        except Exception: pass

sha8 = sys.argv[1]
maxpages = int(sys.argv[2]) if len(sys.argv) > 2 else 3
BANK_WORDS = set(w.lower() for w in sys.argv[3:])
path = manifest.get(sha8)
if not path:
    print("sha8 not in manifest"); sys.exit(1)

import pdfplumber
AMT = re.compile(r"^-?[\d,]+\.\d{2}$|^-?\d[\d,]*\.\d{2}(?:\s?(?:Dr|Cr))?$", re.I)
DATE = re.compile(r"^\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}$|^\d{1,2}[-\s][A-Za-z]{3,9}[-\s,]?\d{2,4}$|^\d{4}-\d{2}-\d{2}$")

def sanitize(tok):
    if AMT.match(tok): return "#AMT"
    if DATE.match(tok): return "#DATE"
    t = re.sub(r"[^a-z]", "", tok.lower())
    if t in GENERIC or t in BANK_WORDS: return t
    if re.fullmatch(r"[A-Z]{4}0[A-Z0-9]{6}", tok): return "#IFSC"
    if tok.isdigit(): return "#"
    # possible bank-name token: keep capitalized alpha words >=4 chars? No - keep
    # only whitelisted; bank identity is shown via detector registry anyway.
    return "W" if tok else "#"

with pdfplumber.open(path) as pdf:
    print(f"sha8={sha8} pages={len(pdf.pages)}")
    for pi, page in enumerate(pdf.pages[:maxpages]):
        txt = page.extract_text() or ""
        print(f"--- page {pi} w={page.width:.0f} h={page.height:.0f} ---")
        for ln in txt.splitlines():
            toks = [sanitize(t) for t in ln.split()]
            if not toks: continue
            print(" ".join(toks)[:160])
