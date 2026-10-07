# Slice 3B - shared extraction engine

HDFC V2 (3A) is now configuration + a layout-neutral engine.

```
statement_engine/
  extraction/            layout-neutral machinery (no bank names)
    layout_spec.py       LayoutSpec: the only thing a bank/layout provides
    words.py anchors.py rows.py normalize.py summary.py checks.py engine.py
    pdf_extractor.py     pdfplumber glue (LayoutExtractor, read_pages)
    registry.py          LayoutRegistry + header-based detect() (DB-backed registry = slice 3C)
  extractors/hdfc/       HDFC layout A spec + thin bindings/re-exports (backwards compatible imports)
  extractors/registry.py DEFAULT_REGISTRY
```

## What a layout provides (LayoutSpec)
Column title token sequences, left-to-right text columns (date first, narration second, optional reference / secondary
date), debit/credit/balance money column roles, date and amount patterns, printed period regex and format, summary
marker + label text + printed field order (any subset of opening / Dr count / Cr count / debits / credits / closing),
whether the header repeats on every page, optional account label and IFSC pattern.

## Behaviour guarantees
- HDFC output is byte-identical to Slice 3A on 92 real files (hash of every row, metadata, checks, failures).
- The engine package contains no bank names or HDFC column words (enforced by a test).
- Proven with three synthetic non-HDFC layouts: different column sets/order (credit left of debit), no reference
  column, month-name dates, other period formats, header on every page, partial or absent summaries.

## Not supported yet (needs new engine capability, decided from the layout census)
Single signed amount column, Dr/Cr suffix amounts, ruled-table (line-based) extraction, left-aligned amounts,
headerless continuation detection without a period line, wrapped two-line headers.
