# R9 — blocks vs lines text layer, and the VLM-free experiment (synthetic scans only)

**blocks served 0/27, lines served 0/27, lines-only served 0/27, side flips: 0 (nothing served — no
statement ever produced a row to flip).**

Branch `devin/r9-layer` = `integration/v2-waves` @ `e52fb24` (F14/F16 line-layer) + my R7/R8 work
rebased. RTX 3060 12 GB, vLLM 0.32.0, `OCR_VL_MAX_NEW_TOKENS=2048`. Synthetic corpus
`tmp/r9_corpus` (27 statements, fresh). Service image `r9-ocr-service` = R7 hardened + opt-in
`OCR_SKIP_VL=1` (my scope, default off).

## Headline

The lines layer did not rescue anything: both layers refuse every statement, identically across 3
runs each. BUT the failure inventory changed — the line layer exposed that PP-OCRv5 **fuses whole
header runs into one box** (the same information loss as the VLM's merged `<td>`, one level earlier),
fuses adjacent money columns into one box, and reads rotated pages as garbage. Lines-only mode is the
one decisive win: **0.76 s/page p50, 0.92 p95 — meets the 4 s/page gate with 4.3× margin, 4.1 GB VRAM
total, 25 s time-to-ready** — and produces byte-identical refusals, proving the VLM contributes
nothing to the lines layer's input. It is also the only honest measurement of "what does the
recogniser give the engine": the VLM adds a second reader only, not better text.

## Part 1 — bring-up & regress — PASS

| check | result |
|---|---|
| corpus | 27 statements, 9 categories, `tmp/r9_corpus` |
| vLLM + service up | ready ~t+240 s (weights re-download); warmup `failed:RuntimeError` honestly recorded (fired while vLLM loaded); VRAM 7,198 MiB |
| backend OCR suite | **51/51 pass** (incl. new line-layer + malformed-table tests) |
| ocr-service tests | **9/9 pass** — one race found + fixed (below) |

**Test fix (my scope):** `test_worker_comes_back_after_kill` raced the spawn thread by swapping
`s._target` after respawn — could flake to `timeout` or hang minutes (respawned worker still the
hang target). Replaced with a `_flaky_worker` that hangs on its first job only, coordinated by a
shared `ctx.Value` — deterministic under fork. In production `_target` never changes, so this was a
test-only defect. 9/9 now pass in 4.4 s.

## Part 2 — blocks vs lines — 0/27 on BOTH

| run | served | exact% | flips | invented | chain+ref | p50 | p95 | refusal mix |
|---|---|---|---|---|---|---|---|---|
| blocks ×3 (each) | 0/27 | 0.00 | 0 | 0 | 0% | ~5.4 | ~6.2-6.6 | 18 AMBIGUOUS + 9 TOO_FEW |
| lines ×3 (each) | 0/27 | 0.00 | 0 | 0 | 0% | ~5.5 | ~6.3-6.4 | 14 AMBIGUOUS + 8 TOO_FEW + 3 NO_DATES + 2 LOW_CONFIDENCE |
| lines-only ×3 (each) | 0/27 | 0.00 | 0 | 0 | 0% | **0.76** | **0.83-0.92** | identical to lines |

Zero run-to-run variation everywhere. Per-category tables (run 1, identical in runs 2-3):

| category | served | exact | flips | inv | chain+ref | p95 blocks | p95 lines |
|---|---|---|---|---|---|---|---|
| blur | 0/3 | 0.00% | 0 | 0 | 0% | 6.8 | 6.2 |
| clean_200 | 0/3 | 0.00% | 0 | 0 | 0% | 12.2 | 6.1 |
| dpi_150 | 0/3 | 0.00% | 0 | 0 | 0% | 6.1 | 6.3 |
| dpi_300 | 0/3 | 0.00% | 0 | 0 | 0% | 6.6 | 6.0 |
| jpeg | 0/3 | 0.00% | 0 | 0 | 0% | 6.0 | 6.1 |
| low_contrast | 0/3 | 0.00% | 0 | 0 | 0% | 6.0 | 6.2 |
| noise | 0/3 | 0.00% | 0 | 0 | 0% | 6.5 | 6.3 |
| rotated_180 | 0/3 | 0.00% | 0 | 0 | 0% | 6.2 | 6.4 |
| skew | 0/3 | 0.00% | 0 | 0 | 0% | 6.3 | 6.3 |

Gates: `exact_amounts` and `p95` FAIL in every category on both layers; `side_flips`/`invented` PASS
vacuously. Full tables in `docs/ocr/eval/report_r9_*.{json,md}`.

**Side-flip check (the one that matters):** N/A — zero statements served, zero rows extracted, zero
amounts compared. Nothing could be on the wrong side because nothing was ever placed. The ambiguity
gate is doing its job: the two failure modes that *would* have produced silent side flips (merged
money titles in blocks; single collapsed value column) are both caught as named refusals.

## Part 3 — VLM-free measurement — the win

`OCR_SKIP_VL=1` (opt-in env, default unchanged): worker loads PP-OCRv5 only, returns `blocks=[]` +
`lines=[…]`; health reports `vl:"disabled"`, skips the VL probe.

| config | ready | VRAM (total) | p50 | p95 | served | refusals |
|---|---|---|---|---|---|---|
| VL in vLLM, blocks layer | ~240 s | ~11.5 GB | 5.4 s | 6.4 s | 0/27 | 18 AMB + 9 TOO_FEW |
| VL in vLLM, lines layer | ~240 s | ~11.5 GB | 5.5 s | 6.4 s | 0/27 | 14 AMB + 8 TOO_FEW + 3 NO_DATES + 2 LOW_CONF |
| **lines only (OCR_SKIP_VL=1)** | **25 s** | **4.1 GB** | **0.76 s** | **0.92 s** | 0/27 | **identical to VL+lines** |

- **Meets the 4 s/page gate: yes, 4.3× under.** VRAM −65%, ready 10× faster.
- Accuracy: *identical* refusals — the VLM adds nothing to the lines layer's input. PP-OCRv5 produces
  every line the engine sees; the VLM's only role was the second-reader amount check.
- **Trade-off (both sides, honestly):** dropping the VLM deletes the independent amount verification —
  `verification.status` becomes `not_run`, and the balance chain alone proves correctness. A misread
  amount that happens to reconcile the chain would then pass uncaught. Recommend keeping the VLM as
  an *optional* verifier tier, not as the text source — the speed win argues for lines-only as the
  primary path with VL verification gated behind it, not for deleting the model.
- NOT RUN: dropping VL in the *blocks* layer (blocks come from the VLM — lines-only has none to give).

## Part 4 — fused boxes & failure analysis

- **OCR_FUSED_AMOUNTS: 157 boxes** across the corpus (26/27 statements affected). Split-layout
  statements carry 2-18 each; combined carry ~1. Fused-vs-clean exact-amount comparison is moot:
  both groups 0% (nothing served).
- 10 example fused boxes (all deposit+balance pairs sharing one box, x~1218→1515):
  `clean_200_00 "3,58,814.09 6,65,814.32" [1226,294,1515,321]` · `"2,35,119.81 8,69,143.41"
  [1224,461,1513,488]` · `"1,22,382.57 6,14,221.32" [1229,669,1516,696]` · `"4,995.74 5,20,597.67"
  [1260,1043,1514,1070]` · `"1,328.73 5,21,926.40" [1263,1086,1515,1113]` · `"4,467.68 5,26,394.08"
  [1261,1127,1515,1154]` · `"71,282.48 5,97,676.56" [1248,1170,1515,1197]` · `skew_00 "79,849.11
  6,34,833.66" [1236,775,1506,812]` · `"2,48,323.52 8,78,250.85" [1218,859,1508,894]` ·
  `"3,821.63 8,82,072.48" [1252,900,1510,936]` — full dumps in `docs/ocr/eval/r9_raw_line_pages.json`.
- **Failure groups (lines, run1):**
  - `AMBIGUOUS_MONEY_COLUMNS` ×14 — split layout; PP-OCRv5 fuses the header tail into ONE box
    (`"Chq./Ref.No. Withdrawal Amt.Deposit Amt. Closing Balance"`, x=748→1473). Even text-splitting
    can't recover it: `"Amt.Deposit"` is fused *inside the token*. Titles: `debit:withdrawal /
    amount:amt`, `deposit` → aux.
  - `TOO_FEW_ROWS` ×8 — combined layout + blur_00; header lines are **clean and separate** here
    (`Date`, `Narration`, `Chq./Ref.No.`, `Amount`, `Balance` — five boxes, right x's), every data
    token present with coordinates — yet 0 rows extracted. Engine-side, not recogniser.
  - `NO_DATES` ×3 — rotated_180 only; PP-OCRv5 (orientation classify disabled in service config)
    returns garbage text on the upside-down page.
  - `LOW_CONFIDENCE_COLUMNS` ×2 — skew_00/_01; header titles empty.
  - `rows_dropped`: 0 everywhere (line layer has no row-shape to drop; the metric is blocks-only).
- **R8 F17 re-check (lines layer):** date digit-drops **gone** — 0 short dates on 8/9 categories
  (was a VLM table-artifact). Missing *values* persist partially via fusion (jpeg_00: 26 amount
  tokens for ~44 expected = 9 fused pairs + a few true misses). rotated_180: 0 dates / 0 refs —
  no orientation fixer in the lines path.

## Part 5 — DECISION: **branch C** (lines serves 0/27)

Full raw PP-OCRv5 output (texts + boxes) committed for 5 pages: `clean_200_00` (split),
`clean_200_01` (combined), `skew_00`, `jpeg_00`, `rotated_180_00` — `docs/ocr/eval/r9_raw_line_pages.json`.

**What the engine needed to see, per failure class:**

1. **Split layout (14 stmts):** it needed the header titles as *separate* boxes. PP-OCRv5 gave it one
   box spanning 4 columns with `Amt.Deposit` fused inside a token — unrecoverable at any downstream
   level. Needs either word-level detection boxes, a per-column region read, or the VLM's header
   semantics where the title strings at least separate (`Withdrawal Amt.` vs `Deposit Amt.` were two
   `<td>`s' worth of text — blocks layer had the same merge, so no help there either).
2. **Combined layout (8 stmts):** it needed nothing — every token is present with correct coordinates
   (verified on clean_200_01: 5 clean header boxes, all 22 date/ref/amount tokens placed). The engine
   extracted 0 rows from complete input: row-grouping/anchor logic on the line layer is the gap.
   **This is the highest-value fix**: combined-layout input is recogniser-clean.
3. **rotated_180 (3 stmts):** orientation handling — PP-OCRv5's `use_doc_orientation_classify` is off
   in the service. Either enable it for lines mode or reject rotated pages earlier.
4. **skew (2 stmts):** header titles came back empty — below the line layer's confidence floor.

## Part 6 — teardown — PASS

All r9 containers + `r9net` removed; VRAM **1,221 MiB** (baseline). `airco_*`/`keycloak*`/`ue_*`/
`demo_*` untouched.

## Recommendation

- **Do not change the text-layer default** (branch C — lines serves nothing). Keep `blocks` default.
- The combined-layout `TOO_FEW_ROWS` is the bug to fix first: the recogniser's input is complete and
  correct there — the engine just can't group it. If that closes, combined statements serve and the
  measurement gets its first non-zero accuracy signal.
- Keep `OCR_SKIP_VL=1` as an opt-in speed tier — it is strictly cheaper and input-identical for the
  lines path, and meets the 4 s gate; but keep the VLM available as the second-reader.
- `use_doc_orientation_classify` off is why rotated pages die in lines mode — a service-side knob
  worth enabling in a later round.

## Remains unverified

Every accuracy number (0 served, all three configs); real scans (not run — synthetic only per rules);
whether a served statement is reachable at all; the 4 s gate in VL mode (fails: 6.2-6.6 s).
