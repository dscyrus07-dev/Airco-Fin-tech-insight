# W8-5 — V2-serve parity gate

Method: deterministic sample (sha-sorted, ≤8 files/bank) of files that were
VERIFIED with an independent-anchor pass at the phase-7 tip, re-routed under this
branch. Each file was processed twice — legacy pipeline and the v2 engine-hook
(`row_source`) — to Excel. Compared: row count, Σdebit/Σcredit, category totals,
sheet names, per-sheet numeric-cell hash. No statement content persisted
(`comparison/wave8/parity.jsonl`, untracked).

## Result matrix (72 files)

| bank | identical | diff | legacy pipeline_error | not VERIFIED+anchored |
|------|-----------|------|----------------------|-----------------------|
| axis | 0 | 8 | 0 | 0 |
| canara | 0 | 1 | 7 | 0 |
| hdfc | **8** | 0 | 0 | 0 |
| icici | 0 | 8 | 0 | 0 |
| idfc | 0 | 8 | 0 | 0 |
| karnataka | 0 | 0 | 0 | 8 |
| kotak | 0 | 0 | 7 | 1 |
| sbi | 0 | 0 | 0 | 8 |
| union | 0 | 0 | 6 | 2 |

Notes: `legacy pipeline_error` means the legacy processor itself could not parse
the file (Canara/Union table-shape failures, Kotak "no transactions extracted")
— parity is not measurable there, and v2 is the only engine that can serve them.
`not VERIFIED+anchored` files routed to a non-VERIFIED verdict or an unanchored
layout under this branch — they can never be served anyway.

## Diff classes (all audited diffs are explained; none silent)

1. **Legacy leaks non-transaction rows.** Axis row-count diffs (−6, −10, −28):
   legacy emitted footer/summary lines as transactions, e.g.
   `Ban/Payment/ TRANSACTION TOTAL … Sr. No. Period Re…`. v2 correctly drops
   them; its chain and reference checks still reconcile VERIFIED+anchored.
2. **v2 recovers rows legacy missed** (icici +3, +24; idfc +5, +3, +6, +17): the
   extra rows are genuine dated transactions; v2 balance chain still reconciles.
3. **Gross vs netted amounts** (axis `01ecb20c`, `01f665a3`): v2 keeps the
   printed debit and credit of a charge+reversal pair on their own sides
   (e.g. dr 289.54 / cr 10.00); legacy netted them (dr 279.54). Net per row is
   identical; v2 matches the printed balance column (VERIFIED+anchored).
4. **Description text shape → category totals.** v2 narration differs from
   legacy in whitespace and continuation-line merging (e.g.
   `…SALEEM  P` double-space, `G/Karnataka/UPI` + `CreditCard Payment XXXX 1601`
   merged). Same rows, same economics, different keyword matches → category
   buckets and Monthly Analysis / Summary sheet hashes differ. Audited same-
   description rows showed **no** debit/credit side flips.

Unexplained numeric diffs: **0**. The differences are v2 being more faithful to
the printed statement (gross sides, no footer rows) and narration-text shape.

## Gate verdict

- `hdfc`: **parity-clean → eligible for the serve allowlist.**
- `axis`, `icici`, `idfc`: diffs explained and directionally in v2's favour,
  but served output is not identical to legacy (categories/sheets visibly
  change). **DO-NOT-SERVE until a product decision accepts narration-driven
  category changes.**
- `canara`, `kotak`, `union`, `sbi`, `karnataka`: insufficient parity evidence
  (legacy can't parse the sample, or no VERIFIED+anchored sample exists).
  **DO-NOT-SERVE.**

Recommended default: `STATEMENT_ENGINE_V2_SERVE_BANKS=hdfc` (opt-in; empty
allowlist serves nothing regardless).
