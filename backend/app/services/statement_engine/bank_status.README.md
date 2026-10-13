# bank_status.json — how to update it

Static data table consumed by `bank_status.py` to derive the additive
`support_state` field in `GET /api/statements/banks`. It is **data, not
logic** — derivation order lives in `bank_status.py`:

1. Bank is in the active v2 serve allowlist (`SERVE_BANKS`/`ONB_EXTRA_SERVE_BANKS`,
   `V2_MODE` includes serve) → `verified`, unless the table lists it as
   `review_required` (servable but can never reach VERIFIED, e.g. no printed
   balance anchors → every report is flagged needs-review).
2. Bank has a legacy processor (`PIPELINE_BANK_NAME`) → `legacy`.
3. Bank appears in the table or has specs/detector config → `coming_soon`.
4. Everything else → `unsupported`.

## Entry shape

```json
"yes": {
  "support_state": "coming_soon",
  "reason": "One-line, plain-language explanation shown to users."
}
```

Only `review_required`, `coming_soon` and `unsupported` belong here.
`verified` and `legacy` are derived automatically — do not add them.

## When a bank changes state

- **New bank onboarded to serve** → if it can reach VERIFIED, remove/keep its
  `coming_soon` entry harmlessly and add it to the serve allowlist; it derives
  `verified` automatically. If it can never reach VERIFIED (no printed
  anchors), change its entry to `"support_state": "review_required"` with a
  reason, then allowlist it.
- **Bank measured but not enabled** → `coming_soon` + reason.
- **Bank with too few samples / scanned corpus** → `unsupported` + reason.
- Keep `reason` short (one line), user-facing, and honest — it renders
  directly in the bank picker and on "<Bank> is not enabled yet" rows.
- Source of truth for states: `docs/PRODUCT_STATUS.md`. Keep the two in sync.
