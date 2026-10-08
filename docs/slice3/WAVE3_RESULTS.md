# WAVE 3 RESULTS — legacy hold, shadow wiring, final gate

Base: `devin/wave2` tip `f9af1cc`. Branch `devin/wave3`.
Baseline corpus: `comparison/wave2/baseline_*.jsonl` (14,445 files, wave2 tip).
Wave-3 full run: `comparison/wave3/full_0*.jsonl` (same corpus, branch tip).

## Task A — Bank of India: explicit LEGACY-HOLD

Commit `f39c7b2`.

- `LEGACY_ONLY_BANKS = {"bank_of_india"}` in `statement_engine/v2_router.py`.
- `route_pages` returns `RoutedExtraction("fallback", fallback_reason="legacy_only:bank_of_india")`
  as soon as the detector confidently names a legacy-only bank — before any layout
  resolution, and `allow_header_only=True` cannot override it.
- `bank_of_india` is not in `DETECTOR_TO_SPEC_BANK`; the bare marker `BANKOFINDIA`
  is deliberately unused (substring of STATEBANKOFINDIA / RESERVEBANKOFINDIA /
  CENTRALBANKOFINDIA — the substring trap is covered by unit tests with synthetic
  furniture text for SBI and Central Bank of India routes).
- Legacy BoI parser untouched.

### Unit tests (`test_registry_store_and_router.py` / shadow wiring)

- legacy-only detection falls back with `legacy_only:bank_of_india`;
- `allow_header_only` does not override the hold;
- SBI + Central Bank of India routes unaffected (substring trap).

### Corpus proof (BoI folder, 73 files)

| Outcome | Count |
|---------|-------|
| `legacy_only:bank_of_india` | 31 |
| `no_layout` | 21 |
| locked | 18 |
| scanned | 3 |
| v2 result / VERIFIED | **0** |

False-hold check (non-BoI files receiving `legacy_only`): **0** across the full
14,445-file corpus. Files in other folders detector-named as Bank of India: **0**.

## Task B — shadow wiring (`wiring:` commit `9b2964b`)

Changed files (3):

- `backend/app/services/statement_engine/shadow.py` (new) — `run_v2_shadow`,
  `STATEMENT_ENGINE_V2_MODE` flag, 60 s hard timeout, comparator call, PII-free record.
- `backend/app/services/pipeline_orchestrator.py` — 6-line hook after a successful
  legacy result (`status == "success"` gate).
- `backend/tests/statement_engine/test_shadow_wiring.py` (new).

Modes: `off` (default, byte-identical behaviour), `shadow` (implemented),
`serve` → raises immediately (`RuntimeError: serve is not enabled`).

Shadow record schema (asserted in tests): `sha8, bank_key, layout_id, v2_status,
fallback_reason, v2_verdict, overall, agree{opening,closing,rows,total_debit,
total_credit}, v2_ms, shadow_error?`. No transaction text, names, or account numbers.
Persistence: audit `JobEvent` (`v2_shadow` event) when `audit_service`/`job_id` are
present — lives under the existing 7-day retention (`DATA_RETENTION_DAYS`); otherwise
a one-line module-log fallback. Nothing from v2 touches disk elsewhere.

Fix during validation: the legacy verification report's `checks` is a dict keyed by
check name (not a list); `_legacy_extraction` reads `opening_closing_check.detail`
for opening/closing and `state` for `verification_status`.

### 200-file shadow run (real `process_statement`, off vs shadow per file)

Corpus: 19 files each × 11 legacy-servable banks (hdfc, axis, kotak, sbi,
bank_of_baroda, union, icici, paytm, canara, idfc, karnataka), sha-sorted.

| Metric | Value |
|--------|-------|
| Files | 200 (legacy success 124, legacy failed 76 — identical both modes) |
| Response-hash equality (excluding per-run `performance` + `excel_path` uuid) | **200/200 identical** |
| Shadow records | 124 (1 per legacy success, 0 on legacy failure) |
| Shadow exceptions escaping | 0 |
| v2 status | v2: 93, fallback: 31 |
| Comparator overall | MAJOR_DIFFERENCE 59, MINOR_DIFFERENCE 34, EXACT_MATCH 0 |
| v2 verdict | VERIFIED 88, FAILED 4, REVIEW 1 |
| v2 fallback reasons | no_layout 25, bank_unconfirmed 6 |
| Added latency | p50 222 ms, p95 3,215 ms, max 8.9 s (hard cap 60 s) |

