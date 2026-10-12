# Repository inventory — 2026-10-12

Scope: `X:\Airco Projects\Airco Insights fintech` (main checkout), sibling
directories under `X:\Airco Projects\`, and git worktrees. Sizes measured at
inventory time; `?` = untracked unless noted.

## Main checkout (on branch `devin/wave5` — not `main`)

| Entry | Tracked? | Size | Last mod | Purpose | Action |
|---|---|---|---|---|---|
| `auth/`, `backend/`, `database/`, `frontend/`, `infra/`, `scripts/`, `docs/` | tracked | normal | — | application code + docs | **keep** |
| `backend;C/`, `comparison;C/` | untracked | 0 MB | 2026-10-07 | empty dirs from bad `;C` shell pastes | **moved → archive** (2026-10-12) |
| `comparison/` | untracked (gitignored) | 932 MB | 2026-10-09 | run artifacts: wave/phase outputs, `hdfc_docker` (554 MB), `sbi_docker`, `c3`, `c3_head`, `*;C` junk | **moved → archive** `X:\Airco Projects\_archive\2026-10-12\comparison` (manifest there) |
| `Unified All Statements/` | untracked | 4,154 MB | 2026-10-07 | statement corpus (customer data) | **keep, read-only** — now gitignored |
| `samples/` | untracked (gitignored) | 42 MB | 2026-07-15 | local parser test PDFs | **keep** (tests reference it) |
| `.env`, `local.env` | untracked (gitignored) | small | — | local secrets | **keep, never commit** |
| `START.bat` | tracked | small | — | local launcher | keep |
| `docs/AGENT_STATE.md`, `docs/CLAUDE_PROJECT_CONTEXT.md`, `docs/SYSTEM_MAP.md`, `docs/MANUAL_TEST_CHECKLIST.md` | untracked in main checkout | small | — | live working docs (tracked on wave branches) | **keep** |
| `docs/slice1/out_*`, `docs/slice1/pristine/`, `docs/slice2/out_*` | untracked | MBs | 2026-10 | run outputs | **moved → archive** |
| `docs/slice2,3/DEVIN_PROMPT_*.md`, `FINAL_COMMIT_LISTS.md` | untracked | small | — | wave prompt files | **moved → archive** (choice: archived, not untracked-in-place) |
| `wt-*/` | untracked dirs | — | — | **git worktrees — see table below; do not move/delete** | keep |

## Git worktrees / branches

| Path | Branch | Head | Merged into `devin/final-rc`? | Prunable after Claude's merge? |
|---|---|---|---|---|
| main checkout | `devin/wave5` | e8ab437 | n/a (working checkout) | no — user's checkout |
| `..\wt-final` | `devin/final-rc` | (candidate) | IS the candidate | no — review candidate |
| `..\wt-base` | detached `880b5e2` | 880b5e2 | yes (ancestor) | yes (verification baseline, created by this wave) |
| `wt-w11` | `devin/wave11` | a4364cf | yes | yes (superseded by final-rc) |
| `wt-w11clean` | detached `bd4cf0c` | bd4cf0c | yes | yes |
| `wt-univ` | `devin/universal` | 2c23e7e | yes (merged at 75abd3a) | yes after merge + after u3b run harvested |
| `wt-audit` | detached `c022630` | c022630 | yes | yes |
| `wt-p8c` | detached `89c7b21` | 89c7b21 | yes (via integ history) | yes |
| `wt-p8b` | detached `971076f` | 971076f | yes | yes |
| `wt-pii` | `devin/pii-fixtures` | ef29716 | yes | yes |
| `wt-trackA` | `devin/wave6` | 971076f | yes | yes |
| `wt-trackB` | `devin/wave8` | a800f45 | yes | yes |
| `wt-wave10` | `devin/wave10` | 5a7d510 | yes | yes |
| `wt-wave9b` | `devin/wave9` | 1d519d8 | yes | yes |
| `wt-demo` | `demo/rc` | c022630 | yes | **no — running demo stack; never touch** |
| `/sessions/.../integ` | `integration/v2-waves` | 89c7b21 | ancestor | no — locked, Claude's merge target |

Branches never merged into final-rc: `devin/wave4` (superseded side
branch). Older `devin/wave1,2,3,5,6,8,9,10`, `feature/*`, `main`, `demo/rc`
are all ancestors.

## Sibling directories (other projects — out of scope, untouched)

`Airco Audioly`, `Airco Billsage`, `Airco Geetika`, `Airco Leadgen`,
`Airco Loan Toan`, `The-Airco-V2-main`, `X:\Airco Projects\Unified All
Statements` (junction → corpus, created for `regression_gate.py` path
resolution), `X:\Airco Projects\_archive\2026-10-12\` (this wave's archive).

## Stray-directory dispositions applied

- Moved to `_archive/2026-10-12/`: `comparison/` (incl. `hdfc_docker`,
  `sbi_docker`, `c3`, `c3_head`, `hdfc_docker;C`, `sbi_docker;C`), `backend;C`,
  `comparison;C`, `docs/slice1/out_*`, `docs/slice1/pristine`,
  `docs/slice2/out_*`, 7 untracked `DEVIN_PROMPT_*.md`/`FINAL_COMMIT_LISTS.md`.
- Proposed for delete (empty 0-byte dirs, user deletes): `backend;C`,
  `comparison;C`, `comparison/c3`, `comparison/*;C` — already moved; safe to
  drop from archive at user discretion.
- Gitignore added: `Unified All Statements/`, `wt-*/`, `*;C/`, `local.env`,
  `*.local.env` (`comparison/`, `samples/`, `.env*` were already ignored).

## Frozen doc-path references

`docs/archive/HANDOFF.md`, `docs/verification/FREEZE_PROPOSAL.md` and
`docs/verification/FINDINGS_RUN1.md` cite `docs/slice*/out_*` paths — those
outputs now live in the external archive; the docs are historical records and
were left frozen (paths annotated where a live doc moved in-repo).
