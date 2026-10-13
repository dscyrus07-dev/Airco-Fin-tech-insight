# UNBLOCK_PLAN — prompt 29 triage (22 SHADOW_ONLY + 2 REVIEW_ONLY + APGV)

Base: `integration/v2-waves @ 54f51ab` (contains `54f51ab`). Branch `devin/unblock-1`,
worktree `wt-ub`. Gates unchanged: det 100% on readable files, 0 cross-bank accepts,
≥90% hold-out yield (V|R with rows), ≥80% VERIFIED where printed balances exist,
clean spec-independent audit. Numbers below are post-onboarding/post-promote baselines
(per-bank `banks/*.md` notes + eval); fresh re-measure at tip running in parallel.

Out of scope: `au_sfb`, `bank_of_maharashtra` (candidates, under verify — untouched),
`apgb/cosmos/deutsche/fincare_sfb/fino_pb/tmb` (NOT_POSSIBLE), `bandhan/pnb/dcb`
(PARKED — Claude engine work; data prep only, §ENGINE_GAPS).

## Triage by cause

| bank | text files | failing gate(s) | cause | notes |
|---|---|---|---|---|
| ippb | 6 | yield (5R+1 no_layout), Vshare | A (+anchor reach) | 2nd fingerprint uncovered; REVIEW = self-derived chain |
| airtel_pb | 7 | yield 4/7, det | D | 3 unrouted are billing docs (non-statement, provable); 4 VERIFIED post-fix; thin corpus |
| uco | 11 | yield, Vshare | B/F residual | 8 routed post-fix incl. honest FAILED (space-glyph cells, multi-segment) |
| iob | 62 | REVIEW ceiling | E | no printed anchors by design — decide_serve honesty test (§3) |
| south_indian | 29 | REVIEW ceiling | E | same |
| apgv | 19 | — | wired | collision clean (APGB docs UNKNOWN/fallback, 0/393 cross detects); 13 x v2 REVIEW (no anchors), 2 honest fallbacks -> REVIEW_ONLY_SERVABLE |
| equitas_sfb | 38 | det 89.5%, yield 76% | A+B+C | 9 no_layout + 6 FAILED + 4 det_none |
| dbs | 131 | yield ~87% | F residual | 9 balance-less variant = engine gap; 6 multi-account FAILED honest; Vshare ~96% |
| central_bank | 49 | det 89.8%, yield 75.5% | A+B | 11 no_layout + 5 det_none + 9 FAILED |
| hsbc | 37 | yield 67.6% | A (+D scanned) | 10 no_layout + 2 NO_ROWS; 66/103 scanned excluded (unreadable) |
| ujjivan_sfb | 39 | det 76.9%, yield 74.4%, cross | A+C + 1 detector false-accept | 10 no_layout + det gaps + f3105a96 detector hit on Human-Verification file |
| indusind | 148 | yield 67.6%, det 93.2% | A | 48 no_layout — fingerprint to collapse |
| standard_chartered | 210 | yield 86.7%, det 91.9% | A+B+C | 22 foreign_bank + 24 FAILED + 6 no_layout + det gaps |
| yes | 106 | yield 77.4%, det 85.8%, Vshare | A+B+C | 11 no_layout + 29 FAILED + det gaps + 5 foreign |
| idbi | 109 | det 72.5%, yield 50.5% | A+C | 42 no_layout + 29 det_none + 11 bank_unconfirmed |
| federal | 308 | yield 63% (Vshare 74%), det 95.5% | A | 113 no_layout — large variant surface; csb "false accepts" are misfiled federal docs (correct routing) |
| kvb | 79 | det 5.1%, yield 5% | C massive | 71 bank_unconfirmed; VERIFIED never reconciles printed closing |
| csb | 16 | det 18.8%, ground truth | D | 8 markerless files unresolvable without OCR; federal accepts them because they ARE federal exports (mislabelled) or markerless — keep blocked |
| dhanlaxmi | 15 | yield ≤47% | F | fp-A needs balance-as-continuation-line (engine gap); fp-C variant addable but ceiling too low |

## Order (smallest gap first; A/B/C before E before F)

1. `ippb` — 1 missing variant + anchor check
2. `airtel_pb` — confirm billing-doc exclusions; gates on 4 valid files
3. `uco` — verify post-fix state; honest FAILEDs documented
4. `equitas_sfb` — 9 no_layout fingerprints + FAILED diagnosis + 4 det_none
5. `dbs` — confirm remaining gap is purely engine-gap files
6. `central_bank` — 11 no_layout + detector gaps
7. `hsbc` — 10 no_layout on 37 valid text files
8. `ujjivan_sfb` — 10 no_layout + detector strengthening + kill f3105a96 false-accept
9. `indusind` — 48 no_layout, collapse by fingerprint
10. `standard_chartered` — 22 foreign_bank + FAILED triage
11. `yes` — FAILED wave + no_layout + detector
12. `idbi` — detector + 42 no_layout
13. `federal` — 113 no_layout (likely multiple shapes; time-box)
14. `kvb` — detector rebuild (bank_unconfirmed 71)
15. `csb` — corpus problem; document precisely, likely stays blocked
16. `dhanlaxmi` — fp-C variant only if cheap; park remainder as engine gap
17. `iob` + `south_indian` — REVIEW_ONLY servability test
18. `apgv` — APGB/APGV collision check → wire or keep blocked
19. ENGINE_GAPS.md + synth generators for bandhan/pnb/dcb

Regression gate after every 3 bank commits and at end: engine suite + API suite +
≥600-file corpus compare (15 existing banks + au_sfb + bank_of_maharashtra),
`54f51ab` vs current, zero differences.
