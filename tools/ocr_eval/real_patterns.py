"""Count the structural failure patterns across every cached real scan, so fixes are ranked by how many real
statements they unblock. PII-safe: prints only pattern names, counts, and LEXICON words (never a token from a
statement — an unknown title is reported as the nearest lexicon entry and its edit distance).

    PYTHONPATH=backend python tools/ocr_eval/real_patterns.py --cache <cache>
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter


def _lev(a: str, b: str, cap: int = 3) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    a = ap.parse_args()
    from app.services.statement_engine.extraction.words import group_lines, norm_token
    from app.services.statement_engine.ocr.contracts import document_from_dict
    from app.services.statement_engine.ocr.grid import page_from_ocr
    from app.services.statement_engine.ocr.html_table import parse_tables_shaped
    from app.services.statement_engine.ocr.line_layer import page_from_lines
    from app.services.statement_engine.universal.lexicon import DATE_SHAPES, HEADER_SYNONYMS

    rxs = [re.compile(p) for _n, p, _f, _t in DATE_SHAPES if p]
    vocab = sorted({t for alts in HEADER_SYNONYMS.values() for alt in alts for t in alt if len(t) >= 4})
    role_of = {t: r for r, alts in HEADER_SYNONYMS.items() for alt in alts for t in alt}
    date_words = {"date", "txndate", "transactiondate", "valuedate", "postingdate", "trandate", "dt"}

    def dated(ln):
        return any(rx.match(w.text.strip()) for w in ln[:4] for rx in rxs)

    pats, near = Counter(), Counter()
    idx = [json.loads(l) for l in open(os.path.join(a.cache, "index.jsonl")) if l.strip()]
    docs = [r for r in idx if r.get("status") == "cached"]
    for rec in docs:
        doc = document_from_dict(json.load(open(os.path.join(a.cache, rec["sha256"] + ".json"))))
        ok = sorted((p for p in doc.pages if p.ok), key=lambda p: p.page)
        if not ok:
            pats["no_usable_page"] += 1
            continue
        for layer, build in (("blocks", page_from_ocr), ("lines", page_from_lines)):
            per = []
            for p in ok[:5]:
                pg = build(p)
                per.append(sum(1 for ln in group_lines(pg.words) if dated(ln)) if pg else 0)
            first = next((i for i, n in enumerate(per) if n >= 4), None)
            if first is None:
                pats[f"{layer}: no page with >=4 dated lines in first 5 pages"] += 1
            elif first > 0:
                pats[f"{layer}: transactions start after page 1 (page {first + 1})"] += 1
        # table-level patterns, from the VL markup. Header checks apply to the FIRST transaction table only:
        # continuation pages legitimately repeat no header.
        seen = set()
        first_table_done = False
        for p in ok[:5]:
            for b in p.blocks:
                if not b.is_table:
                    continue
                for grid, counts in parse_tables_shaped(b.content):
                    if len(grid) < 4:
                        continue
                    titles = [norm_token(c) for c in grid[0]]
                    data = grid[1:]
                    datecol = [c for c in range(len(grid[0]))
                               if sum(1 for r in data if c < len(r) and any(rx.match(r[c].strip().split(" ")[0])
                                                                            for rx in rxs)) >= 2]
                    if not datecol:
                        continue                              # not a transaction table
                    seen.add("txn_table")
                    dc = datecol[0]
                    if not first_table_done:
                        first_table_done = True
                        has_date_title = any(t in date_words or "date" in t for t in titles)
                        roles_in_row0 = {role_of[t] for t in titles if t in role_of}
                        if not has_date_title:
                            above = " ".join(norm_token(w) for bb in p.blocks if not bb.is_table
                                             for w in (bb.content or "").split())
                            seen.add("FIRST txn table: no 'Date' title in row0"
                                     + (" (but 'date' appears in a text block on the page)" if "date" in above else ""))
                        if len(roles_in_row0) >= 3 and not has_date_title:
                            seen.add("FIRST txn table: row0 has other titles but the date column is untitled")
                        if len(roles_in_row0) < 2:
                            seen.add("FIRST txn table: row0 is not a header row at all")
                    filled = sum(1 for r in data if dc < len(r) and r[dc].strip())
                    if filled < 0.6 * len(data):
                        seen.add("date printed on <60% of table rows (carried forward / wrapped rows)")
                    for t in titles:
                        if t and t not in role_of and 5 <= len(t) <= 20 and not any(ch.isdigit() for ch in t):
                            best = min(vocab, key=lambda v: _lev(t, v))
                            d = _lev(t, best)
                            if d <= 2:
                                seen.add("a title is a near-miss of a lexicon word")
                                near[f"{best} (edit distance {d})"] += 1
                    if len(set(counts)) > 1:
                        seen.add("ragged table (rows with different cell counts)")
        for s in seen:
            pats["blocks-table: " + s] += 1
    print(f"documents: {len(docs)}")
    for k, v in pats.most_common():
        print(f"  {v:4d}  {k}")
    if near:
        print("near-miss titles (nearest lexicon word):")
        for k, v in near.most_common(15):
            print(f"  {v:4d}  {k}")


if __name__ == "__main__":
    main()
