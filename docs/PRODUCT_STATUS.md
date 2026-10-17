# Product status â€” per bank (`devin/final-rc`, measured 2026-10-12)

> **Serve state updated for the 14-bank rollout (`devin/rollout-1`, base
> `411f6ca`).** The `onb` default served list is now
> `hdfc,sbi,axis,idfc,paytm,citibank,city_union,au_sfb,bank_of_maharashtra,
> airtel_pb,iob,apgv,south_indian,pnb`: 10 VERIFIED-capable + 4 review-only
> (`review_required` in the API, always flagged needs-review). The table below
> still reflects the final-rc measurement wave; banks whose state changed are
> re-stated in the next section.

> **N9 update (`devin/n9-final`, measured on the `rc` release-candidate stack):**
> the N5–N7 night wave verified six more banks end to end (`docs/onboarding/
> N7_REPORT.md`): `bob` (Bank of Baroda), `canara`, `icici`, `indian_bank`,
> `karnataka`, `kotak` — each `SERVE_V2_WITH_LEGACY_FALLBACK`, each GO after
> independent e2e verification (36 jobs, 0 flags). Proposed served list =
> the 14-bank default **plus those six** (20 banks). The proposal is not yet
> shipped — the `rc` stack carries it via env var; the shipped default is
> unchanged. Everything below the N9 banner reflects pre-wave measurements;
> rows marked superseded have newer truth in `N7_REPORT.md` /
> `N6_LEGACY_VS_V2.md`.

> **V4/R3 update (`devin/verify-4` + `devin/rollout-3`, measured 2026-10-17):**
> `federal` is GO as `verified` (94.9% readable detection, 85.6% VERIFIED share,
> 0 cross-bank accepts, 40-file independent audit clean) and `dhanlaxmi` is GO
> as `review_required` (11/11 REVIEW, totals reconcile — REVIEW-only ceiling).
> `dbs` is **NO-GO**: its no-balance-column layouts render a literal `0`
> Balance column and all-zero balance metrics in the workbook
> (`lite_metrics._to_float` coerces null→0.0; see `docs/onboarding/
> ENGINE_GAPS.md` §6) — REVIEW-gated but misleading; hold until blank-write
> lands. `indusind` stays `coming_soon` (VERIFIED share 76.7% < 80 gate).
> Served list on `rc` = the 20-bank list **+ federal + dhanlaxmi** (22 banks).

## Rolled-out serve list (`411f6ca`)

| Bank | State | Caveats |
|---|---|---|
| hdfc, sbi, idfc, paytm, citibank, city_union | `verified` (VERIFIED-capable) | unchanged from wave-11 |
| axis | `verified` (VERIFIED-capable) | **truncated-statement caveat**: spec could silently drop rows above period-marker footers (`000df35f`, 1,141/1,147 rows). As of the current tip the completeness guard catches it — REVIEW with `unread_transaction_lines:6` instead of VERIFIED. Still demo-flagged. |
| au_sfb | `verified` | promoted after `restore_statement_order` dup-key fix (V3 GO) |
| bank_of_maharashtra | `verified` | promoted (V3 GO) |
| airtel_pb | `verified` | promoted (V3 GO) — **thin corpus** (3 usable files; 3 more are unidentifiable billing docs that honestly refuse) |
| iob | `review_required` | no printed balance anchors — VERIFIED impossible; always needs review |
| apgv | `review_required` | same |
| south_indian | `review_required` | same; `SOUTHINDIANBANK` marker protects against the INDIANBANK substring collision |
| pnb | `review_required` | same; `Amount(INR)` title variant accepted (`6705992`) |

8 legacy-only banks remain on the legacy parser: icici, kotak, canara,
karnataka, union, bank_of_baroda, bank_of_india, indian_bank.
**[N9: superseded — six of these are now v2-verified; only `union` and
`bank_of_india` remain legacy-only.]**

