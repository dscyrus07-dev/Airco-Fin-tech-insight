# Wave 7 — coverage wave results

Base: `2f54fd7` (post-Wave-6). Corpus: unified statement corpus via `comparison/wave6/_u_index.json`.
All corpus files read-only; routing under `v2_router.route_pdf` with the evidence gates
(`bank_evidence` region/document/detector; `foreign_bank` refusal; header-only refused by default).

## 1. New machinery (opt-in, codec round-tripped)

| field | purpose |
|---|---|
| `header_wraps` | column titles that wrap onto a second visual line; pair merged by x0-clusters, completion checked with centre-based coverage (font-width protrusions no longer count as unknown tokens). Pair attempt only when the upper line already matches >=2 columns including `date` — a period line + header line can no longer false-merge. Returns the continuation line index so row scanning starts after the full header. |
| `date_left_pad` | per-spec override of the date-column left pad (data dates printed 1-3pt left of the derived boundary no longer classify as furniture). |
| `_has_dated_row` skips `period_re` lines | a repeated `From:..To:` page header is not a post-summary "additional statement"; without this the `dd/mm/yyyy` widen turned period headers into spurious REVIEW warnings. |

## 2. Spec changes

| bank | change | evidence |
|---|---|---|
| federal | L2/L3 **unparked** (park reason "0 VERIFIED" predates `anchor_full`; printed `openingbalance` + `grandtotal` now anchor both ends). L1-L3: `header_wraps`, `totals_line_re` (`grandtotal <dr> <cr>`, 1-2dp tolerant), `anchor_full`, `date_left_pad=10`, L2 `continuation_start="top"`, L3 `cr/dr`+`crdr` side alts, all 3 accept `dd-MMM-yyyy`|`dd/mm/yyyy`|`dd-mm-yyyy`. | 6 probes: 4 VERIFIED (rows 1492/636/629/233 — incl. 112 rows recovered on continuation pages), 1 REVIEW (`10f8fa93`: genuinely no printed anchors), mutations 5/5 FAILED on every VERIFIED file. |
| sbi | L1/L2/L3 widened: `debits`/`credits`, `particulars`, `ref/no/cheque`, `refno/chequeno`, `reference`, `valuedate`, `narration`, `datevaluedate`, `datevaluedat` (clipped title), `dd-MMM-yy(yy)` dates; L1 `zero_amount_is_empty`. L3 (refnocheque): `refchequeno`/`ref cheque no` alts, `dd-MMM-yy` dates. L5 (postdate): `post`/`post date`/`value date`/`details`/`narration`/`chq*`/`cheque*` alts, `dd/mm/yy`+`dd-mm-yy` dates, `header_wraps`, `BROUGHT FORWARD:` colon-tolerant. **L9 new**: L4 shape + standalone `cheque` column (`continuation_amounts`). | `502262e5` -> L9 REVIEW 265 rows; `344be9cc` -> L3 REVIEW 96; L5 postdate files route REVIEW (opening-only where closing absent). |
| hdfc | L_A: `valuedate`/`value date`, `withdrawal`/`deposit` `amount`, `particulars`, `chqref`/`reference` alts, `dd/mm/yyyy` 4-digit years, `zero_amount_is_empty`. **L_B new**: `Sr.No | Date | Particulars | Chq./Ref. [Number] | Debit | Credit | Closing Balance` — wrapped `Number` title, `OPENING BALANCE` row + `STATEMENT SUMMARY` 6-number block + `END OF STATEMENT` -> `anchor_full`. | `a79b5148` +3 siblings -> **VERIFIED** (113/288/163/355 rows), mutations 5/5 FAILED; `9d0fee6d` extracts -> honest FAILED. |
| icici | L1: `dd,mm,yyyy`+`dd-mm-yyyy` date variants + integer (`00`-style) amounts. L3/L4 stay **parked** — stale-balance export prints fail the chain honestly (park reason stands); wrap-family would need a new spec and could only ever produce honest FAILED/REVIEW, so it is documented rather than built. | 5 `NO_ROWS` files -> REVIEW/FAILED rows (209/109/65/44/287/357/168). `41543445` parses 351 rows under L4 but detector says `yes:MEDIUM` — evidence gate would refuse anyway. |
| kotak | L8/L9 **unparked** (park reason "no bank evidence" measured pre-detector; detector identifies the export family VERY_HIGH -> `bank_evidence:detector`; foreign-marker refusal still applies). L5+L8 `header_wraps` (`Value`/`Date` title wrap). | `90495585` -> L9 REVIEW 183; `c86dabcd` -> L5 FAILED 25 (1 schema err, honest). |
| axis | **L3/L4 new**: `Txn Date | Transaction | Withdrawals | Deposits | Balance [| Other Information]` mobile export — header on page 2, `Opening Balance` row only -> `anchor_full` caps at REVIEW. | 13/43 no-layout axis files recovered: 9 REVIEW + 4 honest FAILED. |
| icici | L3/L4 stay **parked** — stale-balance export prints fail the chain honestly (park reason stands); wrap-family would need a new spec and could only ever produce honest FAILED/REVIEW, so it is documented rather than built. | `41543445` parses 351 rows under L4 but detector says `yes:MEDIUM` — evidence gate would refuse anyway. |
| union | L1: `dd-mm-yyyy`/`ddmmyyyy` dates + bare `dr`/`cr` suffixes + integer amounts; `row_order:"reverse"`->`"auto"` (chain-evidence direction pick — old files kept reverse, new forward-printed files recovered). fused single-token headers (`transactiondetailsono.`) + `detector:UNKNOWN` -> unreachable without evidence; parked as unparseable-by-design. | 16 `NO_ROWS` files -> v2 (REVIEW/FAILED). `b2c5a953`/`016010be`/`39d8937a` all UNKNOWN detector. |

