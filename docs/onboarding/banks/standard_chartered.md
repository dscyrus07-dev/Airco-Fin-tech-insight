# standard_chartered — onboarding notes

Status: **SHADOW_ONLY** — detection 91.9% (<100% gate); 24/182 v2 FAILED on chain/side/totals; audit 30/30 clean

Folders: Standard Chartered Bank
Files: 245 pdf | 210 text | 1 scanned | 34 locked

## Fingerprints

distinct fingerprints: 3 | top share: 99.0%
- `date/narration/ref/credit/debit/balance` x208
- `narration/narration` x1
- `date/date/date/narration/debit/credit/balance` x1

## Current behaviour (V2_MODE=shadow)

- probed: 210 | detected-correct: 91.9% (wrong: 5, none: 12)
- tier: {'v2': 182, 'fallback': 28} | rows read: 28030
- verdicts: {'VERIFIED': 158, 'FAILED': 24}
- fallback reasons: {'foreign_bank': 22, 'no_layout': 6}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 30 of 158 VERIFIED | ok: 30 | disagreements: 0


## unblock-1 re-measure (devin/unblock-1)

Own-marker addition only: `IFSC:SCBL` joined `STANDARDCHARTERED` on `SCB_LAYOUT_1`/`_2` (the account block's
`IFSC : SCBLxxxx` label+code — these prints carry no brand wordmark). That single piece of own evidence
lifts the foreign-refusal on files whose address block names another bank ("NEAR ICICI BANK ATM") or whose
narration wraps carry counterparty IFSCs, and re-enables detection where the markerless doc had none.

- v2 routed: 191 of 196 measured (was 178) | VERIFIED 168 (was 155) | FAILED 23 | no_layout 5
- recovered VERIFIED incl. the `NEAR ICICI BANK ATM` address family and the yearless `BALANCE FORWARD` prints
- still no_layout (4 + 1 payslip): the detector picks `paytm` (MEDIUM, from counterparty `@paytm` narration)
  when the address line `6-3-1090, ...` is read as a date and ends the issuer block before the IFSC line —
  detector/engine gap, not marker-fixable within bank-owned scope. `93a468a8` is a payslip (non-statement, correct)
- FAILED 23: honest — printed TOTAL/opening/closing numbers that do not reconcile with the printed rows,
  schema errors, and multi-section/merged documents
- cross-bank: 0 foreign accepts on 364 pooled files (10 scb-layout hits, all own folder)
- audit: 168 VERIFIED re-checked, 0 disagreements
- stays **SHADOW_ONLY** (FAILED share + locked/scanned remainder keep the gates unmet)

## N5 pass (branch devin/n5-bank-wave)

- `balance_optional=True` on `SCB_LAYOUT_1` (inherited by L2 via `replace`): fee/charge-back rows print a
  Withdrawal with no restated running balance.
- `ifsc_re` (`SCBL0[0-9A-Z]{6}`) on L1/L2: own-IFSC evidence for the layout router's page-1 header zone.
- Folder re-measure (196 files): VERIFIED 168 -> **171**, REVIEW 0 -> 2, FAILED 23 -> **18**, fallback 5.
- New VERIFIEDs audited: 92fb833c, c68862e9, f21e03fc — 0 chain breaks; implied closes match printed.
- Remaining FAILED (18): dominated by the undated multi-line NACH block variant — an amount-bearing undated
  line under a dated row is consumed as continuation narration before `undated_rows_inherit_date` can row it
  (engine ordering, class F); plus duplicated "Page 1 of 1" pages and print-level total/balance
  inconsistencies (class D). `962bc5b5`: undated `0.31` GST charge-component line (class A).
- Remaining fallback (5): `93a468a8` payslip (correct refusal — not a statement); `1c74ce20`, `39f70bde`,
  `5f025201`, `a881906e` — account blocks carry `IFSC: SCBL0036075` but the detector's head zone ends one
  line early on a street-address line that reads date-like (`6-3-1090, ...`), while counterparty
  `PAYTM PAYMENTS BANK` narration leaks 28 pts of paytm evidence. Engine-side head-cut (class F);
  the files fall to legacy safely.
- Cross-bank: 0 wrong-bank accepts / 403 pooled routes (shared N4 probe + indusind-wave probe).
- Gates: detection 192/196 = 98.0% (<100%), yield 173/196 = 88.2% (<90%), VERIFIED 171/196 = 87.2% pass ->
  stays **SHADOW_ONLY**.
