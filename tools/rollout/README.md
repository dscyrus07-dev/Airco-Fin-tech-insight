# tools/rollout — prompt-32 rollout verification

Re-verifies the 14-bank `onb` served list at `411f6ca` (integrity-guard float
fix + compose default). Product code is untouched; this dir is tooling only.

| File | Purpose |
|---|---|
| `enrich_validation.py` | Back-fills `validation.*` (`reconciliation_passed`, `integrity_passed`) + `statement_engine` block into `e2e2.py` records — `e2e2` can read `result_data` before `validation` is persisted, so this re-queries each `job_id` once the job is complete. |
| `ui_ro.mjs` | Playwright smoke on `:3400`: catalog states, panel at 360/1280, one upload→confirm→process→report flow per served bank (14), plus a 5-file mixed batch (review-only / unsupported / non-enabled / verified / legacy). Run from a dir that resolves `playwright` (e.g. copy into `wt-ui/frontend`). |
| `.local/` | run artifacts (sha8 lists, `ro_*.jsonl` records, downloads) — not committed. |

Reused from earlier rounds: `tools/verify2/e2e2.py` (analyze→confirm→
process→poll→download→workbook checks; note it opens its out-file with `"w"`
— one out-file per shard), `tools/verify2/measure2.py` (shadow router pass
for regression), `tools/verify3/reg_compare.py` (record compare).

## What was run (all on the onb stack, 127.0.0.1:8401)

1. Image proof: `restore_statement_order`, `apply_row_count_guard`, `_num`
   float coercion, `SOUTHINDIANBANK` marker, PNB `amountinr` variant,
   spec count 97 = repo, `bank_status.json` present.
2. `/api/statements/banks`: 44 `all_banks`; exactly the 14 rollout ids
   `v2_served: true` (10 `verified` + 4 `review_required`).
3. Integrity e2e: 3 files × 14 banks (`sha8_i*.txt` → `ro_i*.jsonl`), then
   `enrich_validation.py` for `integrity_passed`.
4. Legacy compare: 2 files × 8 legacy-only banks (`sha8_legacy.txt` →
   `ro_legacy.jsonl`); payload vs `bc2cc17` bounded by the product diff
   (`_num` only → `integrity_passed` is the only movable field) + sheet-name
   comparison vs the bc2cc17-era legacy workbook.
5. Regression: 734 sha8s (`sha8_reg_all.txt` = the V3 650 + 84 set),
   measured on the tip via `measure2.py`, compared to the `bc2cc17` baseline
   (`wt-v3` `regnow_*` + `regextra_now`) with `reg_compare.py` → 0 diffs.
6. UI smoke: `ui_ro.mjs` (see above).

Numbers and tables: `docs/onboarding/ROLLOUT_REPORT.md`.