Numbers come from the final-wave runs only:
`comparison/final/after_*.jsonl` (14,445-file router probe at this branch),
`comparison/final/mx_*.jsonl` (30-file flag matrix through the orchestrator),
`comparison/final/e2e/` (live finrc stack API+UI legs).

Recommendations: **serve** = evidence-gated v2 allowlist Â· **shadow** = run,
don't serve Â· **legacy-only** = legacy parser path, no v2 claims Â·
**general reader** = T3 `REVIEW` only Â· **not supported** = honest failure.

| Bank | Tier that serves it | Verdicts it can show | Evidence | Known limitations | Recommendation |
|---|---|---|---|---|---|
| HDFC | T2 (spec `hdfc_*`) | VERIFIED, REVIEW | probe VERIFIED count below; e2e completed VERIFIED + Statement Check; mutation caught | none known | **serve** |
| SBI | T2 (`sbi_*`) | VERIFIED, REVIEW | e2e completed VERIFIED | none known | **serve** |
| Axis | T2 (`axis_*`) | VERIFIED, REVIEW | e2e completed VERIFIED | **spec truncates rows above period-marker footers â€” audit-WRONG `000df35f` reproduced 1,141 of 1,147 rows as VERIFIED. Current tip: completeness guard now lands that file REVIEW (`unread_transaction_lines:6`)** | **serve** (rolled out on `onb`; caveat stands â€” keep demo-flagged) |
| ICICI **[N9: v2-verified, superseded]** | ~~T1 legacy~~ v2 (+T3 REVIEW when legacy fails) | no VERIFIED claim | e2e UNKNOWNâ†’overrideâ†’legacy completed | **audit-WRONG**: legacy fabricates amounts on 2/3 audited files; detector often UNKNOWN â†’ manual pick | **legacy-only** â€” do not demo as verified |
| IDFC First | T2 (`idfc_*`) | VERIFIED, REVIEW | e2e completed VERIFIED | duplicate printed rows can break the chain check (audit TRUE-WITH-GAPS) | **serve** |
| Paytm Payments | T2 (`paytm_*`) | VERIFIED, REVIEW | e2e completed VERIFIED | ~30% of rows print no balance â†’ unverifiable (audit TRUE-WITH-GAPS) | **serve** |
| Citibank | T2 (`citi*`) | VERIFIED | e2e file honest-failed (layout family unmatched); matrix citi file VERIFIED | coverage gap: some citi layouts don't match spec â†’ honest fail | **serve** (partial coverage) |
| City Union | T2 (`city_union_*`) | VERIFIED, REVIEW | e2e REVIEW completed; matrix VERIFIED + REVIEW | most files land REVIEW (honest) | **serve** |
| Kotak Mahindra **[N9: v2-verified, superseded]** | v2+legacy fallback | REVIEW only if T3 | matrix: legacy failed; T3 shadow tier; audit-WRONG legacy merging | **audit-WRONG** legacy; spec shares axis-class truncation | **not supported** (honest fail today) |
| IndusInd | none (spec exists, NOT allowlisted) | REVIEW only if T3 | matrix: honest fail | first-row amount mutation stays VERIFIED â†’ excluded from allowlist by wave11 | **not supported** |
| Union Bank | T1 legacy | no VERIFIED claim | matrix: 1 legacy success, 1 T3 REVIEW under u-serve | â€” | **legacy-only** |
| Bank of India | T1 legacy (added post-880b5e2) | no VERIFIED claim | matrix: legacy success | â€” | **legacy-only** |
| Canara **[N9: v2-verified, superseded]** | v2+legacy fallback | REVIEW only if T3 | matrix: legacy failed; T3 honest fail | â€” | **not supported** |
| Bandhan | none | REVIEW only if T3 | matrix: honest fail | â€” | **not supported** |
| Punjab National | T2 (`pnb_*`, review-only) | REVIEW only | V3: 3 real files REVIEW + `NO_INDEPENDENT_ANCHOR`; 1,171-row file extracts | VERIFIED impossible (no printed anchors) | **serve review-only** (rolled out) |
| Bank of Maharashtra | T2 (`bom*` / `bank_of_maharashtra_*`) | VERIFIED, REVIEW | V3: 7 e2e files, 4 VERIFIED + 3 REVIEW | â€” | **serve** (rolled out, VERIFIED-capable) |
| Tamilnad Mercantile | none | T3 REVIEW | matrix u-serve: REVIEW (465-row class OK in univ wave) | â€” | **general reader** |
| Dhanlaxmi | none | T3 REVIEW | matrix u-serve: REVIEW | â€” | **general reader** |
| South Indian | T2 (`sib_*`/`south_indian_*`, review-only) | REVIEW only | V3: 3 real files REVIEW; full-brand synth detects `south_indian` not `indian_bank` | marker-less layouts + no printed anchors | **serve review-only** (rolled out) |
| AU Small Finance | T2 (`au_sfb_*`) | VERIFIED, REVIEW | V3: 5 e2e VERIFIED incl. dup-key defect file (140 rows exact) | â€” | **serve** (rolled out) |
| Airtel Payments | T2 (`airtel_*`) | VERIFIED, REVIEW | V3: 3/6 files VERIFIED | thin corpus â€” 3 files unidentifiable (honest refusal) | **serve** (rolled out; thin-corpus caveat) |
| Indian Overseas | T2 (`iob_*`, review-only) | REVIEW only | V3: 3 real files REVIEW + `NO_INDEPENDENT_ANCHOR` | VERIFIED impossible | **serve review-only** (rolled out) |
| AP Grameena Vikas | T2 (`apgv_*`, review-only) | REVIEW only | V3: 3 real files REVIEW | VERIFIED impossible | **serve review-only** (rolled out) |
| Other registered specs (~30 more in `extractors/`) | T2 shadow-capable | VERIFIED only if allowlisted | not re-measured individually | evidence gate not passed | **shadow** |
| Anything else / non-statement | â€” | â€” | e2e: non-statement â†’ "could not identify"; locked â†’ password prompt; negatives never VERIFIED | â€” | **not supported** |

