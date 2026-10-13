# tools/verify3 — prompt-31 verification tooling

Reports + tooling only; no product code. Everything runs against the `onb` stack
(backend `http://127.0.0.1:8401`, frontend `http://localhost:3400`, keycloak
`http://localhost:8080` realm `airco-insights`, user `test@airco.com`).

## Files

- `e2e_local.py` — real-HTTP e2e for arbitrary PDF paths (synthetics).
  `analyze -> confirm/override -> process -> poll -> download -> workbook checks`.
  `python tools/verify3/e2e_local.py backend out.jsonl --files=/path/a.pdf,... [--override=bank:filekey]`
  env: `KC_SECRET` (client secret), `E2E_USER_PW`.
  Use this for synthetics; use `tools/verify2/e2e2.py` for corpus sha8s — **warning:
  e2e2.py opens the output file in `w` mode and clobbers prior records; write each
  run to a separate file.**
- `ui3.mjs` — Playwright UI e2e (run from a worktree that has `frontend/node_modules`,
  e.g. `wt-ui/frontend`). `EXTRAS=1` asserts the 7 enable-list banks' states +
  one full flow each; default run asserts the revert. Shots -> `e2e/shots3/`.
- `.local/` — all raw records (jsonl per batch, `dl/` downloaded workbooks,
  `probes/` generated probe PDFs).
- Regression: `tools/verify2/measure2.py` against a `backend` dir; lists in
  `.local/sha8_*.txt`; baselines `reg_tip_*` (54f51ab) vs `regnow_*`/`regextra_*` (tip).

## Notes

- `localhost:8401` hangs on IPv6 for in-page and some client fetches — always use
  `127.0.0.1`.
- Corpus paths come from `tools/verify2/.local/manifest_*.jsonl` (sha8 -> path).
- Synthetic PDFs were generated with reportlab (Temp scripts); `synth_*` PDFs live in
  `%TEMP%`. Layout-shaped synthetics must match the bank's header geometry or the
  router honestly refuses (`routed=None` -> `bank_routing` failure).
