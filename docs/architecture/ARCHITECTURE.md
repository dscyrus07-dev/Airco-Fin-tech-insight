# Architecture — statement engine

Authoritative map of the statement pipeline on `devin/final-rc`. Replaces
`docs/archive/ARCHITECTURE_PREV.md` (pre-V2).

## Request flow

```
upload ──► analyze ──► confirm ──► process ──► jobs ──► download (.xlsx)
```

API: `backend/app/api/routes/{upload,statements_analyze,statements_process,jobs}.py`
Orchestration: `backend/app/services/pipeline_orchestrator.py` (`process_statement`)

## Tiers

| Tier | What serves it | Code | Verdict ceiling |
|---|---|---|---|
| T1 | Legacy bank processor | `app/services/banks/<bank>/parser.py` | none (legacy "success") |
| T2 | Registered `LayoutSpec` + shared engine | `statement_engine/extractors/<bank>/layout_spec.py` | `VERIFIED` |
| T3 | Universal reader (runtime-inferred layout) | `statement_engine/universal/{infer,reader}.py` | `REVIEW` — cannot emit `VERIFIED` |

## Detection & evidence

`statement_engine/detector.py` — bank detection from header/footer text +
metadata; emits `bank_evidence` (bank, confidence, score) and `runner_up`.
`statement_engine/extraction/registry.py` — `LayoutRegistry`: resolves a PDF to
a `LayoutSpec` by header fingerprint; resolution is evidence-gated (ambiguous →
fallback, never silent accept).

## Layout & engine

- `LayoutSpec` (`extraction/layout_spec.py`): declarative column/anchor spec —
  date+money column positions, title synonyms, `ignore_line_res`,
  `period_re`/`page_break_re` region markers, `single_amount_column`, etc.
- Engine (`extraction/engine.py` + `anchors.py`, `rows.py`, `normalize.py`,
  `spec_codec.py`): `extract_pages(pages, spec) -> V2Outcome` — finds the
  transaction table per page, assembles dated rows, normalizes amounts/side.
- `v2_router.py::route_pdf` — detector → registry → engine → outcome
  (`status`, `layout_id`, `fallback_reason`, `notes`, transactions, verdict,
  checks).

## Checks & verdict

`extraction/checks.py` — independent verification on engine rows:
chain (balance continuity), side, reference, totals, date, schema, warnings.
Verdict ∈ `VERIFIED | REVIEW | FAILED`; `needs_review`, `review_codes`,
`anchored`, `detected_bank` also emitted. Checks are frozen (no changes this
wave); a `REVIEW`/`FAILED` never silently serves as good data.

## Serving

`statement_engine/serve.py` — serve path gated by
`STATEMENT_ENGINE_V2_MODE` + `STATEMENT_ENGINE_V2_SERVE_BANKS`
(see `docs/operations/FEATURE_FLAGS.md`). `serve.py` also appends the
`Statement Check` worksheet to the workbook and writes audit records.
`statement_engine/shadow.py` — shadow mode: run V2, record, never serve.

## Universal reader (T3)

`universal/infer.py` — infers a runtime spec from page geometry + header
vocabulary (`universal/lexicon.py`). `universal/reader.py::read` — failure-code
results (`NO_DATES`, `LOW_CONFIDENCE_COLUMNS`, `GLYPH_DUMP`, `MULTI_STATEMENT`,
`TIME_BUDGET`, …). `universal/isolated.py` — subprocess isolation (45 s /
1.5 GB budget). `universal/serve.py` — `block_for`/`engine_block_for` response
blocks, audit hooks. Gated by `STATEMENT_ENGINE_UNIVERSAL_MODE`
(off|shadow|serve); T3 runs only when T1/T2 produced nothing usable, and its
verdict is capped at `REVIEW`.

## Orchestrator wiring (read order)

`pipeline_orchestrator.py` around lines 421–660:

1. `_v2serve.v2_mode()` + `serve_banks()` → serve/shadow plan (T2)
2. `_userv.mode()` → universal plan (T3)
3. Legacy processor class lookup (T1)
4. Order: legacy/v2 serve → shadow observe → T3 only-if-nothing-usable
5. Response: `statement_engine` block (engine, mode, layout_id, verdict,
   needs_review, review_codes, anchored, detected_bank, advisory, `universal`
   sub-block when T3 ran) + optional `Statement Check` sheet append
6. `_mismatch_guard()` — wrong-bank confirmation guard
   (`STATEMENT_ENGINE_MISMATCH_GUARD`, default on)

## Downstream pipeline (unchanged by engine tier)

Rows → categorization (`pipeline/classification/`) → aggregation → Excel
(`frontend_result_builder.py`, report generators) → job store (Redis) →
download. V2/T3 rows reuse the identical path; that is what makes
off-vs-serve workbook cell-identity meaningful.

## UI

`frontend/app/components/analyze/AnalyzeFlow.tsx` — analyze/confirm UX incl.
honest unsupported/scanned messages and the "Other bank" entry (universal
serve only). `frontend/app/components/results/engine/` — `VerificationBadge`
(T2 `VERIFIED`/`REVIEW`, T3 general-reader badge, `BANK_MISMATCH` flag).
Dashboard bank chips + landing count come from
`/api/upload/supported-banks` (registry-derived).

## Onboarding a bank by configuration (U4 pipeline)

`backend/tools/propose_layouts.py` — clusters T3-clean files by header+geometry
fingerprint, emits draft `LayoutSpec` sources + a gate report.
`backend/tools/regression_gate.py` + `backend/tests/regression_manifest.json`
— hash-locked 19-file corpus gate (verdict/code/rows/row_hash must not move).
Onboard = land a generated spec → evidence gates (mutation, wrong-bank,
comparator) → allowlist entry — never by happy-path success alone.
