# federal — onboarding notes

Status: **SHADOW_ONLY**

Folders: Federal Bank
Files: 360 pdf | 308 text | 1 scanned | 51 locked

## Fingerprints

distinct fingerprints: 13 | top share: 37.3%
- `date/date/narration/date/dr_cr/ref/narration/debit/credit/balance/dr_cr` x115
- `balance/debit/balance` x49
- `ref/narration/amount/balance` x48
- `date/date/narration/debit/credit/balance` x28
- `date/date/narration/date/ref/narration/debit/credit/balance` x27
- `date/date/narration/date/debit/credit/balance/dr_cr` x14
- `date/narration/amount/dr_cr` x11
- `date/date/narration/date/debit/credit/balance` x9
- `date/date/narration/debit/credit/balance/dr_cr` x2
- `srno/srno/srno` x2
- `<none>` x1
- `date/narration/dr_cr/amount` x1
- ... +1 more

## Current behaviour (V2_MODE=shadow)

- probed: 308 | detected-correct: 95.5% (wrong: 0, none: 14)
- tier: {'fallback': 114, 'v2': 194} | rows read: 106120
- verdicts: {'VERIFIED': 144, 'REVIEW': 37, 'FAILED': 13}
- fallback reasons: {'no_layout': 113, 'v2_failed:NO_ROWS': 1}
- cross-bank false accepts on pooled other-bank files: 5
  - 18f47088 from CSB Bank via layout
  - 105adbdd from CSB Bank via layout
  - 930efd6d from CSB Bank via layout
  - 528ee39a from CSB Bank via layout
  - 22f26126 from CSB Bank via layout

## Independent audit (hold-out VERIFIED sample)

- sampled: 15 of 144 VERIFIED | ok: 15 | disagreements: 0

## Unblock pass (prompt-29, current branch)

- 113 no_layout fingerprinted in full: ~100 are the Federal/Jupiter app-statement family
  (`Reference ID | Transaction details | Amount(₹) | Balance(₹)`) where the date prints once per
  day-group as a section header and transaction rows carry no date word -> needs section-date
  inheritance; the engine starts a row only on a dated line. ENGINE GAP (generic: "dated section
  headers grouping undated rows"). A doubled-glyph render of the same layout also exists.
- ~16 are balance-less `Date | Description | Amount | Type(Dr/Cr)` statements -> no balance column
  (same engine gap as dbs/idbi). No safe spec change possible for either family.
- misfiled/other: `a18ccc97` (address-doc, not a statement), GL-style prints.
- status unchanged: SHADOW_ONLY; Vshare 144/194 stays honest.

## N5 pass (branch devin/n5-bank-wave)

- Enabled `balance_optional` + `continuation_amounts` on L1/L3 (charge-back rows print a Withdrawal/Deposit
  with no restated balance; some dated rows carry only the Dr/Cr marker while amounts print on the wrap line).
- Folder re-measure (291 readable): VERIFIED 228 -> **232**, REVIEW 36 -> **39**, FAILED 13 -> **6**, fallback 14.
  All 7 diffs are FAILED upgrades; zero VERIFIED/REVIEW regressions.
- New VERIFIEDs audited (`audit2`, sparse-chain aware): 9a717620, a197d1cc, b51f05e0, e423b6e8 — 0 chain breaks.
- Remaining FAILED (6): 3 clipped `GRAND TOTAL` first figures (glued text makes the split ambiguous — print
  defect, class D); 2 bank-printed balance inconsistencies (unread=0, e.g. `54957d48` 46.00 gap); 1 dup-page
  merge (`5fdc1a0d` prints the identical "Page 1 of 1" twice — class D).
- Remaining REVIEW (39): 35 no printed anchors (self-derived chain ceiling — class E, honest), 1
  dates-not-monotonic, plus the new anchor-gap upgrades.
- Remaining fallback (14): 12 detector UNKNOWN (zero bank evidence — correct refusal), `a18ccc97` glued CID
  text (class D, NOT_POSSIBLE), `b491d230` cover page, `a32f18d3` zero-transaction export.
- Status: **SHADOW_ONLY** — detection 277/291 (95.2%) below the 100% gate (unbranded exports cannot be
  claimed without evidence); yield 271/291 = 93.1% pass; Vshare 232/277 = 83.8% pass.
