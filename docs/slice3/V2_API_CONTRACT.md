# Statement Engine V2: API and serving contract (v1)

Status: contract only. Everything is additive and behind flags that default to OFF. Nothing in this document changes the
legacy response for existing clients.

## 1. Modes
`STATEMENT_ENGINE_V2_MODE`: `off` (default) | `shadow` (compare, never serve) | `serve` (policy below).
`STATEMENT_ENGINE_V2_SERVE_BANKS`: comma-separated spec bank keys allowed to be served (default empty = none, even in `serve`).
An unsupported value of the mode flag is logged and treated as `off`; it never interrupts a request.

## 2. Serving policy (applies only in `serve`, only for allow-listed banks)
| v2 verdict | legacy result | what is served |
|---|---|---|
| VERIFIED | any | v2 (`engine: "v2"`) |
| REVIEW | legacy success | legacy (`engine: "legacy"`), v2 outcome attached as `advisory` |
| REVIEW | no legacy parser for the bank, or legacy failed | v2 rows, `needs_review: true` |
| FAILED | any | never served as data; legacy if it succeeded (with `advisory`), otherwise the existing error path |
| v2 fallback / error / timeout | any | legacy, unchanged |

Served v2 rows go through the SAME downstream steps as legacy rows (categorisation, reconciliation, aggregation, Excel).

## 3. Response block (additive key `statement_engine` on the analyse/job result)
```json
"statement_engine": {
  "engine": "v2" | "legacy",
  "mode": "off" | "shadow" | "serve",
  "layout_id": "string | null",
  "verdict": "VERIFIED" | "REVIEW" | "FAILED" | null,
  "needs_review": true,
  "review_codes": ["NO_INDEPENDENT_ANCHOR"],
  "anchored": true,
  "detected_bank": {"key": "string", "name": "string", "confidence": "HIGH", "source": "detector" | "user"},
  "advisory": {"verdict": "REVIEW", "review_codes": ["CHAIN_BREAK"], "layout_id": "string"}
}
```
`verdict`/`review_codes` describe the engine that produced the served rows. `advisory` is present only when legacy rows were served
and v2 also ran. With mode `off` the block is `{"engine": "legacy", "mode": "off"}` and every other field is null/false.

## 4. Review codes (stable, machine-readable; derived from the per-check statuses, never from message text)
| code | source |
|---|---|
| NO_INDEPENDENT_ANCHOR | `reference` check skipped (no printed opening/closing balance) |
| REFERENCE_MISMATCH | `reference` failed |
| CHAIN_BREAK | `chain` failed |
| SIDE_MISMATCH | `side` failed or warned |
| TOTALS_MISMATCH | `totals` failed or warned |
| DATE_ORDER | `dates` warned |
| DATE_OUTLIER | `date_outliers` warned |
| OUTSIDE_PERIOD | `period` warned |
| SCHEMA_ERRORS | `schema` failed |
| EXTRACTION_WARNINGS | engine warnings present |
User-facing wording for each code is defined by the UI; the API returns only codes.

## 5. Privacy and retention
The block contains no statement content (no narrations, names, account numbers, amounts). Job events store this block and nothing
else from v2. No new storage of statement data; the existing 7-day retention applies.

## 6. Detected bank
When the user selected "Auto-detect" (or an unknown/other bank), the Slice 2 detector chooses the bank if its confidence is MEDIUM or
higher; otherwise the request fails with the existing "unsupported bank" error. A user-selected bank is never silently overridden:
if the detector confidently names a different bank, the response carries `detected_bank.source = "detector"` and a
`BANK_MISMATCH` review code, and the user-selected bank's processor is still used.
