"""Validate the OCR tier on REAL scanned statements, which have no answer key.

    # 1. GPU, slow, once: OCR every scan with BOTH readers into a local cache (never committed: tmp/ is ignored)
    PYTHONPATH=backend python tools/ocr_eval/real_scan_eval.py ocr \
        --root "Unified All Statements" --cache tmp/ocr_real_cache --url http://localhost:8090 [--per-bank 3]
    # 2. CPU, fast, as often as the engine changes: evaluate the cache offline
    PYTHONPATH=backend python tools/ocr_eval/real_scan_eval.py eval --cache tmp/ocr_real_cache --out tmp/ocr_real_report

The cache is the backend's `mock:` fixture format (<sha256>.json), so STATEMENT_ENGINE_OCR_URL=mock:<cache> also
replays real scans through the whole app with no GPU.

Correctness without ground truth comes from the statement itself:
  - the balance chain: every balance must follow from the previous one plus or minus the row's amount;
  - the printed anchors: opening/closing balance and printed totals must agree with the rows;
  - two independent readers: the VL model's tables (layer "blocks") and the line recogniser (layer "lines") are read
    from ONE ocr call; where both serve, they are compared row by row.
Each chain break is classified (digit misread, digit dropped/extra, decimal shift, side flip, balance misread) from the
values, but only the CLASS is reported.

PRIVACY: real statements. The cache holds document content and stays on this machine. Everything this script PRINTS or
WRITES outside the cache is restricted to whitelisted fields: sha8, bank folder, page counts, timings, codes, check
statuses, counts, and column-title roles (which are lexicon words by construction). No filename, path, narration, name,
account number, date or amount is ever written. See test_real_scan_eval.py, which asserts this.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

LAYERS = ("blocks", "lines")


# ------------------------------------------------------------------ discovery
def iter_scans(root: str, banks: Optional[Iterable[str]] = None) -> List[Tuple[str, str]]:
    """(bank_folder, path) for every PDF under <root>/<bank>/OCR/, ordered round-robin across banks so that a run
    stopped early still covers every bank. Within a bank the order is a stable hash of the path, not the filename."""
    want = set(banks or [])
    per: Dict[str, List[str]] = defaultdict(list)
    for bank in sorted(os.listdir(root)):
        bdir = os.path.join(root, bank)
        if not os.path.isdir(bdir) or (want and bank not in want):
            continue
        for sub in os.listdir(bdir):
            if sub.lower() != "ocr":
                continue
            for dp, _dn, fns in os.walk(os.path.join(bdir, sub), followlinks=True):
                per[bank] += [os.path.join(dp, f) for f in fns if f.lower().endswith(".pdf")]
    for b in per:
        per[b].sort(key=lambda p: hashlib.sha256(p.encode()).hexdigest())
    out, i = [], 0
    while any(i < len(v) for v in per.values()):
        for b in sorted(per):
            if i < len(per[b]):
                out.append((b, per[b][i]))
        i += 1
    return out


def _page_count(path: str) -> Optional[int]:
    try:
        import pikepdf
        with pikepdf.open(path) as pdf:
            return len(pdf.pages)
    except Exception:
        return None


def _read_index(cache: str) -> List[Dict[str, Any]]:
    p = os.path.join(cache, "index.jsonl")
    if not os.path.exists(p):
        return []
    return [json.loads(l) for l in open(p) if l.strip()]


# ------------------------------------------------------------------ 1. OCR into the cache (GPU)
def cmd_ocr(a) -> None:
    os.environ["STATEMENT_ENGINE_OCR_URL"] = a.url
    from app.services.statement_engine.ocr import client
    from app.services.statement_engine.ocr.contracts import document_to_dict

    os.makedirs(a.cache, exist_ok=True)
    index = _read_index(a.cache)
    seen = {r["sha256"] for r in index}
    per_bank = Counter(r["bank"] for r in index)
    t0, n = time.monotonic(), 0
    with open(os.path.join(a.cache, "index.jsonl"), "a") as idx:
        for bank, path in iter_scans(a.root, a.banks):
            if a.per_bank and per_bank[bank] >= a.per_bank:
                continue
            if a.budget_hours and time.monotonic() - t0 > a.budget_hours * 3600:
                print(f"budget reached after {n} documents; re-run to continue")
                break
            raw = open(path, "rb").read()
            sha = hashlib.sha256(raw).hexdigest()
            if a.sha and not any(sha.startswith(s) for s in a.sha):
                continue                                   # subset re-OCR: only requested sha prefixes
            if sha in seen:                                  # duplicate content, or already cached
                continue
            pages = _page_count(path)
            rec: Dict[str, Any] = {"sha256": sha, "sha8": sha[:8], "bank": bank, "pages": pages}
            if pages and pages > client.max_pages():
                rec.update(status="skipped", reason="OCR_TOO_MANY_PAGES")
            else:
                t = time.monotonic()
                doc = client.ocr_pdf(path, None, verify=True, vl=True, page_count=pages)   # both readers, one call
                rec["ocr_s"] = round(time.monotonic() - t, 1)
                if doc.error:
                    rec.update(status="ocr_error", reason=doc.error)
                else:
                    with open(os.path.join(a.cache, sha + ".json"), "w") as fh:
                        json.dump(document_to_dict(doc), fh)
                    rec.update(status="cached", failed_pages=len(doc.failed_pages), vl=bool(getattr(doc, "engine", "")))
            idx.write(json.dumps(rec) + "\n")
            idx.flush()
            seen.add(sha)
            per_bank[bank] += 1
            n += 1
            print(f"{rec['sha8']} {bank:28s} pages={pages} {rec['status']:9s} {rec.get('ocr_s', '')}")
    print(f"done: {n} documents this run")


# ------------------------------------------------------------------ 2. offline evaluation (CPU)
def _rows(res) -> List[Dict[str, Any]]:
    u = res.universal
    if not (u and u.outcome):
        return []
    return [{"date": r.txn.date, "debit": r.txn.debit, "credit": r.txn.credit, "balance": r.txn.balance}
            for r in u.outcome.rows]


def _digits(v: Decimal) -> str:
    return str(abs(v).quantize(Decimal("0.01"))).replace(".", "")


def _amount_error_class(true: Decimal, read: Decimal) -> str:
    t, r = _digits(true), _digits(read)
    if len(t) == len(r) and sum(1 for x, y in zip(t, r) if x != y) == 1:
        return "digit_misread"
    if len(t) == len(r) and sorted(t) == sorted(r):
        return "digits_transposed"
    if abs(len(t) - len(r)) == 1:
        longer, shorter = (t, r) if len(t) > len(r) else (r, t)
        if any(longer[:i] + longer[i + 1:] == shorter for i in range(len(longer))):
            return "digit_dropped_or_extra"
    for k in (10, 100):
        if read == true * k or true == read * k:
            return "decimal_shift"
    return "other"


def classify_breaks(rows: List[Dict[str, Any]]) -> Counter:
    """Classes of the balance-chain breaks in printed row order (or reverse, whichever chains better).
    Values are used here and never leave this function."""
    def run(seq):
        out = Counter()
        for i in range(1, len(seq)):
            p, cur = seq[i - 1], seq[i]
            if p["balance"] is None or cur["balance"] is None:
                continue
            dr, cr = cur["debit"] or Decimal(0), cur["credit"] or Decimal(0)
            exp = p["balance"] - dr + cr
            if exp == cur["balance"]:
                continue
            if p["balance"] + dr - cr == cur["balance"]:
                out["side_flip"] += 1
            elif i + 1 < len(seq) and seq[i + 1]["balance"] is not None and (
                    exp - (seq[i + 1]["debit"] or 0) + (seq[i + 1]["credit"] or 0) == seq[i + 1]["balance"]):
                out["balance_misread"] += 1
            else:
                read = dr or cr
                true = abs(cur["balance"] - p["balance"])
                out["amount_" + _amount_error_class(true, read) if read else "amount_missing"] += 1
        return out
    fwd, rev = run(rows), run(list(reversed(rows)))
    return fwd if sum(fwd.values()) <= sum(rev.values()) else rev


def cross_validate(a: List[Dict[str, Any]], b: List[Dict[str, Any]]) -> Dict[str, int]:
    """Pair rows by (date, balance); compare amount and side. Counts only."""
    pool: Dict[Tuple, List[Dict[str, Any]]] = defaultdict(list)
    for r in b:
        pool[(r["date"], r["balance"])].append(r)
    out = Counter(rows_a=len(a), rows_b=len(b))
    for r in a:
        cands = pool.get((r["date"], r["balance"]))
        if not cands:
            out["only_a"] += 1
            continue
        o = cands.pop(0)
        out["matched"] += 1
        side_a, side_b = ("dr" if r["debit"] else "cr"), ("dr" if o["debit"] else "cr")
        amt_a, amt_b = (r["debit"] or r["credit"]), (o["debit"] or o["credit"])
        if side_a != side_b:
            out["side_disagree"] += 1
        elif amt_a != amt_b:
            out["amount_disagree"] += 1
        else:
            out["agree"] += 1
    out["only_b"] = sum(len(v) for v in pool.values())
    return dict(out)


def _layer_summary(res) -> Dict[str, Any]:
    u = res.universal
    meta = (u.meta if u else None) or {}
    checks = meta.get("check_results") or {}
    chain_detail = {}
    if u and u.outcome and u.outcome.checks and "chain" in u.outcome.checks.results:
        d = u.outcome.checks.results["chain"].detail or {}
        chain_detail = {"rows_checked": d.get("rows_checked"), "breaks": d.get("breaks")}
    ver = res.verification
    titles = meta.get("header_titles") or ""
    return {                                    # WHITELIST: nothing here can carry statement content
        "served": bool(res.ok), "verdict": res.verdict, "code": res.code, "pre_cap": meta.get("checks_verdict"),
        "rows": len(u.outcome.rows) if (u and u.outcome) else 0,
        "checks": {k: v for k, v in checks.items() if isinstance(v, str)},
        "chain": chain_detail,
        "verification": {"status": ver.status, "confirmed": ver.confirmed, "unconfirmed": ver.unconfirmed,
                         "low_confidence": ver.low_confidence},
        "failed_pages": len(res.failed_pages), "rows_dropped": sum(res.rows_dropped.values()),
        "fused": res.fused_amounts, "layer": res.layer, "layer_note": res.layer_note or None,
        # roles only ("debit", "balance", ...): the matched title words are lexicon entries, but roles are enough
        "header_roles": sorted(p.split(":", 1)[0].strip() for p in titles.split("|") if ":" in p),
    }


def _anchored(s: Dict[str, Any]) -> bool:
    c = s["checks"]
    return s["served"] and c.get("chain") == "pass" and (c.get("reference") == "pass" or c.get("totals") == "pass")


def tier(layers: Dict[str, Dict[str, Any]], cross: Optional[Dict[str, int]]) -> str:
    served = [s for s in layers.values() if s["served"]]
    if not served:
        return "R"
    full_agree = bool(cross) and cross.get("agree", 0) == cross.get("rows_a", -1) == cross.get("rows_b", -2)
    if any(_anchored(s) for s in served):
        return "A+" if (len(served) == 2 and full_agree) else "A"
    if any(s["checks"].get("chain") == "pass" for s in served):
        return "B"
    return "C"


def evaluate_one(path: str, bank: str) -> Dict[str, Any]:
    from app.services.statement_engine.ocr.contracts import document_from_dict
    from app.services.statement_engine.ocr.reader import read_document

    hint = "Unknown bank" if bank.lower() in ("other_unknown", "unknown") else bank
    layers, rows, breaks = {}, {}, {}
    for layer in LAYERS:
        with open(path) as fh:
            doc = document_from_dict(json.load(fh))        # fresh copy per layer: reading mutates the document
        res = read_document(doc, bank_hint=hint, layer=layer)
        layers[layer] = _layer_summary(res)
        rows[layer] = _rows(res)
        breaks[layer] = dict(classify_breaks(rows[layer])) if rows[layer] else {}
    cross = cross_validate(rows["blocks"], rows["lines"]) if (rows["blocks"] and rows["lines"]) else None
    return {"layers": layers, "breaks": breaks, "cross": cross, "tier": tier(layers, cross)}


def cmd_eval(a) -> None:
    os.makedirs(a.out, exist_ok=True)
    docs_path = os.path.join(a.out, "docs.jsonl")
    done = set()
    if os.path.exists(docs_path) and not a.fresh:
        done = {json.loads(l)["sha256"] for l in open(docs_path) if l.strip()}
    elif a.fresh and os.path.exists(docs_path):
        os.remove(docs_path)
    t0, n = time.monotonic(), 0
    with open(docs_path, "a") as out:
        for rec in _read_index(a.cache):
            if rec.get("status") != "cached" or rec["sha256"] in done:
                continue
            if a.budget_s and time.monotonic() - t0 > a.budget_s:
                print(f"budget reached after {n}; re-run to continue")
                break
            r = evaluate_one(os.path.join(a.cache, rec["sha256"] + ".json"), rec["bank"])
            r.update(sha256=rec["sha256"], sha8=rec["sha8"], bank=rec["bank"], pages=rec.get("pages"),
                     ocr_s=rec.get("ocr_s"))
            out.write(json.dumps(r, default=str) + "\n")
            out.flush()
            n += 1
    write_report(a.cache, a.out)
    print(f"evaluated {n} this run; report in {a.out}")


# ------------------------------------------------------------------ report (whitelisted aggregates)
def _pct(x, n):
    return f"{100.0 * x / n:.1f}%" if n else "n/a"


def write_report(cache: str, out_dir: str) -> Dict[str, Any]:
    docs = [json.loads(l) for l in open(os.path.join(out_dir, "docs.jsonl")) if l.strip()]
    index = _read_index(cache)
    tiers = Counter(d["tier"] for d in docs)
    per_bank: Dict[str, Counter] = defaultdict(Counter)
    for d in docs:
        per_bank[d["bank"]][d["tier"]] += 1
    layer_stats = {}
    for layer in LAYERS:
        served = [d for d in docs if d["layers"][layer]["served"]]
        codes = Counter(d["layers"][layer]["code"] for d in docs if not d["layers"][layer]["served"])
        brk = Counter()
        for d in docs:
            brk.update(d["breaks"].get(layer) or {})
        roles = Counter(" ".join(d["layers"][layer]["header_roles"]) or "(no header)"
                        for d in docs if not d["layers"][layer]["served"])
        layer_stats[layer] = {"served": len(served), "refusal_codes": dict(codes.most_common()),
                              "break_classes": dict(brk.most_common()),
                              "refused_header_roles": dict(roles.most_common(12)),
                              "rows_served": sum(d["layers"][layer]["rows"] for d in served)}
    both = [d for d in docs if d["cross"]]
    cross = Counter()
    for d in both:
        cross.update({k: v for k, v in d["cross"].items()})
    ver = Counter()
    for d in docs:
        v = d["layers"]["blocks"]["verification"]
        if v["status"] in ("ran", "partial"):
            ver.update({"confirmed": v["confirmed"], "unconfirmed": v["unconfirmed"], "low_confidence": v["low_confidence"]})
    secs = sorted(r["ocr_s"] / r["pages"] for r in index if r.get("ocr_s") and r.get("pages"))
    report = {
        "documents": len(docs), "tiers": dict(tiers),
        "per_bank": {b: dict(c) for b, c in sorted(per_bank.items())},
        "layers": layer_stats,
        "cross_validation": {"documents_read_by_both": len(both),
                             "fully_agreeing_documents": sum(1 for d in both if d["tier"] == "A+" or (
                                 d["cross"].get("agree") == d["cross"].get("rows_a") == d["cross"].get("rows_b"))),
                             **dict(cross)},
        "second_reader_amounts": dict(ver),
        "ocr_seconds_per_page": {"p50": secs[len(secs) // 2] if secs else None,
                                 "p95": secs[int(len(secs) * 0.95)] if secs else None},
        "index": dict(Counter(r.get("status") for r in index)),
    }
    with open(os.path.join(out_dir, "report.json"), "w") as fh:
        json.dump(report, fh, indent=1, default=str)
    n = len(docs)
    md = ["# OCR on REAL scanned statements (no answer key)", "",
          f"Documents evaluated: **{n}**. Every figure below is a count, a code or a check status — no statement "
          "content.", "",
          "| tier | meaning | documents |", "|---|---|---|"]
    meaning = {"A+": "chain + printed totals reconcile, and both readers agree on every row",
               "A": "chain + printed totals reconcile", "B": "chain reconciles, no printed totals to check",
               "C": "read, but the chain does not fully reconcile", "R": "refused by both readers"}
    md += [f"| {t} | {meaning[t]} | {tiers.get(t, 0)} ({_pct(tiers.get(t, 0), n)}) |" for t in ("A+", "A", "B", "C", "R")]
    md += ["", "| reader | served | rows | top refusals | chain-break classes |", "|---|---|---|---|---|"]
    for layer in LAYERS:
        s = layer_stats[layer]
        md.append(f"| {layer} | {s['served']}/{n} | {s['rows_served']} | "
                  f"{', '.join(f'{k} {v}' for k, v in list(s['refusal_codes'].items())[:4]) or '-'} | "
                  f"{', '.join(f'{k} {v}' for k, v in list(s['break_classes'].items())[:4]) or '-'} |")
    c = report["cross_validation"]
    md += ["", f"Read by both readers: {c['documents_read_by_both']}; fully agreeing: {c['fully_agreeing_documents']}; "
               f"rows agreeing {c.get('agree', 0)}, amount disagreements {c.get('amount_disagree', 0)}, "
               f"side disagreements {c.get('side_disagree', 0)}.",
           f"OCR seconds/page p50 {report['ocr_seconds_per_page']['p50']}, p95 {report['ocr_seconds_per_page']['p95']}.",
           "", "| bank | " + " | ".join(("A+", "A", "B", "C", "R")) + " |", "|---|---|---|---|---|---|"]
    md += [f"| {b} | " + " | ".join(str(cnt.get(t, 0)) for t in ("A+", "A", "B", "C", "R")) + " |"
           for b, cnt in sorted(per_bank.items(), key=lambda kv: -sum(kv[1].values()))]
    with open(os.path.join(out_dir, "report.md"), "w") as fh:
        fh.write("\n".join(md) + "\n")
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("ocr")
    o.add_argument("--root", required=True)
    o.add_argument("--cache", required=True)
    o.add_argument("--url", required=True)
    o.add_argument("--banks", nargs="*")
    o.add_argument("--per-bank", type=int, default=0, help="stratified sample: at most N new documents per bank")
    o.add_argument("--sha", nargs="*", help="only OCR documents whose sha256 starts with one of these prefixes")
    o.add_argument("--budget-hours", type=float, default=0.0)
    e = sub.add_parser("eval")
    e.add_argument("--cache", required=True)
    e.add_argument("--out", required=True)
    e.add_argument("--budget-s", type=float, default=0.0)
    e.add_argument("--fresh", action="store_true", help="re-evaluate everything (after an engine change)")
    a = ap.parse_args()
    {"ocr": cmd_ocr, "eval": cmd_eval}[a.cmd](a)


if __name__ == "__main__":
    main()
