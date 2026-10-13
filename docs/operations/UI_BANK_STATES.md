# UI bank states — honest per-bank support display

With ~44 known banks the UI cannot present one flat "supported" list. Every
bank now carries a `support_state`, derived from the serve configuration plus
a static data table. The UI groups by that state and never invents a default.

## The five states

| state | meaning | selectable | shown where |
|---|---|---|---|
| `verified` | served by the v2 engine; can reach VERIFIED | yes | picker + panel |
| `review_required` | served, but can never reach VERIFIED (e.g. no printed balance anchors); every report is flagged needs-review | yes | picker + panel + persistent result notice |
| `legacy` | served by the legacy parser only | yes | picker + panel |
| `coming_soon` | detected and measured on samples, not enabled | no (greyed) | picker + panel |
| `unsupported` | scanned/too few samples/no layout | no (greyed) | picker + panel |

## Data flow

```
banks/*.json  (detector registry) ─┐
spec registry (LayoutSpec keys)   ─┼─> bank_status.py ──> GET /api/statements/banks
SERVE_BANKS + V2_MODE env         ─┤     (derivation)        └─ all_banks[] {id,name,support_state,reason}
bank_status.json  (static table)  ─┘                          └─ banks[]    {…, support_state}  (unchanged list + new field)
PIPELINE_BANK_NAME (legacy)       ─┘
```

- `banks[]` is **unchanged**: only banks that can actually be processed, same
  ids/order. `all_banks[]` is additive and covers every known bank id
  (registry ids plus orphan spec keys like `apgv`; spec aliases such as
  `scb`/`bob` fold into their registry id).
- Derivation order: v2-served → `verified` (or `review_required` when the
  table declares the ceiling) → legacy processor → `legacy` → table/spec
  presence → `coming_soon` → else `unsupported`.
- `bank_status.json` holds only `review_required`/`coming_soon`/`unsupported`
  entries + reasons. Update rules: `backend/app/services/statement_engine/bank_status.README.md`.

## Frontend surfaces

| surface | component | behaviour |
|---|---|---|
| review-row bank picker | `app/components/bank/BankSelect.tsx` | optgroup per state; non-servable options disabled + text tag; search box when >12 entries; native select = keyboard + SR free |
| supported-banks copy | `app/components/bank/BankSupportPanel.tsx` | counts + names from `all_banks`; collapsible full list with icon + text + reason per row |
| unsupported document row | `ReviewTable.tsx`, `AnalyzeFlow.tsx` | "`<Bank>` is not enabled yet — <reason>"; no default bank, no Confirm |
| result view | `results/engine/BankStateNotice.tsx` | persistent "…reports always need review" banner for `review_required` banks, next to the badge |
| legacy dashboard flow | `layout/StepForm.tsx` | same grouping via optgroups; fallback = bundled servable list |
| landing count | `app/page.tsx` | `count` from `/api/upload/supported-banks` (servable only) |

Colour is never the only signal: every state also renders an icon
(✓ ⚠ ◦ ◷ ✕) and a text tag.

## Hard-coded lists that remain (and why)

- `lib/banks.ts` `FALLBACK_BANK_LIST` / `SUPPORTED_BANK_OPTIONS` — offline
  fallback only, limited to the shipped-default servable banks; required so
  the UI still works when the API is unreachable.
- `types/index.ts` `BankName` union — compile-time names for the legacy
  dashboard flow which keys files by display name; extended to every registry
  `display_name`. The analyze-first flow is id-keyed and fully API-derived.
- `bank_status.json` — the static table itself (data, not logic).

## Testing

- backend: `tests/test_statements_analyze_api.py` — additive `all_banks`,
  coverage of every known id, allowlist flip to `verified`, review-ceiling
  stays `review_required`.
- frontend: `app/components/bank/__tests__/BankSelect.test.tsx`,
  `results/engine/__tests__/BankStateNotice.test.tsx`,
  extended `ReviewTable` + `StepForm` tests.
- e2e: `e2e/ui_banks_e2e.mjs` on the onb stack (3400/8401), synthetic PDFs.
