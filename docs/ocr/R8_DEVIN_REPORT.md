# R8 — first real accuracy measurement of the OCR tier (synthetic scans only)

Branch `devin/r8-accuracy` = `integration/v2-waves` @ `a3f0a2a` (engine fixes F10/F11/F13) + R7
service hardening `6bfaf48` cherry-picked. RTX 3060 12 GB, vLLM 0.32.0 mode, `OCR_VL_MAX_NEW_TOKENS=2048`.
**Synthetic scans only** — `tools/ocr_eval/corpus.py`, 27 fresh statements in `tmp/r8_corpus`.

## Headline

**0 of 27 statements served.** Exact-amount rate 0.00% (no rows were extracted anywhere, so there was
nothing to score), side flips 0 (vacuous). Every run produced the identical split: **18 ×
AMBIGUOUS_MONEY_COLUMNS + 9 × TOO_FEW_ROWS, zero run-to-run variation**. The only passing gates are the
vacuous ones (invented rows = 0, side-flip rate = 0); `exact_amount_rate ≥ 0.995` and `p95 ≤ 4.0 s/page`
FAIL in every category. The F10/F11/F13 fix works exactly as designed — failures are now named, honest
refusals with header titles, not crashes — but the recogniser's table output is still unusable: it
**merges adjacent money-column headers** and **inserts phantom columns**, so nothing downstream can
place a row.

## Part 1 — stack & sanity — PASS

| check | command | result |
|---|---|---|
| corpus | `python tools/ocr_eval/corpus.py --out tmp/r8_corpus --per-category 3` | 27 statements, 9 categories |
| vLLM + service up | `docker run … vllm/vllm-openai:v0.32.0 … --served-model-name PaddleOCR-VL-1.6-0.9B …` + `r7-ocr-service` | vLLM ready t+248 s (weights re-download, fresh container); service 200 at same point. Warm-up recorded `failed:RuntimeError` honestly — it fired while vLLM was still loading. VRAM 6,517 MiB at ready |
| smoke | `run_eval.py --limit 1 --out report_smoke` | all 9 categories → `AMBIGUOUS_MONEY_COLUMNS` (F11 fix firing correctly) — table below |
| backend OCR suite | `pytest backend/tests/statement_engine/ocr/` in Docker (python:3.11-slim + requirements.txt) | **40/40 pass** (32 + 8 new `test_ocr_malformed_tables.py`) |
| ocr-service tests | `pytest ocr-service/tests` in `r7-ocr-service` image | **9/9 pass in 4.4 s** |

Smoke table (exactly as printed):

| category | n | served | exact amounts | side flips | invented (chain-pass) | chain+ref pass | p95 s/page |
|---|---|---|---|---|---|---|---|
| blur | 1 | 0 | 0.00% | 0 | 0 | 0% | 6.6 |
| clean_200 | 1 | 0 | 0.00% | 0 | 0 | 0% | 22.2 |
| dpi_150 | 1 | 0 | 0.00% | 0 | 0 | 0% | 9.0 |
| dpi_300 | 1 | 0 | 0.00% | 0 | 0 | 0% | 7.0 |
| jpeg | 1 | 0 | 0.00% | 0 | 0 | 0% | 9.7 |
| low_contrast | 1 | 0 | 0.00% | 0 | 0 | 0% | 11.5 |
| noise | 1 | 0 | 0.00% | 0 | 0 | 0% | 8.4 |
| rotated_180 | 1 | 0 | 0.00% | 0 | 0 | 0% | 9.3 |
| skew | 1 | 0 | 0.00% | 0 | 0 | 0% | 6.9 |

## Part 2 — headline accuracy — 0/27 SERVED

Three full runs (`report_run{1,2,3}`, committed to `docs/ocr/eval/`). Identical outcome every run:

- served: **0/27** — exact-amount rate **0.00%**, side flips **0**, invented rows **0**, missing 1080/2160 cells-worth (all rows missing)
- pages: **54/54 OCR'd fine, 0 failed pages, 0 timeouts, 0 kills** — the R7 service + vLLM never missed a page
- speed: run1 p50 5.79 / p95 6.76 s; run2 p50 5.89 / p95 6.60 s; run3 p50 5.71 / p95 6.58 s
- **run-to-run variation: zero** — every one of the 27 statements produced the same code in all 3 runs. The VLM's *structural* output on these synthetic pages is deterministic enough to be stable.

