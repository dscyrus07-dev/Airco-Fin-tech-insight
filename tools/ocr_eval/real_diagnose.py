"""PII-safe structural diagnosis of one cached real scan: why did the reader refuse it?

    PYTHONPATH=backend python tools/ocr_eval/real_diagnose.py --cache <cache> --sha8 <sha8> [--layer blocks|lines]

Prints ONLY structure: counts, check statuses, inference codes, column-title roles, and MASKED token shapes —
every digit becomes 9 and every letter A/a, except calendar month names, which are not personal. A date prints as
"99-Apr-9999" and an amount as "9,99,999.99": the format is visible, the value is not. No narration, name,
account number, amount or date value is printed.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

MONTHS = {m.lower() for m in ("Jan Feb Mar Apr May Jun Jul Aug Sep Sept Oct Nov Dec January February March April "
                              "June July August September October November December").split()}
_DATEISH = re.compile(r"\d")
_SEP = re.compile(r"[/\-.]")


def mask(tok: str) -> str:
    parts = re.split(r"([^A-Za-z]+)", tok)
    out = []
    for p in parts:
        if p.isalpha():
            out.append(p if p.lower() in MONTHS else "".join("A" if c.isupper() else "a" for c in p))
        else:
            out.append(re.sub(r"\d", "9", p))
    return "".join(out)


def is_dateish(t: str) -> bool:
    if not _DATEISH.search(t):
        return False
    if _SEP.search(t) and len(t) <= 12 and sum(c.isdigit() for c in t) >= 4:
        return True
    return any(m in t.lower() for m in MONTHS)


def is_amountish(t: str) -> bool:
    return bool(re.fullmatch(r"[-+(]?[\d,]+\.\d{1,2}\)?(?:\s*(?:cr|dr|CR|DR|Cr|Dr))?", t.strip()))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--sha8", required=True)
    ap.add_argument("--layer", choices=("blocks", "lines", "both"), default="both")
    ap.add_argument("--pages", type=int, default=2, help="pages to profile")
    a = ap.parse_args()
    from app.services.statement_engine.extraction.words import group_lines
    from app.services.statement_engine.ocr.contracts import document_from_dict
    from app.services.statement_engine.ocr.grid import pages_from_ocr
    from app.services.statement_engine.ocr.html_table import parse_tables_shaped
    from app.services.statement_engine.ocr.line_layer import page_from_lines
    from app.services.statement_engine.ocr.reader import read_document
    from app.services.statement_engine.universal import infer as I

    idx = [json.loads(l) for l in open(os.path.join(a.cache, "index.jsonl")) if l.strip()]
    rec = next(r for r in idx if r["sha8"] == a.sha8)
    path = os.path.join(a.cache, rec["sha256"] + ".json")
    raw = json.load(open(path))
    doc = document_from_dict(raw)
    print(f"{rec['sha8']}  bank={rec['bank']}  pages={rec['pages']}  ok_pages={sum(1 for p in doc.pages if p.ok)}  "
          f"failed={dict(Counter(p.error for p in doc.pages if not p.ok))}")
    from app.services.statement_engine.universal.lexicon import HEADER_SYNONYMS
    from app.services.statement_engine.extraction.words import norm_token
    vocab = {t for alts in HEADER_SYNONYMS.values() for alt in alts for t in alt}

    def title_mask(cell: str) -> str:
        """a header cell: lexicon words shown (they are column titles by definition), anything else masked"""
        return " ".join(w if norm_token(w) in vocab else mask(w) for w in cell.split()) or "''"

    for p in doc.pages[:a.pages]:
        labels = Counter(b.label for b in p.blocks)
        print(f"  p{p.page}: blocks={dict(labels)} lines={len(p.lines)}")
        for b in p.blocks:
            if not b.is_table:
                continue
            for grid, counts in parse_tables_shaped(b.content):
                ncol = max(counts) if counts else 0
                print(f"     table {len(grid)}r x {ncol}c  cells/row={dict(Counter(counts))}")
                if grid:
                    print(f"       row0: " + " | ".join(title_mask(c) for c in grid[0])[:160])
                for c in range(ncol):
                    col = Counter(" ".join(mask(w) for w in (r[c] if c < len(r) else "").split())[:24] or "''"
                                  for r in grid[1:])
                    top = ", ".join(f"{k} x{v}" for k, v in col.most_common(2))
                    print(f"       col{c}: {top}"[:150])
    layers = ("blocks", "lines") if a.layer == "both" else (a.layer,)
    for layer in layers:
        d2 = document_from_dict(json.load(open(path)))
        res = read_document(d2, layer=layer)
        u = res.universal
        meta = (u.meta if u else None) or {}
        print(f"\n[{layer}] verdict={res.verdict} code={res.code} pre_cap={meta.get('checks_verdict')}")
        print(f"  checks={meta.get('check_results')}")
        print(f"  header_roles={sorted(x.split(':')[0].strip() for x in (meta.get('header_titles') or '').split('|') if ':' in x)}"
              f" date_shape={meta.get('date_shape')} amount_form={meta.get('amount_form')} money={meta.get('money')}"
              f" chain_frac={meta.get('chain_frac')} rows_sample={meta.get('rows_sample')}")
        notes = [n for n in (u.notes if u else []) if not any(ch.isdigit() for ch in n.split(':', 1)[-1][:0])]
        print(f"  notes={[n for n in notes if len(n) < 60][:10]}")
        if u and u.outcome:
            per_page = Counter(r.page for r in u.outcome.rows)
            print(f"  rows per engine page: {dict(sorted(per_page.items()))}")
            if u.outcome.checks:
                ch = u.outcome.checks.results.get("chain")
                if ch:
                    print(f"  chain: rows_checked={ch.detail.get('rows_checked')} breaks={ch.detail.get('breaks')}")
        # what the inference sees on engine page 1
        okp = [p for p in d2.pages if p.ok]
        pages = (pages_from_ocr(okp) if layer == "blocks"
                 else [pg for pg in (page_from_lines(p) for p in sorted(okp, key=lambda p: p.page)) if pg])
        if pages:
            lines = group_lines(pages[0].words)
            toks = [w.text for ln in lines for w in ln]
            ds = Counter(mask(t) for t in toks if is_dateish(t))
            am = Counter(mask(t) for t in toks if is_amountish(t))
            shape = I.infer_date_shape(lines)
            print(f"  page1: lines={len(lines)} words={len(toks)} date-like shapes={dict(ds.most_common(6))}")
            print(f"         amount-like shapes={dict(am.most_common(5))} chosen_date_shape="
                  f"{shape['name'] + '(' + str(shape['hits']) + ')' if shape else None}")
            first_dated = next((i for i, ln in enumerate(lines) if any(is_dateish(w.text) for w in ln[:3])), None)
            if first_dated is not None:
                ln = lines[first_dated]
                print(f"         first dated line #{first_dated}: {len(ln)} words, masked: "
                      + " ".join(mask(w.text) for w in ln)[:150])


if __name__ == "__main__":
    sys.exit(main())
