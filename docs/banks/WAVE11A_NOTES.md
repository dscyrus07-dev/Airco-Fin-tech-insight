# Wave 11A notes — product safety net, history badges, lint

Branch: `devin/wave11` (from `demo/rc` @ `c022630`, local only).

## T1 — wrong-bank guard

- New guard in `pipeline_orchestrator` (`_mismatch_detect` + `_apply_mismatch_flag`):
  after a successful legacy result, runs the Slice-2 detector on first-3-page
  text (pdfplumber, no extraction). If the detector is HIGH/VERY_HIGH for a
  *different supported* bank, the `statement_engine` block gets
  `needs_review=true`, `review_codes += BANK_MISMATCH`, `detected_bank`.
- Never blocks, never switches banks, downloads unaffected. Env flag
  `STATEMENT_ENGINE_MISMATCH_GUARD` (default on; `0` = zero behaviour change).
- UI: prominent `role="alert"` banner above the details panel with the
  wording "The statement looks like it is from a different bank than the one
  you selected." Verified badge never renders (needs_review + engine=legacy).
- False-alarm eval: **300 corpus files** (sha-sorted, round-robin across the
  15 supported-bank folders, own folder selected): **0 false flags** (target
  0; restriction not needed). Eval: `comparison/wave11/mismatch_eval.py`.
- Tests: `tests/test_mismatch_guard.py` — 11 cases (match, mismatch,
  UNKNOWN/LOW/MEDIUM, unsupported, flag-off, flag-off-no-detect, failure-safe).

## T2 — history badges

- `user_file_records.statement_engine` JSONB column (additive auto-DDL in
  `session.py`, same pattern as batch_id/retention columns).
- `mark_completed` persists `result_data["statement_engine"]`; `_entry_payload`
  returns it on uploads and reports. Old rows → `null`, UI unchanged.
- Tests: `tests/test_history_statement_engine.py` — 4 cases via the
  OperationalError fallback path (persist, report entry, legacy-null, shape).

## T3 — lint

- `next lint` removed in Next 16 → flat config `eslint.config.mjs` using
  `eslint-config-next/core-web-vitals` flat export.
- Pinned devDeps: `eslint@9.39.5`, `eslint-config-next@16.2.4` (exact match
  to installed next@16.2.4 so rule set tracks the framework), `@eslint/eslintrc@3.3.7`.
- Baseline: **11 errors + 1 warning**. After legit fixes: **0 errors, 0 warnings**.
  No rules disabled; no `eslint-disable` comments added.
- Fixes: invalid `useAuth()` hook call in `lib/api.ts` (now uses
  `getValidSessionAccessToken`), localStorage restore → lazy `useState`
  initializers (Dashboard), recursive callback → named function expression
  (Dashboard retry), step-4 guard → render-time state correction,
  ProcessingStep phase machine → derived value + `key={jobId}` remount,
  isDesktop → lazy init + resize subscription, batch-result pick → derived
  selection, ApiKeyList fetch deferred to microtask, 2× `&apos;` escapes,
  named config export.

## T4 — friendly states

- UNKNOWN state gets a plain-language box ("We could not tell which bank
  issued this statement…"); UNSUPPORTED box retained. Neither says "error".
- "Supported banks" note under the analyze controls, sourced from
  `listBanks()` with `FALLBACK_BANK_LIST` fallback preserved.

## T5 — validation counts

| check | result |
|---|---|
| backend suite (pikepdf-env files ignored) | 451 passed, 18 skipped, 8 failed* |
| new backend tests | 15 passed |
| `npx tsc --noEmit` | 0 errors |
| `npm run lint` | 0 errors, 0 warnings |
| vitest | 29 passed |
| `npm run build` | pass |
| offline render, 4 block shapes | VERIFIED, REVIEW/NO_INDEPENDENT_ANCHOR, FAILED-as-legacy, legacy+BANK_MISMATCH — all in `statementEngine.test.tsx` + snapshot |
| flag-off vs `880b5e2` (3 corpus files: status, stats, sheet names, numeric hash) | 3/3 identical |
| guard on vs guard off (same 3 files) | 3/3 identical |
| detector false alarms (300 corpus files) | 0 |

\* all 8 are baseline failures also present on the unmodified base: missing
sample PDFs (`test_axis_parser`, `test_canara_parser`, `test_icici_parser`,
`test_finbit_analytics`), rule-engine table drift
(`test_json_rule_engine` ×2), Windows event-loop env
(`test_api_key_service` rate-limit). Not touched by this wave.
