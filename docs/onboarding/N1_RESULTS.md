# N1 results — header/marker capabilities, per bank

Base `5be615d`, branch `devin/n1-engine-headers`. All measures shadow-mode
(`measure2.py`), same sha8 lists before/after (folders under the corpus root).
Nothing promoted; every new layout stays shadow-only.

## Totals (same file sets)

| Bank | Files | v2 before → after | VERIFIED | REVIEW | FAILED | fallback |
|---|---|---|---|---|---|---|
| idbi | 83 | 45 → **65** | 15 → 15 | 20 → 22 | 10 → 28 | 38 → 18 |
| yes | 92 | 87 → **88** | 33 → **34** | 34 → 34 | 20 → 20 | 5 → 4 |
| central_bank | 34 | 31 → **32** | 2 → 2 | 24 → 25 | 5 → 5 | 3 → 2 |
| pnb | 82 | 71 → **81** | 0 → 0 | 71 → **76** | 0 → 5 | 11 → 1 |

No previously-routed file changed: every diff is `fallback → v2`.

## Per bank

### idbi — `IDBI_LAYOUT_3` (3-line header + `Dr.`/`Cr.` side markers)
- 20 files moved `no_layout → v2` on the new layout: 2 REVIEW, 18 FAILED, 0 VERIFIED.
- FAILEDs are chain/side breaks — several fixtures print `0.00` in every balance
  cell (redacted corpus) and can never reconcile; FAILED is the honest verdict.
- Remaining fallbacks: 18 (10 `bank_unconfirmed`, 7 `no_layout` other shapes,
  1 `foreign_bank`).
- Audit: 15/15 VERIFIED files pass independent audit (row completeness, chain,
  opening/closing anchors). Cross-bank: 0 foreign accepts.

### yes — `YES_LAYOUT_5` (3-line interleaved header, multi-word dates)
- `008a966b`: `no_layout → v2`, **VERIFIED**, 327 rows.
- Audit: 15/15 VERIFIED ok. Cross-bank: 0.

### central_bank — `CBI_LAYOUT_4` (15-column × 3-line, mid-word splits)
- `459f15b8`: `no_layout → v2`, REVIEW (13 rows; no independent anchor).
- Audit: 2/2 VERIFIED ok. Cross-bank: 0.

### pnb — `PNB_LAYOUT_2` / `PNB_LAYOUT_3` (landscape `Transaction|Cheque` family)
- 10 files moved `no_layout → v2`: 5 REVIEW (276–1311 rows), 5 FAILED
  (incl. `f2be0893` 1961 rows, `1c442c0a` 1616 rows — extraction runs, chains
  honestly do not reconcile; candidates stay parked).
- Audit: 0 VERIFIED pool (expected: all candidates are REVIEW/FAILED). Cross-bank: 0.

## Regression & safety

- **734-file corpus compare vs `411f6ca` baseline: 0 diffs** (status, bank,
  layout, verdict, rows).
- Engine unit suite: 446 passed. N1 capability + mutation tests: 27 passed.
- Cross-bank: all 32 N1-layout routings occurred in the correct folders; no
  other-bank file claims an N1 layout, and no N1-family file is claimed by a
  foreign layout.
- Fresh audits (above): 32 files audited across idbi/yes/central_bank, all pass.

## Honest notes for N4

- `IDBI_LAYOUT_3` rows parse and sides are correct, but 18/20 newly routed files
  end FAILED (chains). Root cause observed on `1f8ffc2f`: printed balance column
  is `0.00` on every row — fixture redaction, not a parse bug. N4 should confirm
  with a non-redacted file before relying on the yield count.
- `pnb` 3-line files produce large row counts with schema/chain failures —
  plausibly real layout noise (continuation-line amounts); review-only.
- `date_join_words` was added for YES 3-word dates; it widens the date cell join
  only where opted in.