## Counts at this branch (router probe, all readable corpus)

Filled from `comparison/final/REPORT.md` Â§2.2 â€” see the per-folder table there
(VERIFIED / REVIEW / fallback / unsupported per folder at final-rc).

## Policy notes

- Axis + ICICI + Kotak were graded **WRONG** by the independent audit
  (`wt-audit/comparison/audit/REPORT.md`). Axis is nonetheless on the wave-11
  recommended allowlist â€” flagged as a BLOCKER in the final report.
- IndusInd is correctly excluded (mutation gate).
- T3/general reader never emits VERIFIED by construction.


## UI bank states (devin/ui-banks)

`GET /api/statements/banks` returns an additive `all_banks` list: every known
bank id with `support_state` — `verified` (v2-served, VERIFIED-capable),
`review_required` (servable but VERIFIED-impossible; persistent needs-review
notice), `legacy` (legacy parser only), `coming_soon` (detected + measured,
not enabled), `unsupported` (scanned/too few samples). Derivation: serve
config + `statement_engine/bank_status.json` (see its README).
`banks[]` is unchanged — still only servable banks.
Surfaces: grouped bank pickers, supported-banks panel, "<Bank> is not enabled
yet" rows, persistent review-required notice. See `docs/operations/UI_BANK_STATES.md`.

## UI entry (devin/unified-entry)

One entry point behind `NEXT_PUBLIC_UNIFIED_ENTRY` (default off): `/dashboard`
runs Upload â†’ Review â†’ Processing â†’ Report with per-file bank override,
statement type, inline unlock, parallel processing and the existing report
view. `/analyze` redirects when the flag is on. Flag off = both legacy pages
unchanged. See `docs/UNIFIED_ENTRY_PLAN.md` + `docs/engine/V2_UI_NOTES.md`.

## Onboarded banks (devin/onboard-all, shadow wave)

