# tools/n7 — N7 integration-verification tooling

Reports + tooling only; no product code. Everything runs against the `onb`
stack rebuilt from the integrated tip `devin/n7-integrate`
(backend `http://127.0.0.1:8401`, frontend `http://localhost:3400`,
keycloak `http://localhost:8080` realm `airco-insights`, user `test@airco.com`).

## Candidates

N5 yielded zero serve candidates (all `SHADOW_ONLY`); the N7 candidate set is
N6's six `SERVE_V2_WITH_LEGACY_FALLBACK` banks (spec keys):
`bob, canara, icici, indian_bank, karnataka, kotak`.

## Files

- `picks.py` — builds `picks_<bank>.json` (main/review/fallback/disagree10/
  locked/scanned groups) from N6 `*.h2h.jsonl` (read from the `wt-n6` worktree)
  + integrated-tip `integ_shard*.jsonl` + corpus manifest.
  `python tools/n7/picks.py backend`
- `e2e_n7.py` — real-HTTP flow per sha8 (analyze→confirm/override→process→poll→
  download→workbook checks) with per-stage timing + `--group` tags.
  Same interface as `tools/verify2/e2e2.py`.
- `validate_n7.py` — joins e2e records with shard records + audits; flags
  detected!=folder, served verdict!=shadow verdict, wb rows!=engine rows,
  formula errors, integrity fails, anchor misses.
- `diff_reg.py` — base-tip vs integrated-tip shard diff
  (status/fallback/layout/rows/verdict). `--base=<dir-or-glob> --integ=<dir-or-glob>`
- `confusion.py` — folder bank vs routed spec bank across all shard records;
  prints matrix + wrong accepts. `--max-per-folder=N` optional.
- `mutate.py` — tampers downloaded workbooks (one amount cell +1.00, one row
  deleted) and re-checks against the audit anchors to show the independent
  validator flags the mutation. `python tools/n7/mutate.py tools/n7/.local/dl sha8,... tools/n7/.local/audit_n7.jsonl`
- `perf.py` — p50/p95 analyze + process timings per bank; lists files >120s.
- `ui_n7.mjs` — Playwright UI pass (one flow per candidate, bank-panel counts
  vs API, review-only/UNSUPPORTED/coming-soon rows, mixed batch, 360/1280,
  console errors). Run from `wt-ui/frontend` (has node_modules).
- `claims_audit.md` — N5/N6 claims re-measured as TRUE/FALSE/UNSUPPORTED.
- `bank_status_proposed.patch` — proposed `bank_status.json` diff (not applied).
- `.local/` — picks, e2e/neg/ovc records, `dl/` workbooks + `dl/mut/` mutants,
  lane scripts + logs, regression shards (`integ_shard*.jsonl`), audit records.
  Gitignored.

## Flow notes

- `CONFIRM` on an unidentified document fails `BANK_REQUIRED`; the real user
  path for undetected files is `OVERRIDE` with the correct `bank_id`, which
  scopes v2 routing (`_v2_servable`). The `override_correct` group exercises it.
- `neg_override_out/_in` groups test wrong-bank override both directions
  between adjacent candidates; `crossfile` confirms a foreign candidate file
  as detected; `neg_nonenabled` runs a `union` (legacy-only) file;
  `neg_unknown` runs files the detector marks UNKNOWN.
- Downloaded workbooks keep only sha8 names; mutants live under `dl/mut/`.
