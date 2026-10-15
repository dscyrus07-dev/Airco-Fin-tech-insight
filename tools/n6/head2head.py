"""n6 head-to-head: legacy parser path vs v2 engine (shadow) + spec-independent
audit of BOTH outputs on the same file.

usage: python tools/n6/head2head.py <backend_dir> <bank_id> [--limit=N]
Reads sha8s from tools/n6/.local/<bank>.sample.txt; appends PII-free records to
tools/n6/.local/<bank>.h2h.jsonl (resumable: done sha8s skipped).

Per file:
  legacy: pdf_validator -> structure_validator -> parser -> transaction_validator
          -> DataIntegrityGuard(strict)  (the exact step objects production uses;
          classify/recurring/aggregate/Excel are downstream of extraction and
          do not change row data)
  v2:     route_pdf(path, DEFAULT_REGISTRY) under shadow mode
  audit:  dated amount-lines vs rows; forward balance chain recomputed;
          first/last balance vs printed anchors (generic label scan) — run
          identically on legacy and v2 row sets.
"""
import json, os, re, sys, glob, inspect, importlib, random
from decimal import Decimal
from collections import Counter, defaultdict

backend, bank_id = sys.argv[1], sys.argv[2]
limit = None
for a in sys.argv[3:]:
    if a.startswith("--limit="): limit = int(a[8:])
sys.path.insert(0, backend)
os.environ.setdefault("STATEMENT_ENGINE_V2_MODE", "shadow")

from app.services.statement_engine.v2_router import route_pdf
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.extraction.pdf_extractor import read_pages
from app.services.statement_engine.extraction.words import group_lines, squash
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.banks._shared.base_processor import BaseBankProcessor

here = os.path.dirname(os.path.abspath(__file__))
local = os.path.join(here, ".local")
mani = {}
for m in glob.glob(os.path.join(here, "..", "verify2", ".local", "manifest_*.jsonl")):
    for ln in open(m, encoding="utf-8"):
        d = json.loads(ln)
        mani[d["sha8"]] = d["path"]

# ---- legacy processor discovery -------------------------------------------
mod = importlib.import_module(f"app.services.banks.{bank_id}.processor")
PROC_CLS = next(c for _, c in inspect.getmembers(mod, inspect.isclass)
                if issubclass(c, BaseBankProcessor) and c is not BaseBankProcessor
                and issubclass(c, BaseBankProcessor) and "Error" not in c.__name__)

# ---- shared audit pieces (same regexes/logic as tools/verify2/audit2.py) ----
DATE = re.compile(r"^\d{0,4}\d{2}[-/.]\d{2}[-/.]\d{2,4}$|^\d{2}\s?-?\s?[A-Za-z]{3}\s?-?\s?\d{2,4}$")
AMT_ANY = re.compile(r"-?[\d,]+\.\d{1,2}(?:\s*\(?(?:cr|dr)\.?\)?)?", re.I)
OPEN_LBL = re.compile(r"(?i)opening\s*balance|opening\s*bal|b/?f")
CLOSE_LBL = re.compile(r"(?i)closing\s*balance|closing\s*bal|c/?f(?=[\d.-])")
TOT_LBL = re.compile(r"(?i)total\s*(debit|debits|credit|credits|withdrawal|withdrawals|deposit|deposits)|^total(?=[\d,.\-])")
BARE_TOTAL = re.compile(r"(?i)^total(?=[\d,.\-])")
AMT_LINE = re.compile(r"^-?[\d,]+(?:\.\d{1,2})?\s?\(?[cd]r\.?\)?$|^-?[\d,]+(?:\.\d{1,2})?$|^-?$|^-?[\d,]+$", re.I)

def to_dec(s):
    neg = bool(re.search(r"(?i)dr\.?\s*$", s))
    v = Decimal(re.sub(r"[^\d.\-]", "", s.replace(",", "")))
    return -v if neg else v

