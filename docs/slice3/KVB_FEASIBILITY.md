# KVB (Karur Vysya Bank) — Wave-10 feasibility study — NO-GO

Settles the Wave-5 vs Phase-6 disagreement about what the uncovered KVB files contain.
All counts measured on `devin/wave10` over the corpus folder `Karur Vysya Bank`
(71 readable files; 4 already route under `KVB_LAYOUT_1`, 67 `bank_unconfirmed`).

## Question

- Wave 5 said: transaction rows are `(cid:N)` glyph dumps — no decodable text.
- Phase 6 said: 19/20 files have ToUnicode and text is `(key:value)` paren cells — a tokenization problem.

## Evidence (counts only, masked)

Under `read_pages` (pdfplumber — the engine's actual path), all 67 `bank_unconfirmed` files:

- Every page carries ~300 decodable chars (Verdana furniture: `Account Statement`, account header)
  plus ~2,600 `(cid:N)` chars — the entire transaction table.
- `(cid:)` chars all come from one font: `VerdanaBold`, a subset `Type0`/`CIDFontType2`,
  `/Encoding /Identity-H`, `/CIDToGIDMap /Identity`.
- `/ToUnicode` IS present as a reference (`/ToUnicode N 0 R`) — **but the stream is EMPTY**
  (length 0) on every file checked (5/5 sampled). Phase 6's "has ToUnicode" was technically right
  (reference exists) but the stream carries no mappings — reconciling both reports.
- The embedded TTF subset has **no `cmap` and no `post` table** (directory: cvt/fpgm/glyf/head/
  hhea/hmtx/loca/maxp/name/prep only) — glyph indices cannot be inverted to unicode from the font.
- PyMuPDF does not decode the body font either (emits raw codepoints); the one font per file with a
  non-empty ToUnicode (~1,170 bytes) is `Verdana` — the furniture font.
- No `(key:value)` paren-cell text observed under pdfplumber on any of the 67 — the Phase-6 sample
  likely drew from the 4 decodable files (different generator; they already route `KVB_LAYOUT_1`,
  3 VERIFIED).

## Verdict: NO-GO for a tokenizer/layout in this wave

There is no programmatic cid→unicode path: no ToUnicode content, no font cmap, no post names.
The remaining avenue (glyph-shape matching / OCR) is out of scope and disallowed.

## Even if text were solved, evidence still gates

The 67 files print no KVB marker (brand sits inside the CID body font). `bank_evidence` would have
to come from the detector, which scores `kvb:LOW:23` — below the confident gate — so every file
would still fall back `bank_unconfirmed`. Serving them is additionally blocked by detector strength,
not just decoding. Detector data is out of bounds for this track.

## Residual value

`KVB_LAYOUT_1` continues to serve the decodable minority (4 files, 3 VERIFIED) and refuses the rest
honestly (`bank_unconfirmed`/`no_layout`). No change needed.
