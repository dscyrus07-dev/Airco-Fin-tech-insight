# indusind — onboarding notes

Status: **SHADOW_ONLY**

Folders: IndusInd Bank
Files: 154 pdf | 148 text | 3 scanned | 3 locked

## Fingerprints

distinct fingerprints: 9 | top share: 37.8%
- `date/narration/credit/balance` x56
- `date/narration/ref/srno/debit/credit/balance` x43
- `date/dr_cr/narration/debit/credit` x21
- `srno/dr_cr/amount/balance` x11
- `date/narration/debit/credit/balance` x8
- `date/narration/ref/debit/credit/balance` x3
- `date/dr_cr/narration/debit/credit/balance` x2
- `date/narration/ref/srno/ref/debit/credit/balance` x2
- `<none>` x2

## Current behaviour (V2_MODE=shadow)

- probed: 148 | detected-correct: 93.2% (wrong: 0, none: 10)
- tier: {'fallback': 48, 'v2': 100} | rows read: 61410
- verdicts: {'VERIFIED': 95, 'FAILED': 2, 'REVIEW': 3}
- fallback reasons: {'no_layout': 48}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 20 of 95 VERIFIED | ok: 20 | disagreements: 0


## unblock-1 re-measure (devin/unblock-1)

Added `INDUSIND_LAYOUT_2`/`_3`: the newer "Chq No/Ref No" export family. Distinct from L1 (`ChqRefNo`):
dated `Brought Forward`/`Carried Forward` restate rows on every page (used as printed anchors:
opening row + `carriedforward<amt>` closing), `0.00` printed in unused money cells, header titles may
wrap (`header_wraps`), date cells on continuation pages drift ~4pt left of the anchor page
(`date_left_pad`), two date spellings (dd-Mmm-yyyy and "dd Mmm yyyy"), newest-first print order
(`row_order="auto"`), space-date variant amounts print with a single decimal place.

- v2 routed: 103 of 129 manifest files (was 85) | VERIFIED 92 (was 80) | REVIEW 6 | FAILED 5 | no_layout 26
- L2 (dashed dates, B/F+C/F anchors): 12 VERIFIED
- L3 (space dates, no anchors): 3 REVIEW (honest self-derived chains) + 3 FAILED — those prints truncate
  the balance column to whole rupees while debits/credits keep paise (printed-vs-derived mismatch is real:
  e.g. derived 8,323.15 vs printed 8,323.00); honest failure, not a spec gap
- still no_layout (26): the `Date|Type|Description|Debit|Credit` + wrapped-Balance family
  (needs implicit_header; most files carry no own-bank header/footer evidence — header-only acceptance
  would be unsafe), truncated-date-token files (e.g. `2025-12-` with the day missing), a `Ref No|Chq`
  column-order variant, and mislabelled/cover-only documents
- cross-bank: 0 accepts / 0 detector hits on 364 pooled other-bank files
- audit: 43 VERIFIED sampled, 0 disagreements
- gate unchanged: stays **SHADOW_ONLY** (share of VERIFIED still below bar; unrouted families remain)