## 3. What stays honest-fallback (intended)

- `no_layout` remainder: detector UNKNOWN/weak on files that also lack bank markers -> header-only refusal is correct.
- `foreign_bank` (e.g. `b7542f52`: HDFC furniture inside SBI-shaped header).
- `bank_unconfirmed`: 456 files in the baseline where a header matches but no bank evidence exists — sampled files literally carry *other* banks' ad tokens or none. See `BANK_UNCONFIRMED_ANALYSIS.md`.
- `other_bank:*` / `legacy_only:bank_of_india`: out-of-scope banks, by design.
- `locked` (encrypted) and `scanned_no_text` (image PDFs): environment limits, not parser bugs.
- `v2_failed:NO_ROWS` (~29): layout matched but no parseable rows — union L1 (17) + small tails; documented.

## 4. Coverage delta

Fresh baseline (pre-W7-spec code) over the full corpus, 14,445 files
(`comparison/wave7/baseline_{0,1,2,3a,3b}.jsonl`, deduplicated by sha):

| status | files | detail |
|---|---|---|
| v2 | 9,495 (65.7%) | VERIFIED 7,177 / REVIEW 1,851 / FAILED 467 |
| fallback | 2,754 | no_layout 2,018 / bank_unconfirmed 456 / foreign_bank 131 / NO_ROWS 47 / other+legacy 102 |
| unsupported | 2,196 | locked 1,658 / scanned_no_text 537 (environment limits) |

no_layout subset recount under final code (`recount_final.jsonl`, deduplicated, 171 unique recoveries):

| bank | no_layout files | now v2 | VERIFIED | REVIEW | FAILED | still fallback |
|---|---|---|---|---|---|---|
| federal | 189 | **77** | 42 | 28 | 7 | 112 |
| sbi | 293 | **44** | 0 | 41 | 3 | 249 |
| hdfc | 50 | **21** | 4 | 1 | 16 | 29 |
| kotak | 58 | **16** | 0 | 3 | 13 | 42 |
| axis | 43 | **13** | 0 | 9 | 4 | 30 |
| icici | 543 | 0 | — | — | — | 543 (345 balance-less unrepresentable; ~140 parked-L3/L4 wrap variants; rest evidence-less) |
| union | 58 | 0 | — | — | — | 58 (fused headers + `detector:UNKNOWN`) |
| **total** | **1,234** | **171** | **46** | **82** | **43** | 1,063 |

`v2_failed:NO_ROWS` recovery (widened date/amount shapes):
- union L1 (`dd-mm-yyyy`+`ddmmyyyy` dates, integer/`(Dr)` amounts, `row_order:auto`): 16 files now v2 (REVIEW/FAILED honest)
- icici L1 (`dd,mm,yyyy`/`dd-mm-yyyy` dates, integer amounts): 7 files now v2 (REVIEW/FAILED honest)
- kotak/dbs/hsbc residual NO_ROWS: 8 files still NO_ROWS (deeper row-shape variants — parked)

Net: **~195 additional files reach v2** (46 VERIFIED, ~89 REVIEW, ~60 honest FAILED). VERIFIED total gains
46 new files (federal 42 + hdfc 4); every REVIEW/FAILED outcome is honest under the checks.

## 5. Regression check

- 150-file random sample of VERIFIED-at-baseline on the 7 edited banks: **0 diffs** (same status, layout, verdict, row count).
- 457-file union L1 exhaustivve re-route after `row_order:"reverse"->"auto"`: **0 diffs**.
- Fix during the wave: `dd/mm/yyyy` widening let repeated `From:..To:` period headers classify as dated rows and
  trip `additional_statement_after_summary` -> REVIEW on 5 HDFC files; `_has_dated_row` now skips `period_re` lines
  (rows.py), all 5 back to VERIFIED.
- Codec: `header_wraps`/`date_left_pad` round-trip verified for all 72 registered layouts.

## 6. Honest failures observed (not fixed)

- SBI `f84ae745`: tail-row chain/amount breaks.
- Axis `260b71e6`: printed opening 0.95 vs derived 0.00.
- HDFC `9d0fee6d`: malformed/ambiguous amount-side cells.
- Axis `4d22d913`/`813d0de5`/`34c864b9`: schema/chain breaks on the new layout family.
- Federal `10f8fa93`: no printed anchors exist -> REVIEW ceiling by `anchor_full` policy.