def _amt_after(text, pos):
    m = AMT_ANY.search(text, pos)
    return to_dec(m.group(0)) if m else None

def anchor_values(pages):
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
    return vals

def dated_amount_lines(pages):
    n = 0
    for p in pages:
        for l in group_lines(p.words):
            toks = [w.text.strip() for w in l]
            if any(DATE.match(t) for t in toks[:3]) and sum(1 for t in toks if AMT_LINE.match(t)) >= 2:
                n += 1
    return n

def dec(v):
    if v in (None, ""): return None
    try: return Decimal(str(v).replace(",", ""))
    except Exception: return None

def norm_rows(txns):
    """list of (debit, credit, balance) Decimals from either v2 txn objects or legacy dicts."""
    out = []
    for t in txns:
        if not isinstance(t, dict):
            d = t.to_dict() if hasattr(t, "to_dict") else getattr(t, "__dict__", {})
        else:
            d = t
        debit = dec(d.get("debit") or d.get("withdrawal") or d.get("withdrawals"))
        credit = dec(d.get("credit") or d.get("deposit") or d.get("deposits"))
        if debit is None and credit is None:
            amt = dec(d.get("amount"))
            side = str(d.get("type") or d.get("dr_cr") or d.get("txn_type") or "").lower()
            if amt is not None:
                if side.startswith("cr") or "credit" in side or "dep" in side: credit = amt
                elif side.startswith("dr") or "debit" in side or "with" in side: debit = amt
        bal = dec(d.get("balance"))
        out.append((debit, credit, bal))
    return out

def audit_rows(rows, anchors, dated_lines):
    """spec-independent: chain recompute + anchor agreement. Returns dict."""
    flags, breaks = [], 0
    bals = [r[2] for r in rows]
    for a, b in zip(rows, rows[1:]):
        if a[2] is None or b[2] is None:
            continue
        side = (b[1] or Decimal(0)) - (b[0] or Decimal(0))
        if abs(b[2] - a[2] - side) > Decimal("0.011"):
            breaks += 1
    if breaks: flags.append(f"chain_breaks:{breaks}")
    if dated_lines < len(rows): flags.append("rows_gt_dated_lines")
    implied_open = implied_close = None
    if rows and rows[0][2] is not None:
        implied_open = rows[0][2] - (rows[0][1] or Decimal(0)) + (rows[0][0] or Decimal(0))
    if rows and rows[-1][2] is not None:
        implied_close = rows[-1][2]
    opens = [v for k, _, v in anchors if k == "open"]
    closes = [v for k, _, v in anchors if k == "close"]
    if implied_open is not None and opens and all(abs(v - implied_open) > Decimal("0.011") for v in opens):
        flags.append("open_anchor_mismatch")
    if implied_close is not None and closes and all(abs(v - implied_close) > Decimal("0.011") for v in closes):
        flags.append("close_anchor_mismatch")
    return {"rows": len(rows), "chain_breaks": breaks, "flags": flags,
            "implied_open": str(implied_open) if implied_open is not None else None,
            "implied_close": str(implied_close) if implied_close is not None else None}

