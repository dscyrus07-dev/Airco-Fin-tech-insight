# uco â€” onboarding notes

Status: **SHADOW_ONLY**

Folders: UCO Bank
Files: 11 pdf | 11 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 3 | top share: 72.7%
- `date/narration/ref/srno/debit/credit/balance` x8
- `date/narration/credit/balance` x2
- `date/narration/debit/credit/balance` x1

## Current behaviour (V2_MODE=shadow)

- probed: 11 | detected-correct: 100.0% (wrong: 0, none: 0)
- tier: {'fallback': 11} | rows read: 0
- verdicts: {}
- fallback reasons: {'other_bank:uco': 11}
- cross-bank false accepts on pooled other-bank files: 0

## Notes (post-onboarding measure)

- NEW specs `UCO_LAYOUT_1` (with instrument-no column) + `UCO_LAYOUT_2` (without) registered;
  `uco` detector entry added (UCBA / uco bank names).
- Post-spec folder measure (11 text): 8 v2 (4 REVIEW self-derived chain, 4 FAILED chain+side —
  real reconciliation mismatches, not spec crashes), 2 no_layout (landscape fingerprint uncovered),
  1 other fallback.
- Detector identifies uco VERY_HIGH on all measured files.

## promote-1 changes

- `row_order="auto"` on L1/L2: newest-first exports (15/99/176-row files) now reverse on
  unbroken-reversed-chain evidence -> 3 FAILED(chain+side) became REVIEW.
- `opening_balance_re`/`closing_balance_re` widened (`:?`, 1-2 decimals): 3 docs now surface
  a REAL document inconsistency -- printed closing contradicts the doc's own table
  (opening reconciles, all dated lines extracted, chain intact) -> honest FAILED.
- UCO_LAYOUT_3 (CHQ.NO. col, wrapped WITHDRAW/ALS, left-aligned amounts, `x.xx CR` balance
  suffix): routes `eb3419dc` but its amount cells are space-only glyphs in the text layer
  (162/248 rows balance-only) -> FAILED, engine/PDF-extraction gap.
- UCO_LAYOUT_4 (dd-MMM-yyyy dates, integer amounts): routes `14ab1185` -> FAILED on genuine
  chain breaks at out-of-order date segments (multi-segment doc, engine gap).
- Result: 5 REVIEW + 4 FAILED (was 4 REVIEW + 3 FAILED + 2 fallback). Yield 55.6% < 90%,
  corpus 9 files -> SHADOW_ONLY.
