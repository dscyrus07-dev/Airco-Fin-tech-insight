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

## N5 pass (branch devin/n5-bank-wave)

- Added `INDUSIND_LAYOUT_4` for the app/CA export family `DATE|TYPE|DESCRIPTION|DEBIT|CREDIT|BALANCE`:
  two-line header ("Balance" on the second header line), each record = a type/narration line above the
  dated line (`Transfer Credit | UPI/...`), `-` empty money cells (`empty_amount_marker`),
  `header_lines=2` + `leading_narration`. No anchors print anywhere -> REVIEW ceiling by design.
- Added `ifsc_re` (`INDB0[0-9A-Z]{6}`) to all four specs: the export prints `IFSCCODE:INDB...` in the
  page-1 account block (header region — own-bank evidence); foreign IFSCs seen in UPI narration remain
  non-evidence. This routed 23 previously-fallback files.
- `row_order="auto"` on L4: a subset prints newest-first; reversal is accepted only when the balance
  chain holds newest-first and breaks oldest-first (evidence-driven).
- Date variants widened on L4: `Aug 1, 2022` comma form; `period_date_format` extended the same way.
- Folder re-measure (129 files): VERIFIED 92 -> 92, REVIEW 6 -> **28**, FAILED 5 -> 6, fallback 26 -> **3**.
  22 new REVIEWs are rows-read yield (honest: no printed anchors, class E); the one new FAILED
  (`d602934e`) has a single real chain gap with unread=0 — the PDF itself skips rows (class D).
- Cross-bank: 0 wrong-bank accepts / 417 pooled routes; 0 foreign files landed on indusind.
- Audit: 40/40 VERIFIED clean (0 chain breaks); residual flags are auditor generic-scan artifacts
  (account-number strings read as anchor amounts; B/F-C/F restate rows are the engine's true anchors).
- Remaining fallback (3): `10973719`, `51d9158e`, `8fde16bc` — date column renders as split glyph runs
  (`05-23` / `2026-` on adjacent lines), no complete date token anywhere (class D, NOT_POSSIBLE).
- Gates: detection 126/129 = 97.7% (<100%), yield 120/129 = 93.0% pass, VERIFIED share 92/129 = 71.3%
  (<80% where balances print) -> stays **SHADOW_ONLY**.