Per-category table (run 1; runs 2-3 identical):

| category | n | served | exact amounts | side flips | invented (chain-pass) | chain+ref pass | p95 s/page |
|---|---|---|---|---|---|---|---|
| blur | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.5 |
| clean_200 | 3 | 0 | 0.00% | 0 | 0 | 0% | 9.3 |
| dpi_150 | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.6 |
| dpi_300 | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.3 |
| jpeg | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.5 |
| low_contrast | 3 | 0 | 0.00% | 0 | 0 | 0% | 7.5 |
| noise | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.6 |
| rotated_180 | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.7 |
| skew | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.8 |

Not served (all 27, run 1 — the two refusal modes and the titles that caused them):

| id | code | dropped | header titles |
|---|---|---|---|
| *_00, *_02 (18 stmts) | AMBIGUOUS_MONEY_COLUMNS | 0 | `date / narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:closing balance` (+ aux `amtdeposit`) |
| *_01 (9 stmts) | TOO_FEW_ROWS | 0 | `date / narration / ref:chqrefno / amount:amount / balance:balance` |

Representative rows: `clean_200_00 AMBIGUOUS_MONEY_COLUMNS` … `clean_200_01 TOO_FEW_ROWS` (full tables in
`docs/ocr/eval/report_r8_run{1,2,3}.md`).

Gate table per category (value / threshold / verdict, run 1):

| category | served | exact% (≥99.5) | flips (≤0.1%) | invented (0) | p95 s (≤4.0) |
|---|---|---|---|---|---|
| blur | 0/3 | 0.00 FAIL | 0 PASS | 0 PASS | 6.5 FAIL |
| clean_200 | 0/3 | 0.00 FAIL | 0 PASS | 0 PASS | 9.3 FAIL |
| dpi_150 | 0/3 | 0.00 FAIL | 0 PASS | 0 PASS | 6.6 FAIL |
| dpi_300 | 0/3 | 0.00 FAIL | 0 PASS | 0 PASS | 6.3 FAIL |
| jpeg | 0/3 | 0.00 FAIL | 0 PASS | 0 PASS | 6.5 FAIL |
| low_contrast | 0/3 | 0.00 FAIL | 0 PASS | 0 PASS | 7.5 FAIL |
| noise | 0/3 | 0.00 FAIL | 0 PASS | 0 PASS | 6.6 FAIL |
| rotated_180 | 0/3 | 0.00 FAIL | 0 PASS | 0 PASS | 6.7 FAIL |
| skew | 0/3 | 0.00 FAIL | 0 PASS | 0 PASS | 6.8 FAIL |

**No accuracy gate passes.** `invented` and `side-flips` PASS only vacuously — nothing was ever placed.

## Part 3 — raw HTML structural analysis — the decisive answer

Six pages dumped raw (`docs/ocr/eval/r8_raw_pages.json`): clean_200_00/_01, skew_00, noise_00,
jpeg_00/_01 — covering both corpus layouts.

| page | header `<td>` | drawn cols | header logical width | data-row width dist | empty `<td></td>` in data |
|---|---|---|---|---|---|
| clean_200_00 (split) | 5 | 6 | 6 (`Closing Balance` colspan=2) | {6: 22} | 22 |
| skew_00 (split) | 5 | 6 | 5 | {5: 22} | 0 |
| noise_00 (split) | 5 | 6 | 5 | {5: 22} | 8 |
| jpeg_00 (split) | 5 | 6 | 5 | {5: 22} | 9 |
| clean_200_01 (combined) | 6 | 5 | 6 (trailing `''` title) | {6: 22} | 22 |
| jpeg_01 (combined) | 6 | 5 | 6 (trailing `''` title) | {6: 22} | 22 |

**a. Empty cells:** emitted as `<td></td>` when the column exists (22/22 rows on clean_200_00, _01,
jpeg_01; 8-9 on noise_00/jpeg_00). **Zero short rows anywhere** — every row in every table is uniform
width. The model *does not* drop cells mid-row on this data; F10's original trigger is absent here.

