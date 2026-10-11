# V2 serving design note (Wave 8)

Goal: serve the v2 statement engine inside `process_statement`, flag-gated and off
by default, per `V2_API_CONTRACT.md` (authoritative). Track B scope: no changes to
`extractors/**`, `extraction/checks.py`, `extraction/registry.py`, detector data,
or legacy parsers (single additive `engine-hook:` in `base_processor.py`).

## Decision point

One place: `pipeline_orchestrator.process_statement`. Both entry points
(`/api/statements/{id}/process` and `POST /api/v1/statements`, plus the async
consumer) call it, so every entry behaves identically.

## Modes (`statement_engine.serve`)

- `v2_mode()` gains `"serve"` (contract §1: unsupported values are logged and
  treated as `off`; `serve` is now supported). `run_v2_shadow` still only acts on
  `shadow` — behaviour unchanged.
- `serve_banks()` reads `STATEMENT_ENGINE_V2_SERVE_BANKS` (comma-separated spec
  bank keys; empty = none, even in `serve`).

## Routing (serve mode only, allowlisted banks only)

`route_for_serve()` reads pages once, calls `detect_spec_bank(pages)` for the
detector outcome, then `route_pages(pages, DEFAULT_REGISTRY, spec_key)` — the
same production router, detector evidence and gates as shadow. Hard timeout via
a single-worker pool (env `STATEMENT_ENGINE_V2_SERVE_TIMEOUT_S`, default 30s).
Any read/route error or timeout degrades to "v2 unavailable" → legacy unchanged.

Pipeline `bank_key` → spec key via `DETECTOR_TO_SPEC_BANK` (bob/union/etc.).

## Policy (contract §2)

| v2 outcome | legacy available & ok | served |
|---|---|---|
| VERIFIED | any | v2 rows (`engine:"v2"`) |
| REVIEW | yes | legacy + `advisory` |
| REVIEW | no parser / legacy failed | v2 rows + `needs_review:true` |
| FAILED | yes | legacy + `advisory` |
| FAILED | no parser / failed | existing error path (v2 never served) |
| fallback/unsupported/timeout/error | any | legacy, unchanged |

Bank mismatch guard (§6): when the detector is confident (MEDIUM+) and names a
different spec bank than the one selected, v2 rows are never served; the block
carries `detected_bank.source="detector"` + `BANK_MISMATCH` and the user's bank
runs as today.

Auto-detect: `bank_key` "unknown"/"auto" routes with `bank_key=""` so the
detector drives layout resolution; a routed v2 result names
`detected_bank.source="detector"` and, when served, runs through that bank's
legacy processor if present, else `UnknownProcessor`'s shared steps.

## Serving the rows (engine-hook)

`BaseBankProcessor._run_pipeline(..., row_source=None)` — keyword-only, default
None. When given, steps 1–4 (pdf/structure validation, parse, txn validation)
are skipped and the supplied `V2RowSource` seeds `structure_result`- /
`parse_result`-shaped namespaces plus `validated` txn dicts. Steps 5–10
(repair, reconcile, classify, recurring, aggregate, integrity, dates, Excel)
are literally the same code — composition alternative would duplicate ~250
lines and drift. With `row_source=None` the diff is a single `if` around the
existing block: legacy output is byte-identical by construction (proved in the
hook commit with a sheet-name + cell-hash test).

`V2RowSource` is built from `RoutedExtraction.result`: `transactions` are
`NormalizedTransaction.to_dict()`s; summary/period/account fields seed the
metadata namespace (extras stay out of the served path).

## Response block (`statement_engine` key, contract §3)

Always present in `process_statement`'s dict (additive). `off` →
`{"engine":"legacy","mode":"off"}`. Fields: engine, mode, layout_id, verdict,
needs_review, review_codes, anchored, detected_bank, advisory.

- `review_codes` (§4) are derived from `result.metadata.extras.checks`
  per-check statuses — never from message text: reference skipped →
  NO_INDEPENDENT_ANCHOR, failed → REFERENCE_MISMATCH; chain failed →
  CHAIN_BREAK; side fail/warn → SIDE_MISMATCH; totals fail/warn →
  TOTALS_MISMATCH; dates warn → DATE_ORDER; date_outliers warn → DATE_OUTLIER;
  period warn → OUTSIDE_PERIOD; schema failed → SCHEMA_ERRORS; engine warnings
  → EXTRACTION_WARNINGS; detector mismatch → BANK_MISMATCH.
- `anchored` = reference check ran and passed.
- `advisory` present only when legacy rows are served and a v2 verdict exists
  (REVIEW or FAILED). A bare fallback/timeout yields no advisory — nothing
  meaningful was verified.
- `verdict`/`review_codes` describe the engine that produced the served rows:
  legacy-served rows carry verdict null; the v2 outcome lives in `advisory`.

The block is attached to the returned dict (which `build_frontend_processing_result`
passes through → job result), and emitted as audit job event
`v2_serve_decision` (block only — no statement content, §5).

## Excel — `Statement Check` sheet

Appended post-generation by the serve layer (`append_statement_check_sheet`)
whenever the block says `engine:"v2"` or `needs_review` or an `advisory`
exists: verdict, engine, review reasons (codes), anchor yes/no, generated
timestamp — appended AFTER existing sheets via openpyxl, never altering them.
Mode `off` never touches the workbook → byte-identical trivially.

## Banks endpoint (§7)

`GET /api/statements/banks` entries keep every field/order and gain
`engines` (`["legacy"]`, `["legacy","v2"]` or `["v2"]`) and `v2_served`
(`mode=="serve" and spec_key in serve_banks()`). v2-only banks (specs whose
bank has no legacy processor key) are appended only when `v2_served`. The
response never lists a bank that cannot be processed.

## Privacy

Block/audit carry verdict, codes, layout_id, sha-free flags only — no
narrations, names, account numbers, amounts (§5). Parity output is aggregate
hashes/counts keyed by sha8.
