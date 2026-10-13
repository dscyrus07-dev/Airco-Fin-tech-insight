"""verify2 audit: independent re-check of routed files.
Method (own implementation, prompt-28): extract via router, then independently:
  - count dated amount-bearing text lines vs rows read
  - recompute the forward balance chain from the first row
  - implied opening (row0.bal - side) and closing (last bal) vs printed anchors found by a
    GENERIC label scan (not the spec's regexes): any line containing opening/closing/total
    label text followed by an amount, on the same or the next line; Dr/Dr./DR suffix negates.
usage: python tools/verify2/audit2.py <backend_dir> <sha8-list|run.jsonl> <out.jsonl> [--seed=N] [--per-bank=K]"""
import json, os, re, sys, glob, random
from decimal import Decimal

backend, src, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
seed, per_bank = 29, 40
for a in sys.argv[4:]:
    if a.startswith("--seed="): seed = int(a[7:])
    elif a.startswith("--per-bank="): per_bank = int(a[11:])

sys.path.insert(0, backend)
os.environ.setdefault("STATEMENT_ENGINE_V2_MODE", "shadow")
from app.services.statement_engine.v2_router import route_pdf
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extraction.pdf_extractor import read_pages
from app.services.statement_engine.extraction.words import group_lines, squash

here = os.path.dirname(os.path.abspath(__file__))
mani = {}
for m in glob.glob(os.path.join(here, ".local", "manifest_*.jsonl")):
    for ln in open(m, encoding="utf-8"):
        d = json.loads(ln)
        mani[d["sha8"]] = d["path"]

DATE = re.compile(r"^\d{2}[-/.]\d{2}[-/.]\d{2,4}$|^\d{2}\s?-?\s?[A-Za-z]{3}\s?-?\s?\d{2,4}$")
AMT_ANY = re.compile(r"-?[\d,]+\.\d{1,2}(?:\s*(?:cr|dr)\.?)?", re.I)
OPEN_LBL = re.compile(r"(?i)opening\s*balance|opening\s*bal|b/?f")
CLOSE_LBL = re.compile(r"(?i)closing\s*balance|closing\s*bal|c/?f(?=[\d.-])")
TOT_LBL = re.compile(r"(?i)total\s*(debit|debits|credit|credits|withdrawal|withdrawals|deposit|deposits)|^total(?=[\d,.\-])")
BARE_TOTAL = re.compile(r"(?i)^total(?=[\d,.\-])")
AMT_LINE = re.compile(r"^-?[\d,]+(?:\.\d{1,2})?(?:\s?[cd]r\.?)?$|^-?$|^₹-?[\d,]+", re.I)

def to_dec(s):
    neg = bool(re.search(r"(?i)dr\.?\s*$", s))
    v = Decimal(re.sub(r"[^\d.\-]", "", s.replace(",", "")))
    return -v if neg else v

def _amt_after(text, pos):
    """First amount token starting at/after character position pos."""
    m = AMT_ANY.search(text, pos)
    return to_dec(m.group(0)) if m else None

def anchor_values(pages):
    """Every (kind, page, value): amount taken right AFTER its own label so co-located
    open/close labels on one squashed line cannot cross-read each other's figure."""
    vals = []
    for pi, p in enumerate(pages):
        lines = [squash(l) for l in group_lines(p.words)]
        for i, sq in enumerate(lines):
            mo = OPEN_LBL.search(sq)
            if mo:
                v = _amt_after(sq, mo.end())
                if v is None and i + 1 < len(lines):
                    v = _amt_after(lines[i + 1], 0)
                if v is not None:
                    vals.append(("open", pi, v))
            mc = CLOSE_LBL.search(sq)
            if mc:
                v = _amt_after(sq, mc.end())
                if v is None and i + 1 < len(lines):
                    v = _amt_after(lines[i + 1], 0)
                if v is not None:
                    vals.append(("close", pi, v))
            if TOT_LBL.search(sq):
                amts = [to_dec(a) for a in AMT_ANY.findall(sq)]
                vals.append(("totals", pi, amts))
                if BARE_TOTAL.match(sq) and amts:
                    vals.append(("close", pi, amts[-1]))
    return vals

def dated_amount_lines(pages):
    n = 0
    for p in pages:
        for l in group_lines(p.words):
            toks = [w.text.strip() for w in l]
            if any(DATE.match(t) for t in toks[:3]) and sum(1 for t in toks if AMT_LINE.match(t)) >= 2:
                n += 1
    return n

if src.endswith(".jsonl"):
    cand = [json.loads(ln) for ln in open(src, encoding="utf-8")]
    cand = [r for r in cand if r.get("verdict") == "VERIFIED"]
    random.seed(seed); random.shuffle(cand)
    by = {}
    for r in cand:
        by.setdefault(r["folder_bank"], []).append(r)
    sample = [r for rs in by.values() for r in rs[:per_bank]]
else:
    sample = [{"sha8": s.strip(), "folder_bank": ""} for s in open(src, encoding="utf-8") if s.strip()]

out = open(out_path, "w", encoding="utf-8")
for r in sample:
    s8, path = r["sha8"], mani.get(r["sha8"])
    rec = {"sha8": s8, "flags": []}
    try:
        res = route_pdf(path, DEFAULT_REGISTRY)
        ex = res.result
        txns = list(ex.transactions or [])
        rec["rows"] = len(txns)
        rec["verdict"] = ex.verification_status
        pages = read_pages(path)
        rec["dated_amt_lines"] = dated_amount_lines(pages)
        if rec["dated_amt_lines"] < len(txns):
            rec["flags"].append("rows_gt_dated_lines")
        # chain recompute
        breaks = 0
        for a, b in zip(txns, txns[1:]):
            side = (b.credit or Decimal(0)) - (b.debit or Decimal(0))
            if abs(b.balance - a.balance - side) > Decimal("0.011"):
                breaks += 1
        rec["chain_breaks"] = breaks
        if breaks:
            rec["flags"].append(f"chain_breaks:{breaks}")
        # anchors
        anch = anchor_values(pages)
        if txns:
            r0, rN = txns[0], txns[-1]
            imp_open = r0.balance - (r0.credit or Decimal(0)) + (r0.debit or Decimal(0))
            imp_close = rN.balance
            rec["implied_open"], rec["implied_close"] = str(imp_open), str(imp_close)
            opens = [v for k, _, v in anch if k == "open"]
            closes = [v for k, _, v in anch if k == "close"]
            rec["printed_open"], rec["printed_close"] = [str(v) for v in opens], [str(v) for v in closes]
            if opens and not any(abs(v - imp_open) <= Decimal("0.011") for v in opens):
                rec["flags"].append("open_anchor_mismatch")
            if closes and not any(abs(v - imp_close) <= Decimal("0.011") for v in closes):
                rec["flags"].append("close_anchor_mismatch")
            if not opens and not closes:
                rec["flags"].append("no_printed_anchors_found")
    except Exception as e:
        rec["flags"].append("audit_error:" + type(e).__name__)
    out.write(json.dumps(rec) + "\n")
    out.flush()
out.close()
print("audited", len(sample))