**b. What is missing is never a cell — it is a whole column.** On split layouts the model collapses
`Withdrawal Amt.`+`Deposit Amt.` to ONE data column carrying whichever side is non-empty
(`skew_00` row: `['01/04/2026','UPI/GPAY/…','R333848','1,66,553.34','1,37,447.18']` — debit/credit
indistinguishable; had this served, it would be side flips). On noise_00/jpeg_00 it additionally drops
some amount *values* outright (money cell `''`, balance present).

**c. Header cell count does NOT match the drawn header on either layout.** Split: drawn 6 → 5 `<td>`;
the model concatenates the adjacent titles verbatim — `<td>Withdrawal Amt.Deposit Amt.</td>` — every
category, every run. Sometimes it then colspan-compensates `Closing Balance` to keep width 6, sometimes
not. Combined: drawn 5 → **6** `<td>` — it invents a trailing empty header cell and a matching phantom
column of `<td></td>` in every data row.

**d. Total `OCR_TABLE_ROWS_DROPPED` across the full run: 0 of 2,160 expected row cells (0%).** The
dropped-row path never engaged because the model normalizes every page to a *uniform* grid — the
failure moved up a level, from cell-shape to column-identity.

**Verdict:** HTML-grid extraction cannot be reliable while the model is free to (i) merge adjacent
money headers into one cell, (ii) collapse two money columns into one, and (iii) invent phantom
columns — with no coordinates on any of it. The grid is *rectangular*, just wrong. A coordinate-based
text layer is the defensible direction (Part 4).

## Part 4 — PP-OCRv5 coordinate feasibility — MEASUREMENT ONLY

Same six pages, `lines` + `rec_boxes` (PP-OCRv5, the existing verifier).

**Amount-shaped tokens cluster into distinct vertical bands** — split pages: 3 bands (x-centres
~1,080-1,100 / ~1,284-1,334 / ~1,426-1,458 px on a 1,654 px page), combined pages: 2 bands
(~1,263-1,302 / ~1,445-1,474). Separation quality: inter-band **gap 140-190 px vs band width 25-75 px**
— clean separation (gap ≥ ~2× width) on every page except where a band is empty.

**Transaction-row coverage:** all 22 rows present on every page in both readers — date tokens 22/22,
ref tokens 22/22, matching the VLM's 22 data rows exactly.

**But token granularity is imperfect:** PP-OCRv5 **fuses horizontally-adjacent amounts** into one box —
`'3,58,814.09 6,65,814.32'` is a single line spanning deposit+balance columns when both are printed and
the gap is small (< ~100 px). Counting amounts within each row's y-band, fused rows show 1 token
(splitting on the internal space recovers both values), and occasionally the fusion *corrupts the
boundary* — `'1,20,132.467'` (deposit `1,20,132.46` + first digit of balance absorbed; unrecoverable
without column priors). Fusion hits ~9/22 rows on clean_200_00, ~5-9 on skew/noise/jpeg_00, **0 on the
combined-layout pages** (the empty-side column keeps the printed gap wide).

