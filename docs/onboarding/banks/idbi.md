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
