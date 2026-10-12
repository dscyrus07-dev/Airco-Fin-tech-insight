# Engine observability

Structured job events emitted per extraction tier. No content is recorded —
tier, bank, layout, verdict, codes, timings only.

## Events

| event_type | emitted when | metadata |
|---|---|---|
| `v2_serve_decision` | every processed job (mode≠off) | full `statement_engine` block: engine, mode, layout_id, verdict, needs_review, review_codes, anchored, detected_bank |
| `t3_universal_decision` | every T3 attempt (universal mode≠off, no tier served) | `universal` sub-block: tier, verdict, code, needs_review, rows, elapsed_ms, pre_cap_verdict, infer{} |
| `v2_shadow` (existing) | legacy success path | shadow comparison block |

## Counters to watch

- `t3_universal_decision` rate: share of jobs that reached T3 (T1+T2 both
  failed/absent). A rising share means new-bank volume or a regression in the
  registered tiers.
- `code` distribution: `GENERAL_READER` (served REVIEW) vs failure codes
  (`NO_TABLE_HEADER`, `LOW_CONFIDENCE_COLUMNS`, `TIME_BUDGET`, `NO_TEXT_LAYER`,
  `GLYPH_DUMP`, `LOCKED`, `CHECKS_FAILED`, `MULTI_STATEMENT`, `NON_STATEMENT`,
  `CRASH`). `CRASH` or `TIME_BUDGET` above zero is an engineering signal, not a
  data signal.
- `pre_cap_verdict`: `VERIFIED` means checks passed pre-cap; paired with
  `verdict: REVIEW` this is the T3 population that could later be considered
  for elevation (decision pending U3 numbers — see REPORT).
- `elapsed_ms`: p50/p95 per tier. T3 carries a hard budget
  (`STATEMENT_ENGINE_UNIVERSAL_TIMEOUT`, default 45 s isolated) plus an
  internal 20 s inference/extraction budget; overruns surface as
  `TIME_BUDGET`, never a stall.
- `infer.margin`: column-assignment margin. Low-margin layouts should be
  rare among served files; they FAILED instead of guessing.

## Guards

- Isolation: T3 runs in a child process (spawn). Timeout → terminate →
  `FAILED/TIME_BUDGET`. POSIX sets `RLIMIT_AS` (default 1.5 GB,
  `STATEMENT_ENGINE_UNIVERSAL_MEM_MB`); Windows dev skips the rlimit.
- Idempotency: the reader is deterministic (no AI, no clock-dependent
  decisions) — same file, same verdict, same rows. Double submission is
  handled by the existing job pipeline, not by T3.
- Regression: `backend/tools/regression_gate.py` replays the hash-locked set
  in `backend/tests/regression_manifest.json` (sha8 + verdict + row-hash only)
  and fails on any change.
