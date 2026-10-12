# V2 API contract changes — universal reader (T3)

Additive to `V2_API_CONTRACT.md`. All gated by
`STATEMENT_ENGINE_UNIVERSAL_MODE=off|shadow|serve` (default `off`). With `off`,
responses are byte-identical to the previous contract.

## Tier order

| tier | engine | verdict ceiling |
|---|---|---|
| T0 | — | unreadable (no text layer / glyph dump / locked): plain message, nothing runs |
| T1 | `v2` | VERIFIED (registered layout + bank evidence) — unchanged |
| T2 | `legacy` | as today, never VERIFIED — unchanged |
| T3 | `universal` | **REVIEW** (code `GENERAL_READER`); FAILED when checks fail; never VERIFIED |

T3 only runs when T1 and T2 produced no usable result. `shadow` records the
`universal` sub-block and serves nothing. `serve` passes REVIEW rows through
the same downstream steps (categorisation, Excel + `Statement Check` sheet,
history); FAILED carries no data and fails the job honestly.

## New review code

`GENERAL_READER` — the layout was inferred at runtime; the figures must be
checked against the statement. Always accompanied by `needs_review: true`,
`anchored: false`.

## `statement_engine` block additions

When T3 serves the result:

```json
"statement_engine": {
  "engine": "universal",
  "mode": "serve",
  "layout_id": "universal_auto",
  "verdict": "REVIEW",
  "needs_review": true,
  "review_codes": ["GENERAL_READER"],
  "anchored": false,
  "detected_bank": { ... unchanged ... },
  "advisory": null,
  "universal": { ... }
}
```

The `universal` sub-block is present whenever a T3 attempt ran (serve or
shadow, served or not):

```json
"universal": {
  "tier": "T3",
  "engine": "universal",
  "mode": "serve",
  "served": true,
  "verdict": "REVIEW | FAILED | <T0 code>",
  "code": "GENERAL_READER | <failure code>",
  "needs_review": true,
  "review_codes": ["GENERAL_READER"],
  "anchored": false,
  "bank_hint": "<detector bank name or 'Unknown bank'>",
  "rows": 0,
  "elapsed_ms": 0,
  "pre_cap_verdict": "REVIEW | VERIFIED | FAILED",
  "infer": {"header": true, "money": "...", "date_shape": "...",
            "amount_form": "...", "margin": {...}}
}
```

No statement content appears in the block (§5 unchanged).

## `GET /api/statements/banks`

Under universal `serve` the response gains a synthetic entry
`{"id": "other", "name": "Other bank / not listed", "engines": ["universal"]}`.
An `OVERRIDE` confirm with `bank_id: "other"` is accepted under serve and
routes to auto-detect → T3. Absent under `off`/`shadow`.

## `GET /api/upload/supported-banks`

Now derived from the bank registry instead of a hardcoded list; gains a
`count` field. Legacy fields unchanged.

## Analyse document fields (unchanged shape)

- Detected-but-not-onboarded bank with a text layer, flag on: `state` stays
  confirmable (`REVIEW`), `bank.supported: true`, message = the
  general-reader sentence.
- Flag off: `state: "UNSUPPORTED"`, message "This bank isn't fully supported
  yet." — the scanned/image-based wording applies only to
  `detail_state: "UNSUPPORTED_SCANNED_PDF"` (T0).
