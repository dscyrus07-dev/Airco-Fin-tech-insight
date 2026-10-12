# Feature flags — STATEMENT_ENGINE_*

Authoritative inventory for `devin/final-rc`. Every flag, its default, where it is
read, and whether the default is the safe one. Defaults are the values used when
the variable is unset (and what `docker-compose*.yml` injects when `.env` omits
them).

## Behaviour flags

| Flag | Default | Values | Read at | Consumers | Safe default? |
|---|---|---|---|---|---|
| `STATEMENT_ENGINE_V2_MODE` | `off` | `off` \| `shadow` \| `serve` | `statement_engine/shadow.py:35` (`v2_mode()`) | `serve.py:63`, `api/routes/statements_analyze.py:84`, `api/routes/upload.py:398`, `services/analysis_service.py:61`, `services/pipeline_orchestrator.py:421` | YES — `off` = V2 never runs |
| `STATEMENT_ENGINE_V2_SERVE_BANKS` | `""` (empty) | comma-separated spec bank keys | `statement_engine/serve.py:35` (`serve_banks()`) | `serve.py:66,296`, `statements_analyze.py:87`, `upload.py:402`, `analysis_service.py:61` | YES — empty = no bank served even in `serve` mode |
| `STATEMENT_ENGINE_UNIVERSAL_MODE` | `off` | `off` \| `shadow` \| `serve` | `statement_engine/universal/serve.py:26` (`mode()`) | `pipeline_orchestrator.py:428,454,473,524,540,583-603`, `statements_analyze.py:118`, `analysis_service.py:70` | YES — `off` = T3 reader never runs |
| `STATEMENT_ENGINE_MISMATCH_GUARD` | `1` (on) | `1`/`true`/`yes`/`on` vs anything else | `pipeline_orchestrator.py:168` (`_mismatch_guard()`) | orchestrator bank-mismatch guard | YES — guard ON by default; `0` explicitly disables the wrong-bank confirmation guard |

## Tuning flags (do not change routing behaviour)

| Flag | Default | Read at | Purpose |
|---|---|---|---|
| `STATEMENT_ENGINE_V2_SHADOW_TIMEOUT_S` | `20` | `shadow.py:26` | Inline shadow-run time budget |
| `STATEMENT_ENGINE_V2_SERVE_TIMEOUT_S` | `30` | `serve.py:26` | V2 serve worker-pool timeout |
| `STATEMENT_ENGINE_UNIVERSAL_TIMEOUT` | `45` | `universal/isolated.py:19` | T3 subprocess hard timeout |
| `STATEMENT_ENGINE_UNIVERSAL_MEM_MB` | `1536` | `universal/isolated.py:20` | T3 subprocess memory cap (rlimit; skipped on Windows) |

## Compose declarations

`docker-compose.local.yml:29-31` and `docker-compose.w11.yml:32-34` declare the
three behaviour flags with fallbacks matching the code defaults:

```
STATEMENT_ENGINE_V2_MODE: ${STATEMENT_ENGINE_V2_MODE:-off}
STATEMENT_ENGINE_V2_SERVE_BANKS: ${STATEMENT_ENGINE_V2_SERVE_BANKS:-}
STATEMENT_ENGINE_V2_SERVE_TIMEOUT_S: ${STATEMENT_ENGINE_V2_SERVE_TIMEOUT_S:-30}
```

`STATEMENT_ENGINE_UNIVERSAL_MODE` is **not** declared in compose — unset
containers therefore run it `off` (safe).

## Frontend

No `STATEMENT_ENGINE_*` variable is read by frontend code. The UI learns
engine state only from API response fields (`v2`, `universal` blocks,
`engines`, verdicts).

## Semantics

- `off` — the engine never runs. Output is byte-/cell-identical to the
  pre-V2 baseline commit `880b5e2` (verified in Stage 2.4).
- `shadow` — engine runs, result is recorded in the response `v2`/`universal`
  block for comparison, never served.
- `serve` — V2 rows may be returned **only** for banks in
  `STATEMENT_ENGINE_V2_SERVE_BANKS`. T3 universal rows may be returned only as
  `REVIEW` (T3 cannot emit `VERIFIED` by design).

## Kill switches

Setting any behaviour flag to `off` (V2) or removing a bank from the serve
allowlist takes effect on the next request — no rebuild required
(env is read per-call, except the two `*_TIMEOUT_S`/mem constants which are
read at module import).
