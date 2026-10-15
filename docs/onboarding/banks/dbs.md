# dbs — onboarding notes

Status: **SHADOW_ONLY** (promote-1, improved) — yield 87.0% (114/131 V|R) < 90% gate because
9 files print a balance-less layout the engine cannot verify (engine gap, parked for Claude).
VERIFIED share of routed files is 91.7% (110/120). The original diagnosis was wrong:
the 'Opening Balance' line is undated (dropped as a pre-row narration line), not a dated opening
row — adding `opening_balance_re` (searched on the table's first page) restored both anchors.
Was: SHADOW_ONLY — detection 99.2%, 0 VERIFIED.

Folders: DBS Bank
Files: 137 pdf | 131 text | 4 scanned | 2 locked

## Fingerprints

distinct fingerprints: 3 | top share: 91.6%
- `dr_cr/balance` x120
- `date/narration/debit/credit` x9
- `date/date/branch/narration/debit/credit/balance` x2

## Current behaviour (V2_MODE=shadow)

- probed: 131 | detected-correct: 99.2% (wrong: 0, none: 1)
- tier: {'v2': 118, 'fallback': 13} | rows read: 19972
- verdicts: {'REVIEW': 112, 'FAILED': 6}
- fallback reasons: {'no_layout': 12, 'v2_failed:NO_ROWS': 1}
- cross-bank false accepts on pooled other-bank files: 0

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0

## promote-1 changes

1. `opening_balance_re` added to DBS_LAYOUT_1 -> 109/112 former REVIEWs now VERIFIED.
   The 6 `chain+side` FAILEDs are multi-account docs where merged statement segments share
   one row stream — the boundary break is engine behaviour, not a spec defect (unchanged).
2. `DBS_LAYOUT_2` added for the `Transaction date | Value date | Branch code | Description |
   Cheque/Reference number | Debit | Credit | Balance` variant (wrapped 'number' title,
   dd/mm/yyyy dates, label/value summary block anchored via INR-prefixed last-page text).
   `d8e38ff6` -> VERIFIED/593 rows; `fe125181` -> REVIEW (summary block sits on the
   second-to-last page — out of reach of the last-page anchor scan; honest cap).

Remaining gaps (engine/corpus, not spec-fixable):
- 9 files `Date | Details of Transaction | Debit | Credit` with NO balance column —
  the engine cannot verify a chain without balances -> park (engine capability needed).
- `b4a408e2` (CID-encoded fonts, v2_failed:NO_ROWS), `2afd8fc8` (scanned),
  `0e3bc943` (consolidated-accounts certificate, not a transaction statement),
  4 scanned + 2 locked -> corpus problems.
- `fe125181` REVIEW as described above.

## Unblock pass (devin/unblock-1)

Re-measure at unblock tip (137 files): 110 VERIFIED + 4 REVIEW + 6 FAILED v2;
11 no_layout; 2 locked; 3 scanned; 1 NO_ROWS. Yield 114/~130 = ~88% <90%;
Vshare 110/114 = 96.5%. Remaining gap is entirely engine-class, not spec:
- balance-less `Date | Details of Transaction | Debit | Credit` variant (no
  balance column; LayoutSpec requires balance_column): ~9 files
  (`4e83e770`,`660bdbec`,`80f46ade`,`0d4c198e`,`4b87612b`,`c6fefe46`,
  `fe8199d0`,`01de47c4`,`d408b98c`).
- multi-account / mid-document summary statements: FAILED chain
  `2cce319e`,`fa24a579`,`ac939c61`,`e22fdd6a`,`6d986d74`,`e7494071`; honest
  REVIEW `c898cb0f`,`af0a1396`,`b7f2b63c` (second account section unread).
- `fe125181` honest REVIEW (no printed anchors).
- `b4a408e2` zero-transaction statement -> NO_ROWS (honest).
- excluded as non-statement/unreadable: `0e3bc943` (1-page consolidated
  summary), `2afd8fc8` (scanned, 1 word).
Still **SHADOW_ONLY**; needs the balance-less and multi-account engine
capabilities listed in ENGINE_GAPS.md.

## N5 pass (branch devin/n5-bank-wave)

- N2 capabilities already absorbed the known gaps: the 6 multi-account FAILEDs now read via
  `merge_statements`/segment handling (`additional_statement_after_summary` REVIEW flags on
  `af0a1396`, `b7f2b63c`, `c898cb0f` — honest cap), and the balance-less family rides
  `DBS_LAYOUT_3` (`no_running_balance`) to REVIEW-with-rows.
- Added `DBS_LAYOUT_4` (`replace` of L3): the same balance-less family with yearless `02 Jul`
  row dates — year from the printed `Transaction History From .. To ..` period
  (`year_from_period`). `660bdbec` -> REVIEW/196, `80f46ade` -> REVIEW/10.
- Folder re-measure (129 readable): VERIFIED 116, REVIEW 11, FAILED 0, fallback 1
  (`b4a408e2` CID-mojibake text layer — class D, NOT_POSSIBLE).
- Cross-bank: 0 foreign accepts / 363 pooled routes (L4 shares the `DBSBANK` marker only).
- Audit: REVIEW ceiling is structural for `no_running_balance` (no printed balance = no
  independent anchor evidence); prior VERIFIED audit coverage stands (see unblock-1 section).
- Gates: detection 128/129 = 99.2% (<100%: `b4a408e2` unparseable), yield 127/129 = 98.4% pass,
  VERIFIED 116/129 = 89.9% pass -> stays **SHADOW_ONLY** on the detection leg.