Agreement on the 93 v2-extracted files: rows 77/93, total_debit 66/93,
total_credit 66/93, opening 77/81-known, closing 66/93. No `EXACT_MATCH` is expected:
the comparator is strict and compares v2 RAW rows against the legacy *final*
(post-repair) transactions, plus legacy metadata defects (account number format,
statement dates) count as MINOR. The point of shadow mode is that this signal is
recorded without any effect on the response.

## Task C — final gate (14,445-file corpus, branch tip, 4 workers)

### Headline

| Metric | Wave 3 | Phase 5 | Phase 4 |
|--------|--------|---------|---------|
| Files | 14,445 | 14,445 | — |
| Readable (non-unsupported) | 12,249 | — | — |
| v2 results | 8,275 | 7,587 | — |
| VERIFIED | 7,771 | 7,143 | — |
| Coverage (v2/readable) | **67.6%** | 61.9% | 65.7% |
| Trusted (VERIFIED/v2) | **93.9%** | 94.1% | 93.8% |

Verdicts on v2: VERIFIED 7,771, FAILED 368, REVIEW 136.
Fallback reasons (0 empty): no_layout 3,537 · bank_unconfirmed 202 ·
foreign_bank 82 · v2_failed:NO_ROWS 61 · legacy_only:bank_of_india 31 ·
other_bank:* 61 (rbl 24, uco 19, airtel_pb 4, deutsche 4, ippb 4, csb 3, tmb 2, …).

### Safety

- **Regression vs wave-2 baseline: 0 was-v2 files changed** status/verdict/layout.
  All 229 diffs are the expected wave-2 onboardings (fallback→v2), BoI→`legacy_only`
  (31), APGB→`foreign_bank` (2), plus refusal-reason moves (e.g. `other_bank:→no_layout`,
  `no_layout→bank_unconfirmed/foreign_bank` on SBI files) — no verdict regressions.
- **Wrong-bank VERIFIED: 0.** 19 cross-*folder* VERIFIEDs exist; every one carries
  positive evidence (document 15, detector 3, region 1) that the *file's own text*
  belongs to the matched bank — i.e. misfiled statements verified under their true
  bank (e.g. a CBI statement sitting in the Kotak folder, `ccca9c20`, detector had
  already named it `central_bank` in the wave-2 baseline).
- **Negative set**: zero v2/VERIFIED inside every refused or legacy-hold folder
  (BoI, CSB, APGB, UCO, Dhanlaxmi, Airtel, IPPB, Fincare, Cosmos, Deutsche, TMB,
  Fino, RBL, SBM — 0 v2 results).
- `legacy_only` on non-BoI folders: **0** (no false hold; no file outside
  "Bank of India" was detector-named BoI).
- `bank_evidence` on all 8,275 v2 results: detector 2,243 / document 4,200 /
  region 1,832 — **zero accepts with evidence `none`**.
- Empty fallback reasons: **0**.

### Determinism

- 200 files, two separate processes: **0 diffs** (status, layout, verdict, row
  count, row-hash all identical).
- 50 files shuffled × 4 workers vs sorted order: **0 diffs**.

### Performance

- Full-corpus route run: ~1.4 s/file average (4 workers, 14,445 files ≈ 85 min wall).
- Shadow added latency over legacy: p50 +222 ms, p95 +3.2 s, max +8.9 s (< 60 s cap).
- 5 largest readable files (4–8 MB, up to 160 pages): max 19.8 s, peak RSS 245 MB.

### Spec hygiene
- 45 registered layouts / 33 bank keys; every `extractors/<bank>/extractor.py` is the
  thin wrapper (1 function); layout modules contain only `LayoutSpec` literals —
  configuration-only claim holds. Opt-in field counts per layout: 4–12 each, all
  documented in `layout_spec.py` comments.
- `extractors/csb/` exists in the working tree only (untracked refuse-triage leftover,
  not registered, not committed).

### DB registry readiness (throwaway Postgres 16)
- `registry_to_rows` → `registry_from_rows` round-trip: identical, 45 layouts.
- `seed_sql` run twice: second run changed nothing (`config_version` untouched,
  md5 of rows identical, identical SQL output). 45 layouts / 33 banks / 30 families.

## Task D — repo data hygiene (plan only)

`comparison/wave3/GOLDEN_PII_PLAN.md` (untracked): golden snapshots carry
1,055 phone-like tokens, 11 emails, 315 IFSCs, and account numbers in 11+ filenames;
`queue.json` embeds customer paths. Plan gives a deterministic anonymisation that
keeps the golden tests meaningful, plus `git filter-repo` options and risks.
Nothing was executed.

## Commits

| Commit | What |
|--------|------|
| `f39c7b2` | legacy-hold: Bank of India stays on the legacy parser |
| `9b2964b` | wiring: STATEMENT_ENGINE_V2_MODE shadow hook |
