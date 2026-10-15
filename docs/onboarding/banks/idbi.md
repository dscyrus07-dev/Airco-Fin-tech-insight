# idbi — onboarding notes

Status: **SHADOW_ONLY**

Folders: IDBI Bank
Files: 119 pdf | 109 text | 6 scanned | 4 locked

## Fingerprints

distinct fingerprints: 13 | top share: 31.2%
- `date/narration/srno/debit/credit/balance` x34
- `srno/date/date/narration/ref/srno` x31
- `date/date/narration/dr_cr/amount/balance` x20
- `date/narration/amount/dr_cr` x11
- `date/narration/ref/ref/date/debit/credit/balance` x2
- `<none>` x2
- `date/date/ref/narration/debit/amount/credit/amount/balance` x2
- `date/narration/ref/srno/debit/credit/balance` x2
- `date/narration/date/debit/credit/balance` x1
- `date/date/ref/srno/narration` x1
- `narration/ref/credit` x1
- `date/date/debit/amount/credit/amount` x1
- ... +1 more

## Current behaviour (V2_MODE=shadow)

- probed: 109 | detected-correct: 72.5% (wrong: 1, none: 29)
- tier: {'v2': 55, 'fallback': 54} | rows read: 27903
- verdicts: {'REVIEW': 31, 'VERIFIED': 15, 'FAILED': 9}
- fallback reasons: {'no_layout': 42, 'bank_unconfirmed': 11, 'foreign_bank': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 15 of 15 VERIFIED | ok: 15 | disagreements: 0

## Unblock pass (prompt-29, current branch)

- new `IDBI_LAYOUT_4`: passbook `Date | Particulars | Cheque No | Debit | Credit | Closing Balance`
  (dd/mm/yy, split `CR`/`DR` balance suffix, `Opening Balance As On <d> :<amt> CR` anchor) -> 2 VERIFIED.
- new `IDBI_LAYOUT_5`: passbook `Date | Particulars | Chq No. | Chq Date | Debit | Credit | Balance`
  (dd-mm-yyyy, merged `Cr` balance suffix, undated `Opening/Closing Balance` in-table anchor lines;
  closing line carries period totals -> regex takes the last `\d+\.dd` before `Cr`). Both corpus files
  route but stay honest FAILED (printed balance missing on rows: 1 row and 1409/2045 rows respectively).
- after: 104 manifest files -> 48 v2 / 46 fallback | 17 VERIFIED / 20 REVIEW / 11 FAILED
  (before: 15 VERIFIED). audit n/a (2 VERIFIED delta only). cross-bank: see run.
- parked `IDBI_LAYOUT_3` (defined, unregistered): the dominant 19-file family
  `Srl|Txn Date|Value Date|Description|Cheque No|CR/DR|CCY|Amount(INR)|Balance(INR)` prints period-suffixed
  `Dr.`/`Cr.` side markers; `normalize.py` marker regex lacks `\.?$` -> every row errors. ENGINE GAP.
- engine gaps left: `Dr.`/`Cr.` marker suffix (19 files), balance-less `Date|Description|Amount|Type`
  family (8 files), markerless/det-deep-page files (bank_unconfirmed+det_none = honest unrouteable).
- misfiled (class D): `3fd73a3a` is an AP Mahesh Bank doc (apmaheshbank.com footer),
  `2cde3656` is a GL ledger print (not a statement). `7dd67f11` carries ICICI evidence -> routed there.

## N5 pass (branch devin/n5-bank-wave)

- Re-measure on N3 tip (83 readable files): VERIFIED 15, REVIEW 22, FAILED 28, fallback 18
  (14 `bank_unconfirmed`, 4 `foreign_bank`).
- L3 `Dr.`-suffix family (18 of the FAILEDs): `row_order="auto"` cannot rescue — both directions
  carry real print gaps with unread=0 (the statement print itself skips rows) -> class D, honest FAILED.
- 8 files on `idbi_date_particulars_chqno_withdrawals_deposits_balance` fail `schema errors: 1`:
  the dated `...,B/F` opening row prints `0.00` in BOTH money cells; `opening_row_balance_only` tests
  raw amounts before `zero_amount_is_empty` empties them, so the row reaches schema with zero sides.
  Engine-ordering gap (class F) — no spec-side fix exists.
- 14 `bank_unconfirmed` + 4 `foreign_bank`: sampled files carry no own-bank header evidence at all
  (`IDBI`/`IBKL` absent from issuer text; IDBI and foreign tokens appear only inside counterparty
  narration) -> correct refusal, class C/E.
- No spec/detector change applied this pass — every residual is class D/F/E. Folder stays
  **SHADOW_ONLY** (detection ~78% including markerless exports).
