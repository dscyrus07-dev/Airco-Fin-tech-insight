# ippb â€” onboarding notes

Status: **SHADOW_ONLY**

Folders: India Post Payments Bank
Files: 6 pdf | 6 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 2 | top share: 83.3%
- `date/date/narration/credit/balance` x5
- `srno/srno/srno/srno/srno/srno/srno` x1

## Current behaviour (V2_MODE=shadow)

- probed: 6 | detected-correct: 100.0% (wrong: 0, none: 0)
- tier: {'fallback': 6} | rows read: 0
- verdicts: {}
- fallback reasons: {'other_bank:ippb': 5, 'no_layout': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Notes (post-onboarding measure)

- NEW spec `ippb_date_tranid_transaction_particulars_withdrwal_deposit_balance` + `ippb` detector
  entry (IPOS / "India Post Payments Bank"). Header title literally prints "WITHDRWAL".
- Post-spec folder measure (6 text): 5 v2 all REVIEW (self-derived chain — opening line folds into
  rows), 1 no_layout (second fingerprint uncovered).
- Detector identifies ippb VERY_HIGH on the routed files.

## unblock-1 update

- `opening_balance_re` widened to `OpeningBalance:?` — the printed label carries a colon
  (`OpeningBalance:20.02Cr.`). Opening anchor now detectable, but `anchor_full=True` still requires
  the closing/totals end.
- Closing end unparseable at spec level: summary prints labels
  (`OPENING BALANCE|TOTAL WITHDRAWALS|TOTAL DEPOSITS|CLOSING BALANCE|No. of Transactions`) then a
  5-value line whose amounts merge ambiguously when squashed (e.g. `20.0221,94622,205279.0227`),
  and `No. of Transactions` maps to no `PrintedSummary` field -> engine gap (needs a
  column-skipping summary parse or positional value-row parse). REVIEW ceiling stands.
- `5128847f` is a custom-encoded-font PDF: transaction text extracts as garbage glyphs -> excluded
  as unreadable (class D), not a parser failure.
- Status: **SHADOW_ONLY** — det 100% (6/6), yield 5/5 v2 REVIEW, VERIFIED unreachable, thin corpus.

## N5 re-check

- Re-measured: 4 v2 REVIEW + 1 no_layout (`5128847f`, CID-garbage font, class D) â€” unchanged.
- No spec change; SHADOW_ONLY stands.