**Feasibility verdict:** PP-OCRv5 gives complete row coverage, true coordinates, and clean money-column
x-bands — everything the engine's word-grid design expects and the VLM cannot lie about. The gap is a
tokenisation layer: fused adjacent amounts must be split (trivial when the space survives; needs
column-band priors when it doesn't, e.g. `1,20,132.467`). Feasible, with a defined fusion-splitting
rule — and it should be verified against a page where two values genuinely sit in one box before
committing.

## Part 5 — end-to-end dropped-row reporting — PASS (via mock fixture; see caveat)

The live VLM could **not** be induced to emit a mis-shaped row in 6 constructions (colspan=6 footers,
wrapped narration → merged cell, contiguous narr+ref → re-split, missing balance → `<td></td>`, stray
mark → phantom 7th column table-wide, 2-item row → padded 6-wide). The reporting path was therefore
verified through `process_statement` with `STATEMENT_ENGINE_OCR_URL=mock:` replaying a contract-level
`OcrDocument` containing one 5-td non-transaction row inside a 6-col table — every downstream component
(client contract, grid, reader, serve, Excel, Statement Check) is the real production code; only the
model call is replayed. `STATEMENT_ENGINE_OCR_MODE=serve`, `bank_name="No Such Bank"`:

- result `success`, workbook `tmp/r8_p5_out/Unknown_account_T_U_...xlsx` (10 sheets)
- job block: `engine:"ocr"`, `verdict:"REVIEW"`, `needs_review:true`, `anchored:false`,
  `review_codes:["OCR_READER","OCR_TABLE_ROWS_DROPPED"]` ✓
- `block.ocr.rows_dropped: {"1":1}`, `rows_dropped_total: 1` ✓
- checks: schema/chain/side/dates **pass** (dropped row was non-transactional), verifier ran 24/24 confirmed

Statement Check sheet (synthetic only), verbatim:

```
Statement Check
Engine | ocr
Verdict | REVIEW
Independently verified | no
Needs review | yes
Review reasons | OCR_READER, OCR_TABLE_ROWS_DROPPED
OCR (scanned statement)
Read with | PaddleOCR-VL-1.6 + PP-OCRv5
Pages read | 1
Pages NOT read | none
Rows that could not be placed | 1 page 1: 1
Note | 1 table row(s) were read in a broken shape and could NOT be placed in a column safely,
       so they are NOT in this workbook. Check those rows in the PDF.
Second-reader amount check | ran
Amounts confirmed / low confidence / not confirmed | 24 / 0 / 0
Note | Figures were read from an image. OCR can misread digits, so every figure must be checked
       against the original statement. This result is never marked as verified.
```

## Part 6 — teardown — PASS

`docker rm -f r8_ocr r8_vllm` + network removed. VRAM **1,455 MiB** (baseline; other stacks' idle).
No `r8_*`/`devin_*` containers remain. `airco_*`, `keycloak*`, `ue_*`, `demo_*` untouched.

## Findings for Claude (engine-side, reported not fixed)

| id | sev | finding |
|---|---|---|
| **F14** | critical | VLM **merges adjacent money-column titles**: `<td>Withdrawal Amt.Deposit Amt.</td>` (and `Dr./Cr.` splits avoided only because single-word headers happen to map cleanly). 18/27 refusals. The header text carries the column boundary the model refuses to draw — consider detecting merged-title cells (`Amt.`+title fragments in one cell / `header_aux` leftovers) and splitting the DATA column by PP-OCRv5 x-bands rather than refusing. `AMBIGUOUS_MONEY_COLUMNS` detail string itself is good evidence the engine sees the right shape. |
| **F15** | major | Combined layout: model **invents a phantom column** (extra trailing header `<td></td>`, uniform 6-wide table over a 5-col statement) → `TOO_FEW_ROWS` with 0 rows extracted. 9/27 refusals. The grid adapter can't tell header-width-6-vs-5 apart without coordinates. |
| **F16** | major | On split pages the model emits ONE money column carrying whichever side is non-empty — had the header not been ambiguous, these would have been silent side flips. `AMBIGUOUS_MONEY_COLUMNS` is currently the only thing between this and wrong money. Coordinate grounding is the real fix. |
| F17 | minor | noise/jpeg pages: some amount *values* missing entirely (money cell `''`, balance present) — silent data loss inside an otherwise well-formed grid. |
| — | note | The `OCR_TABLE_ROWS_DROPPED` path is correct but **unreachable with this model**: it normalizes every table to a uniform-width grid (pads, colspan, phantom columns). Verified end-to-end via mock fixture; a live-model trigger could not be constructed in 6 attempts. |
| — | note | `xtra` construction exposed a second misread class: dates `10/04`-`20/04` returned as `0/04`-`9/04` (tens digit dropped) — these rows would die at schema. Not counted in the refusal tables because the statement refused earlier for other reasons. |

## What remains unverified

- **All accuracy numbers.** Zero statements served → zero rows scored; exact-amount, side-flip and
  chain rates are all unmeasured (not failed — unmeasured).
- Real scans — not in this run, per the task rules.
- The 4 s/page gate: measured p95 6.58-6.76 s on the 3060 — FAILS, honestly reported.
- Whether a served OCR statement can exist at all with this model — every synthetic layout refused.
- Default non-vLLM path: unchanged since R7 (identical `app.py`, `OCR_VL_SERVER_URL` opt-in only);
  `STATEMENT_ENGINE_OCR_MODE` unset = baseline, untouched.
