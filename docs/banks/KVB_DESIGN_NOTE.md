# KVB (Karur Vysya Bank) — CID-encoded transaction rows — PARKED (wave 5)

## Status

**NO-GO for a LayoutSpec field.** The transaction rows in these statements are not text at all
but a sequence of `(cid:N)` glyph dumps. Decoding them is an extraction-layer algorithm
(cid → unicode via the embedded font cmap), not something a declarative field can express.
The existing `kvb_txn_value_brn_particulars_refno_debit_credit_balance` layout stays registered:
it VERIFIES the minority of KVB files whose rows are real text, and harmlessly refuses the rest
(`bank_unconfirmed` / `no_layout`).

## Evidence (masked probe, `comparison/wave5/`)

- Folder `Karur Vysya Bank`: 75 readable files (5 skipped/locked).
- 71/75 files carry `(cid:N)` fused words on the transaction lines. Line profile:
  3–7 words per line, each word a run of `(cid:..)` groups — i.e. **each word is one whole
  table cell** (date, narration, amount…) rendered glyph-by-glyph with no space between glyphs.
- The page furniture reads normally: letterhead, account header, and the statement period line
  (`… a/c NNNNNNNNNNNNNNNN … dd/mm/yyyy to dd/mm/yyyy`) are real text. Only the table body font
  is unmapped.
- Phase 6 reported "19/20 sampled files have a ToUnicode map" — that map exists for *some*
  fonts, but the row font's glyphs still surface as `(cid:N)` through `pdfplumber.extract_words`
  (the extractor path used by `read_pages`), so the effective text layer for the table is
  unreadable.
- Detector outcome on the folder (wave-5 code): `UNKNOWN` ×68, `kvb` LOW ×4, `canara` LOW ×2 —
  the brand sits inside the CID region or never prints, so the detector cannot confirm the bank
  either. Routing: `bank_unconfirmed` ×31, `VERIFIED` ×3 (mixed files whose rows are plain text),
  rest `no_layout`/`FAILED`.

## What a fix would have to do (pre-tokenizer, not a field)

1. In `pdf_extractor.read_pages`, detect `(cid:N)` runs inside words and re-decode them from
   `pdfplumber`'s char stream (`page.chars` carry per-glyph x0/x1 and `fontname`).
2. Build a cid→unicode map for the CID font. Options, in order of honesty:
   - the font's embedded cmap (invert unicode→glyph), if present in the font program;
   - a declared `cid_map` on the spec (i.e. a per-font lookup table learned once from a file
     whose cells ARE readable — the corpus mixes both renderings);
   - hardest: OCR-free glyph-shape matching (do not attempt — no OCR, and shape matching is
     out of scope).
3. Re-emit the decoded cell at the fused word's x-span; downstream layout machinery is
   unchanged.

Estimated reach: ~70 files (`Karur Vysya Bank`). Risk if misbuilt: a wrong cid map produces
*syntactically valid but wrong* numbers — the chain/totals checks would catch most cases, but
this is exactly the class of change that must land behind its own tests, which is why it is
parked rather than hacked into a field.
