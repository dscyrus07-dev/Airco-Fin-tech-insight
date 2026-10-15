# dhanlaxmi — onboarding notes

Status: **SHADOW_ONLY**

Folders: Dhanlaxmi Bank
Files: 15 pdf | 15 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 3 | top share: 53.3%
- `date/date` x8
- `date/date/narration/ref/srno/debit/credit/balance` x5
- `date/srno/narration/debit/amount/credit/amount/balance` x2

## Current behaviour (V2_MODE=shadow)

- probed: 15 | detected-correct: 0.0% (wrong: 0, none: 15)
- tier: {'fallback': 15} | rows read: 0
- verdicts: {}
- fallback reasons: {'no_layout': 15}
- cross-bank false accepts on pooled other-bank files: 0

## Notes (post-onboarding measure)

- NEW spec `dhanlaxmi_date_valuedate_description_chequeno_debits_credits_balance` (fp-B, 5 files) +
  `dhanlaxmi` detector entry (DLXB / dhanbank domains). Detector: VERY_HIGH on all 15 files.
- Real rows print literal `0.00` in the unused debit/credit cell -> `zero_amount_is_empty` set.
- Post-spec measure (15 text): 5 v2 REVIEW, 10 no_layout.
  Uncovered: fp-A x8 (interleaved layout printing the running balance on its OWN line after the row �
  needs a balance-as-continuation capability the engine does not have today -> stayed fallback, not built);
  fp-C x2 (`debit amount | credit amount` titles, `srno` column).
- VERIFIED not reachable yet: routed files are REVIEW (self-derived chain).

## [UB] re-check (fp-A / fp-C)

- fp-A x8 (`Txn Date`/`Value Date`/`Description`/`Cheque-RefNo`/`Txn Amount` titles scattered across
  THREE interleaved header lines): each transaction prints amount+`Dr/Cr` on the narration line ABOVE
  the dated line and the running balance inline as `Balance :  n.nn` text inside the dated row —
  `continuation_amounts` cannot reach backwards and no column anchor exists for the balance. Engine
  gap (needs: above-row amount capture + inline-labelled balance + 3-line header). Parked.
- fp-C x2 (`Date|Cheque/Ref No|Description|Debit Amount|Credit Amount|Balance`, dd/mm/yyyy, `B/F ...`
  opening row, `Total d.dd c.cc` tail): shape is spec-able BUT most data rows print the balance cell
  as a space glyph (empty word at the balance x; digits absent from the text layer). A spec would land
  honest FAILED on missing balances — no gate improvement; not added.
- fp-B x5 remain REVIEW via `dhanlaxmi_date_valuedate_description_chequeno_debits_credits_balance`.
- Yield ceiling ~47% unchanged; status stays SHADOW_ONLY. No engine/spec edits this pass.

## N5

- fp-C (`Date|Cheque/Ref No|Description|Debit Amount|Credit Amount|Balance`, dd/mm/yyyy,
  signed balances): the earlier "space-glyph balance" diagnosis was wrong — both files
  extract cleanly (121 + 61 rows, chain pass). Added `DHANLAXMI_LAYOUT_3`.
- The `B/F ...` opening prints as a dated row whose CREDIT cell repeats the balance, and the
  printed `Total <debits> <credits>` counts it, so the row stays a transaction and the totals
  pair verifies independently (MATCH on both files). No opening/closing labels print ->
  `reference` skipped -> REVIEW ceiling (correct: chain is still self-derived).
- Totals regex is `(?i)^total...` — `flat` preserves case (`Total` not `TOTAL`).
- Result: 9 REVIEW + 2 fallback -> 11 REVIEW, 0 fallback. Yield 11/15 = 73%.
- Cross-bank false accepts: 0. Status stays SHADOW_ONLY.