Measured on `devin/onboard-all` (base `8b57e0d`), 30 previously unsupported bank
folders. All shadow or review-ceiling â€” **none enabled for serving**; the
`SERVE_BANKS` allowlist is unchanged. Per-bank detail:
`docs/onboarding/OVERNIGHT_REPORT.md` + `docs/onboarding/banks/<id>.md`.

| Bank | Status | Note |
|---|---|---|
| standard_chartered | shadow_only | det 91.9%, audit clean; FAILEDs are real chain/reference issues |
| dbs | shadow_only | 110V+4R+6F; yield 87.0% < 90% (balance-less variants = engine gap); audit clean — promote-1 |
| ujjivan_sfb | shadow_only | det 76.9% |
| au_sfb | ready_to_serve_candidate | 16/17 v2 VERIFIED (1 evidence-less file unroutable); yield 94.1%; audit clean — promote-1 |
| dcb | shadow_only | det 100%; 8/15 real multi-account FAILED |
| federal | shadow_only | det 95.5%, 144 VERIFIED; audit heuristic flags = anchor lines |
| indusind | shadow_only | det 93.2% |
| idbi | shadow_only | det 72.5% |
| yes | shadow_only | det 85.8%; marker-less (detector/bank_key evidence only) |
| pnb | shadow_only | det 98.9%; all REVIEW |
| kvb | shadow_only | det 5.1% â€” pre-existing detector weakness |
| iob | review_only | det 100%; no printed balance anchors â†’ VERIFIED impossible |
| central_bank | shadow_only | det 89.8% |
| equitas_sfb | shadow_only | det 89.5% |
| bank_of_maharashtra | ready_to_serve_candidate | 26/27 routed: 21V+5R; yield 96.3%, Vshare 80.8%; audit clean — promote-1 |
| bandhan | shadow_only | det 94.4% |
| hsbc | shadow_only | 66/103 files image-only; det 97.3% on text files |
| south_indian | review_only | det 100%; marker-less + no printed anchors |
| apgv | shadow_only | det 84.2%; detector entry intentionally absent |
| csb | shadow_only | NEW spec; ~6 folder files are mislabeled Federal docs |
| uco | shadow_only | 5R+4F after newest-first/anchor fixes; remaining FAILEDs are real doc defects — promote-1 |
| airtel_pb | shadow_only | 4/4 VERIFIED after furniture fixes; 3 files are billing docs; thin corpus — promote-1 |
| ippb | shadow_only | NEW spec; REVIEW-ceiling (self-derived chain) |
| dhanlaxmi | shadow_only | NEW spec; fp with balance-on-continuation unsupported |
| iobâ†’(see above) | | |
| apgb | not_possible | 2 text files |
| cosmos | not_possible | 2 text files |
| deutsche | not_possible | 2 text files |
| fincare_sfb | not_possible | 3 text files |
| fino_pb | not_possible | 1 text file |
| tmb | not_possible | 2 text files |

Cross-bank pooled check: 415 probes, zero genuine false accepts. 400-file
regression compare vs base: 0 diffs. Full suite: 639 passed vs 519 on base,
same 8 pre-existing failures.

## N5 wave refresh (devin/n5-bank-wave, base f81095e)

Shadow re-measure of the onboarded set on the N1–N3 engine. Shipped states
unchanged; refreshed numbers in `docs/onboarding/N5_RESULTS.md`.

- Improved: federal 228→232V (FAILED 13→6), scb 168→171V, indusind fallback
  26→3 (+22 REVIEW-with-rows via L4 + INDB own-IFSC), bandhan 5→8V (fallback
  7→0), dhanlaxmi +2 REVIEW via L3, dbs +2 REVIEW (yearless variant),
  bom 24→25V (`dates_monotonic_expected=False` on L3; zero-diff proof +
  audited change).
- Unchanged with classified residuals: idbi, yes, central_bank, equitas_sfb,
  ujjivan_sfb, hsbc, kvb, dcb, uco, csb, ippb, pnb.
- Candidates (proposed, not shipped): none new — all remain shadow_only /
  review_only / legacy per existing table; bom stays `verified` (served).
