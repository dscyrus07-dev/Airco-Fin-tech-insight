# Product status — per bank (`devin/final-rc`, measured 2026-10-12)

Numbers come from the final-wave runs only:
`comparison/final/after_*.jsonl` (14,445-file router probe at this branch),
`comparison/final/mx_*.jsonl` (30-file flag matrix through the orchestrator),
`comparison/final/e2e/` (live finrc stack API+UI legs).

Recommendations: **serve** = evidence-gated v2 allowlist · **shadow** = run,
don't serve · **legacy-only** = legacy parser path, no v2 claims ·
**general reader** = T3 `REVIEW` only · **not supported** = honest failure.

| Bank | Tier that serves it | Verdicts it can show | Evidence | Known limitations | Recommendation |
|---|---|---|---|---|---|
| HDFC | T2 (spec `hdfc_*`) | VERIFIED, REVIEW | probe VERIFIED count below; e2e completed VERIFIED + Statement Check; mutation caught | none known | **serve** |
| SBI | T2 (`sbi_*`) | VERIFIED, REVIEW | e2e completed VERIFIED | none known | **serve** |
| Axis | T2 (`axis_*`) | VERIFIED, REVIEW | e2e completed VERIFIED | **spec truncates rows above period-marker footers — audit-WRONG `000df35f` reproduced 1,141 of 1,147 rows as VERIFIED** | **serve-with-blocker** (see REPORT; audit grade WRONG — recommend remove from allowlist until spec fix) |
| ICICI | T1 legacy (+T3 REVIEW when legacy fails) | no VERIFIED claim | e2e UNKNOWN→override→legacy completed | **audit-WRONG**: legacy fabricates amounts on 2/3 audited files; detector often UNKNOWN → manual pick | **legacy-only** — do not demo as verified |
| IDFC First | T2 (`idfc_*`) | VERIFIED, REVIEW | e2e completed VERIFIED | duplicate printed rows can break the chain check (audit TRUE-WITH-GAPS) | **serve** |
| Paytm Payments | T2 (`paytm_*`) | VERIFIED, REVIEW | e2e completed VERIFIED | ~30% of rows print no balance → unverifiable (audit TRUE-WITH-GAPS) | **serve** |
| Citibank | T2 (`citi*`) | VERIFIED | e2e file honest-failed (layout family unmatched); matrix citi file VERIFIED | coverage gap: some citi layouts don't match spec → honest fail | **serve** (partial coverage) |
| City Union | T2 (`city_union_*`) | VERIFIED, REVIEW | e2e REVIEW completed; matrix VERIFIED + REVIEW | most files land REVIEW (honest) | **serve** |
| Kotak Mahindra | none (spec exists, not allowlisted) | REVIEW only if T3 | matrix: legacy failed; T3 shadow tier; audit-WRONG legacy merging | **audit-WRONG** legacy; spec shares axis-class truncation | **not supported** (honest fail today) |
| IndusInd | none (spec exists, NOT allowlisted) | REVIEW only if T3 | matrix: honest fail | first-row amount mutation stays VERIFIED → excluded from allowlist by wave11 | **not supported** |
| Union Bank | T1 legacy | no VERIFIED claim | matrix: 1 legacy success, 1 T3 REVIEW under u-serve | — | **legacy-only** |
| Bank of India | T1 legacy (added post-880b5e2) | no VERIFIED claim | matrix: legacy success | — | **legacy-only** |
| Canara | none usable (legacy fails; spec not allowlisted) | REVIEW only if T3 | matrix: legacy failed; T3 honest fail | — | **not supported** |
| Bandhan | none | REVIEW only if T3 | matrix: honest fail | — | **not supported** |
| Punjab National | none (no spec, no legacy) | T3 REVIEW | e2e: honest `LOW_CONFIDENCE_COLUMNS` fail | T3 can't express mPassbook layout | **general reader** (when it matches, REVIEW only) |
| Bank of Maharashtra | none | T3 REVIEW | e2e + UI: T3 completed REVIEW, general-reader badge | REVIEW ceiling | **general reader** |
| Tamilnad Mercantile | none | T3 REVIEW | matrix u-serve: REVIEW (465-row class OK in univ wave) | — | **general reader** |
| Dhanlaxmi | none | T3 REVIEW | matrix u-serve: REVIEW | — | **general reader** |
| South Indian | none | T3 REVIEW | e2e: honest fail | this file's layout unreadable | **general reader** |
| Other registered specs (~30 more in `extractors/`) | T2 shadow-capable | VERIFIED only if allowlisted | not re-measured individually | evidence gate not passed | **shadow** |
| Anything else / non-statement | — | — | e2e: non-statement → "could not identify"; locked → password prompt; negatives never VERIFIED | — | **not supported** |

## Counts at this branch (router probe, all readable corpus)

Filled from `comparison/final/REPORT.md` §2.2 — see the per-folder table there
(VERIFIED / REVIEW / fallback / unsupported per folder at final-rc).

## Policy notes

- Axis + ICICI + Kotak were graded **WRONG** by the independent audit
  (`wt-audit/comparison/audit/REPORT.md`). Axis is nonetheless on the wave-11
  recommended allowlist — flagged as a BLOCKER in the final report.
- IndusInd is correctly excluded (mutation gate).
- T3/general reader never emits VERIFIED by construction.

## UI entry (devin/unified-entry)

One entry point behind `NEXT_PUBLIC_UNIFIED_ENTRY` (default off): `/dashboard`
runs Upload → Review → Processing → Report with per-file bank override,
statement type, inline unlock, parallel processing and the existing report
view. `/analyze` redirects when the flag is on. Flag off = both legacy pages
unchanged. See `docs/UNIFIED_ENTRY_PLAN.md` + `docs/engine/V2_UI_NOTES.md`.