def legacy_leg(path):
    # strict_mode=False mirrors production (pipeline_orchestrator runs legacy
    # processors non-strict: integrity failures warn, workbook still ships)
    proc = PROC_CLS(strict_mode=False)
    pdf = proc.pdf_validator.validate(path)
    text = getattr(pdf, "text_content", "") or ""
    struct = proc.structure_validator.validate(text, getattr(pdf, "first_page_text", None))
    meta = getattr(struct, "metadata", None)
    parse = proc.parser.parse(path, text)
    txns_raw = list(getattr(parse, "transactions", None) or [])
    dicts = [t.to_dict() if hasattr(t, "to_dict") else t for t in txns_raw]
    val = proc.transaction_validator.validate(dicts)
    if isinstance(val, tuple):
        validated = val[0]
    else:
        validated = getattr(val, "validated_transactions", dicts)
    validated = [v.to_dict() if hasattr(v, "to_dict") else v for v in validated]
    ig = DataIntegrityGuard(strict_mode=False).validate(
        validated,
        expected_count=getattr(meta, "expected_transaction_count", None),
        expected_opening_balance=_f(getattr(meta, "opening_balance", None) or getattr(parse, "opening_balance", None)),
        expected_closing_balance=_f(getattr(meta, "closing_balance", None) or getattr(parse, "closing_balance", None)),
        expected_total_credits=_f(getattr(parse, "total_credits", None)),
        expected_total_debits=_f(getattr(parse, "total_debits", None)),
    )
    return {"rows": len(validated), "integrity_passed": bool(ig.is_valid),
            "integrity_failed_checks": [c.name for c in ig.checks
                                        if getattr(c, "status", None) and c.status.value == "failed"],
            "txns": validated,
            "opening": getattr(parse, "opening_balance", None),
            "closing": getattr(parse, "closing_balance", None)}

def _f(v):
    try: return float(str(v).replace(",", "")) if v not in (None, "") else None
    except Exception: return None

SPEC_KEY = {"bank_of_baroda": "bob"}.get(bank_id, bank_id)

def v2_leg(path):
    # scoped to the bank's own specs = the production serve path (route_pages with
    # spec_key); the detector leg is exercised separately by the xbank probe.
    res = route_pdf(path, DEFAULT_REGISTRY, bank_key=SPEC_KEY, use_detector=False)
    ex = res.result
    txns = []
    if ex:
        for t in ex.transactions or []:
            txns.append({"debit": getattr(t, "debit", None), "credit": getattr(t, "credit", None),
                         "balance": getattr(t, "balance", None)})
    return {"status": res.status, "layout": res.layout_id or "",
            "fallback": getattr(res, "fallback_reason", "") or "",
            "verdict": getattr(ex, "verification_status", None) if ex else None,
            "rows": len(txns), "txns": txns}

sample = [l.strip() for l in open(os.path.join(local, f"{bank_id}.sample.txt")) if l.strip()]
if limit: sample = sample[:limit]
out_path = os.path.join(local, f"{bank_id}.h2h.jsonl")
done = {json.loads(l)["sha8"] for l in open(out_path)} if os.path.exists(out_path) else set()
out = open(out_path, "a", encoding="utf-8")

for i, s8 in enumerate(sample):
    if s8 in done: continue
    path = mani.get(s8)
    rec = {"sha8": s8}
    if not path:
        rec["error"] = "no_path"
    else:
        try:
            pages = read_pages(path)
            anchors = anchor_values(pages)
            dated = dated_amount_lines(pages)
            rec["dated_amt_lines"] = dated
            rec["anchors_n"] = len(anchors)
        except Exception as e:
            rec["error"] = f"pages:{type(e).__name__}"
            pages, anchors, dated = None, [], None
        if pages is not None:
            try:
                leg = legacy_leg(path)
                lr = norm_rows(leg["txns"])
                rec["leg"] = {"rows": leg["rows"], "integrity_passed": leg["integrity_passed"],
                              "integrity_failed_checks": leg["integrity_failed_checks"],
                              **audit_rows(lr, anchors, dated)}
                rec["leg"]["rows"] = leg["rows"]
            except Exception as e:
                rec["leg"] = {"error": type(e).__name__}
            try:
                v2 = v2_leg(path)
                v2r = norm_rows(v2["txns"])
                rec["v2"] = {"status": v2["status"], "layout": v2["layout"],
                             "fallback": v2["fallback"], "verdict": v2["verdict"],
                             "rows": v2["rows"], **audit_rows(v2r, anchors, dated)}
            except Exception as e:
                rec["v2"] = {"error": type(e).__name__}
    out.write(json.dumps(rec) + "\n")
    out.flush()
    if (i + 1) % 20 == 0:
        print(f"{bank_id} {i+1}/{len(sample)}", flush=True)
print(f"{bank_id} done")
