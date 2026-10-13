# tools/verify2 — independent verification of serve candidates (prompt 28)

Checker tooling for `au_sfb` + `bank_of_maharashtra` promotion claims.
Everything here was written fresh for this verification; it reuses only the
corpus manifest (`sha8 -> path`) to locate files. No statement content is ever
printed or stored — only bank ids, counts, sha8s, and verdicts.

## Files

| tool | purpose |
|---|---|
| `measure2.py` | shadow-mode router pass over manifest sha8s; records status, layout, verdict, rows, detector notes. `--sha8-file=<list>` `--banks=a,b` |
| `audit2.py` | spec-independent audit: dated amount-bearing line count vs extracted rows, forward balance-chain recompute, generic open/close/total label scan vs implied balances. `--per-bank=K --seed=N` |
| `e2e2.py` | real-HTTP flow on the onb stack: analyze -> confirm/override -> process -> poll -> download -> workbook checks (sheets, Statement Check, formula errors). `--files=...` `--override=bank:sha8` |
| `ui2.py` | Playwright unified-flow check: sign-in, upload, review chips, bank dropdown, UNSUPPORTED row, widths 360/768/1280. Preinstalled Chromium only. |
| `wb_verify.py` | downloaded-workbook reconciliation: sheet row count vs audit rows, internal chain, implied open/close vs printed anchors. |
| `dupkeys.py` | counts duplicate composite transaction keys per file — the trigger for the shared `base_processor` order-rebuild row-leak defect. |

## Inputs

`.local/` holds the corpus manifest copies (`manifest_*.jsonl`, `folders.json`),
sha8 lists, run outputs, downloaded workbooks, and scratch debuggers
(`dbg_*.py`, `mk_*.py`, `analyze.py`, `dl_again.py`). `.local/` is not
evidence-grade output; the evidence lives in the `.jsonl` run records and
`docs/onboarding/VERIFY2_REPORT.md`.

## Environment

- `STATEMENT_ENGINE_V2_MODE=shadow` for offline measurement (set by the tools).
- E2E needs the onb stack: `http://localhost:8401` backend, `3400` frontend,
  keycloak on `:8080` (realm `airco-insights`, client `frontend-app`,
  user `test@airco.com`, password via `E2E_USER_PW`, client secret via
  `KC_SECRET`).
- `ONB_EXTRA_SERVE_BANKS=au_sfb,bank_of_maharashtra` for candidate serving.

## Method notes

- `audit2.py` is deliberately generic: it does NOT use spec regexes. Amount
  cells are matched unsigned/with leading `-`/`Cr|Dr` suffix/integer forms;
  labels scanned on squashed line text (`OpeningBalance`, `B/F`, bare
  `Total<amt><amt><amt>`); the amount read is the first amount AFTER the label
  so co-located labels cannot cross-read.
- Known benign artifacts handled: negative printed balances on overdrawn
  accounts (`-3,91,483.45`) and AU's integer-rupee amounts.
