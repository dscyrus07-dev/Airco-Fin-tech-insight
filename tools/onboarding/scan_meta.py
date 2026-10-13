# scan_meta.py — per-file triage scan (resumable, chunked, shardable).
# usage: python scan_meta.py [max_files] [shard] [nshards]
# shard runs every nshards-th path (deterministic); all shards share OUT/manifest safely
# via per-path dedupe (append-only; worst case a dup record, harmless downstream).
import os, sys, json, hashlib, re, glob

ROOT = r"X:\Airco Projects\Airco Insights fintech\Unified All Statements"
SHARD_SUFFIX = f"_{sys.argv[2]}" if len(sys.argv) > 2 else ""
OUT = os.path.join(os.path.dirname(__file__), ".local", f"scan_meta{SHARD_SUFFIX}.jsonl")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend")))

# fixed label vocabulary (generic column labels only)
LABELS = {
    "date": ["date", "txn date", "transaction date", "tran date", "posting date", "post date", "tran. date", "tran"],
    "value_date": ["value date", "valuedate", "value dt", "val dt"],
    "narration": ["narration", "description", "particulars", "transaction details", "details", "remarks", "transaction description", "transaction detail"],
    "ref": ["cheque", "chq", "ref", "chq no", "cheque no", "ref no", "reference", "instrument", "cheque/reference", "chq./ref.", "utr", "rrn"],
    "debit": ["debit", "withdrawal", "withdrawals", "debits", "paid out", "debit amount", "dr amount", "withdrawal amt", "withdrawal amount", "money out", "spent"],
    "credit": ["credit", "deposit", "deposits", "credits", "paid in", "credit amount", "cr amount", "deposit amt", "deposit amount", "money in", "received"],
    "amount": ["amount", "txn amount", "transaction amount", "amt", "amount(inr)", "amount (inr)", "transaction amt"],
    "balance": ["balance", "running balance", "closing balance", "available balance", "balance amount", "bal", "ledger balance"],
    "dr_cr": ["dr/cr", "dr cr", "dr / cr", "type", "d/c", "cr/dr"],
    "branch": ["branch", "branch name", "branch code", "location"],
    "srno": ["s.no", "sr no", "sl no", "no", "s.no.", "sr.no.", "sl.no.", "#"],
    "charges": ["charges", "charge", "fee", "commission"],
    "points": ["reward points", "points"],
}
DATE_RE = re.compile(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$|^\d{1,2}[-\s][A-Za-z]{3}[-\s]\d{2,4}$|^\d{4}-\d{2}-\d{2}$")
AMT_RE = re.compile(r"^\d[\d,]*\.\d{2}$")
OPEN_RE = re.compile(r"opening bal|bal\s*b/?f|brought forward|b/f\b|balance b/f", re.I)
CLOSE_RE = re.compile(r"closing bal|bal\s*c/?f|carried forward|c/f\b|balance c/f", re.I)
NONASCII = re.compile(r"[^\x00-\x7f]")
CUR_RE = re.compile(r"[₹$€£¥]|rs\.?|inr\b|usd\b", re.I)
ACCT_RE = re.compile(r"account\s*(no|number|#)|a/c\s*no|acct", re.I)

def line_sig(words, tol=3.0):
    """Group words into visual lines by top coord."""
    lines = {}
    for w in words:
        key = round(w["top"] / tol)
        lines.setdefault(key, []).append(w)
    return [sorted(ws, key=lambda w: w["x0"]) for ws in sorted(lines.values(), key=lambda ws: ws[0]["top"])]

def norm_label(t):
    t = t.lower().strip()
    for canon, aliases in LABELS.items():
        if t in aliases:
            return canon
    return None

def header_sig(page_words):
    """Find the best header line: line containing >=2 label hits; return ordered canon labels."""
    best = None
    for line in line_sig(page_words):
        lab = []
        for w in line:
            c = norm_label(w["text"])
            if c: lab.append(c)
        if len(lab) >= 2 and (best is None or len(lab) > len(best)):
            best = lab
    return tuple(best) if best else None

def date_fmt(text):
    if re.match(r"\d{4}-\d{2}-\d{2}", text): return "iso"
    if re.match(r"\d{1,2}/\d{1,2}/\d{4}", text): return "d/m/yyyy"
    if re.match(r"\d{1,2}/\d{1,2}/\d{2}\b", text): return "d/m/yy"
    if re.match(r"\d{1,2}-\d{1,2}-\d{4}", text): return "d-m-yyyy"
    if re.match(r"\d{1,2}-\d{1,2}-\d{2}\b", text): return "d-m-yy"
    if re.match(r"\d{1,2}[-\s][A-Za-z]{3}[-\s]\d{2,4}", text): return "d-Mmm-yy(yy)"
    return "other"

def scan_one(path):
    rec = {"path": path}
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    rec["sha8"] = h.hexdigest()[:8]
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            rec["pages"] = len(pdf.pages)
            n_pages = len(pdf.pages)
            sel = sorted(set([0, 1, 2, n_pages - 1] if n_pages > 3 else range(n_pages)))
            all_words = 0
            first_txt = ""
            last_txt = ""
            sig = None
            dated_rows = 0
            continuation = 0
            dated_with_bal = 0
            dated_total = 0
            cur_hits = set()
            acct_hits = 0
            all_txt_parts = []
            for i in sel:
                try:
                    ws = pdf.pages[i].extract_words()
                except Exception:
                    continue
                all_words += len(ws)
                txt = " ".join(w["text"] for w in ws)
                if i == 0: first_txt = txt
                if i == n_pages - 1: last_txt = txt
                if sig is None:
                    s = header_sig(ws)
                    if s: sig = s
                for line in line_sig(ws):
                    texts = [w["text"] for w in line]
                    joined = " ".join(texts)
                    has_date = any(DATE_RE.match(t) for t in texts)
                    if has_date:
                        dated_total += 1
                        amts = [t for t in texts if AMT_RE.match(t)]
                        if len(amts) >= 1: dated_rows += 1
                        if len(amts) >= 2: dated_with_bal += 1
                    elif dated_rows and joined.strip() and not has_date and len(texts) > 2 and not DATE_RE.match(texts[0]):
                        # rough continuation heuristic: short text line right after dated rows
                        if len(joined) < 120: continuation += 1
                for c in CUR_RE.findall(txt): cur_hits.add(c.lower().rstrip('.'))
                acct_hits += len(ACCT_RE.findall(txt))
                all_txt_parts.append(txt)
            joined_all = " ".join(all_txt_parts)
            rec["words_sampled"] = all_words
            rec["has_text"] = all_words > 30
            rec["header_sig"] = list(sig) if sig else None
            rec["date_fmt"] = None
            if joined_all:
                m = DATE_RE.search(joined_all)
                if m: rec["date_fmt"] = date_fmt(m.group(0))
            rec["open_bal"] = bool(OPEN_RE.search(first_txt)) if first_txt else False
            rec["close_bal"] = bool(CLOSE_RE.search(last_txt)) if last_txt else False
            rec["dated_lines"] = dated_total
            rec["dated_multi_amt"] = dated_with_bal
            rec["continuation_lines"] = continuation
            rec["currencies"] = sorted(cur_hits)[:6]
            rec["multi_account_hint"] = acct_hits > 2
            rec["nonascii_share"] = round(len(NONASCII.findall(joined_all)) / max(len(joined_all), 1), 3)
    except Exception as e:
        t = type(e).__name__
        if "password" in str(e).lower() or "encrypted" in str(e).lower() or t in ("PDFPasswordIncorrect", "PdfminerException"):
            rec["locked"] = True
        else:
            rec["corrupt"] = t
    rec["size"] = os.path.getsize(path)
    return rec

def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
    shard = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    nshards = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    paths = sorted(glob.glob(os.path.join(ROOT, "**", "*.pdf"), recursive=True) +
                   glob.glob(os.path.join(ROOT, "*.pdf")))
    paths = [p for i, p in enumerate(paths) if i % nshards == shard]
    done = set()
    man = os.path.join(os.path.dirname(OUT), f"manifest{SHARD_SUFFIX}.jsonl")
    if os.path.exists(man):
        for l in open(man, encoding="utf-8"):
            try: done.add(json.loads(l)["path"])
            except Exception: pass
    n = 0
    with open(OUT, "a", buffering=1, encoding="utf-8") as out, \
         open(man, "a", buffering=1, encoding="utf-8") as m:
        for p in paths:
            if n >= limit: break
            if p in done: continue
            folder = os.path.basename(os.path.dirname(p)) if os.path.dirname(p) != ROOT else "(root)"
            try:
                rec = scan_one(p)
            except Exception as e:
                rec = {"path": p, "sha8": "err-" + hashlib.sha256(p.encode()).hexdigest()[:8], "corrupt": type(e).__name__}
            rec.pop("path")
            rec["folder"] = folder
            print(json.dumps({"sha8": rec["sha8"], "path": p}), file=m)
            print(json.dumps(rec), file=out)
            done.add(p)
            n += 1
    print("scanned", n)

if __name__ == "__main__":
    main()
