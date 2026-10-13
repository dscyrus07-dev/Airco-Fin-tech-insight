# Overnight all-banks onboarding — report

Branch `devin/onboard-all` (worktree `wt-ob`) on base `integration/v2-waves` @ `8b57e0d`.
Scope: every in-scope bank folder except the 13 supported banks + citibank + city_union.
30 banks processed. One commit per bank. Nothing pushed. Corpus untouched; no statement
content, paths, or PII anywhere in committed artifacts (sha8 + counts only).

## Status counts

| status | n | banks |
|---|---|---|
| READY_TO_SERVE | 0 | — |
| SHADOW_ONLY | 22 | standard_chartered dbs ujjivan_sfb au_sfb dcb federal indusind idbi yes pnb kvb central_bank equitas_sfb bank_of_maharashtra bandhan hsbc apgv csb uco airtel_pb ippb dhanlaxmi |
| REVIEW_ONLY | 2 | iob south_indian |
| PARKED | 0 | — |
| NOT_POSSIBLE | 6 | apgb cosmos deutsche fincare_sfb fino_pb tmb |

No bank reached READY_TO_SERVE — every bank missed at least one gate (detection <100%,
VERIFIED share <80% of anchored files, or REVIEW-ceiling layouts with no usable anchors).
Proposed `SERVE_BANKS`: **unchanged** (see below).

## Per-bank table

Files = total PDFs; txt/scn/lck = text-readable/scanned/locked; det% = correctly detected
share of text files (pre-onboarding); v2 V/R/F = VERIFIED/REVIEW/FAILED under shadow;
audit = independent check of VERIFIED sample; fa = cross-bank false accepts.

| bank | txt/scn/lck | det% | v2 V/R/F | audit | fa | status | commit |
|---|---|---|---|---|---|---|---|
| standard_chartered | 210/1/34 | 91.9 | 158/0/24 | 30/30 clean* | 0 | SHADOW_ONLY | 3236b09 |
| dbs | 131/4/2 | 99.2 | 0/112/6 | n/a (no VERIFIED) | 0 | SHADOW_ONLY | 24411d3 |
| ujjivan_sfb | 39/0/0 | 76.9 | 0/24/5 | n/a | 0 | SHADOW_ONLY | 0bfbc9a |
| au_sfb | 18/0/0 | 94.4 | 15/0/0 | 15/15 clean | 0 | SHADOW_ONLY | 36d410e |
| dcb | 15/1/0 | 100 | 7/0/8 | 7/7 clean | 0 | SHADOW_ONLY | 498c245 |
| federal | 308/1/51 | 95.5 | 144/37/13 | 15/15 clean* | 0† | SHADOW_ONLY | 86d2bd0 |
| indusind | 148/3/3 | 93.2 | 95/3/2 | 20/20 clean* | 0 | SHADOW_ONLY | a81b03b |
| idbi | 109/6/4 | 72.5 | 15/31/9 | 15/15 clean* | 0 | SHADOW_ONLY | 4588f56 |
| yes | 106/9/22 | 85.8 | 16/37/29 | 16/16 clean | 0 | SHADOW_ONLY | 3813032 |
| pnb | 88/1/20 | 98.9 | 0/57/0 | n/a | 0 | SHADOW_ONLY | 6618147 |
| kvb | 79/7/3 | 5.1 | 3/0/1 | n/a | 0 | SHADOW_ONLY | 1066d54 |
| iob | 62/3/6 | 100 | 0/55/3 | n/a | 0 | REVIEW_ONLY | 92bbb8f |
| central_bank | 49/2/5 | 89.8 | 0/28/9 | n/a | 0 | SHADOW_ONLY | 71046c5 |
| equitas_sfb | 38/1/3 | 89.5 | 0/23/6 | n/a | 0 | SHADOW_ONLY | 5b21e0b |
| bank_of_maharashtra | 33/0/3 | 100 | 9/11/0 | 9/9 clean* | 0 | SHADOW_ONLY | 1dae342 |
| bandhan | 18/0/1 | 94.4 | 5/5/0 | 5/5 clean | 0 | SHADOW_ONLY | 20a04c1 |
| hsbc | 37/66/0 | 97.3 | 0/25/0 | n/a | 0 | SHADOW_ONLY | 8b34812 |
| south_indian | 29/1/3 | 100 | 0/28/0 | n/a | 0 | REVIEW_ONLY | 82658af |
| apgv | 19/0/0 | 84.2 | 0/16/0 | n/a | 0 | SHADOW_ONLY | 2411712 |
| csb | 16/0/1 | 18.8‡ | post-spec: 2 REVIEW, ~6 are mislabeled Federal docs | n/a | 0 | SHADOW_ONLY | 933f0be |
| uco | 11/0/0 | 100‡ | post-spec: 8 v2 (4R/4F real chain mismatches), 2 no_layout | n/a | 0 | SHADOW_ONLY | 430506e |
| airtel_pb | 7/0/0 | 57.1‡ | post-spec: 4/7 v2, real schema errs on edge rows | n/a | 0 | SHADOW_ONLY | 8f2e55c |
| ippb | 6/0/0 | 100‡ | post-spec: routed v2, REVIEW (self-derived chain) | n/a | 0 | SHADOW_ONLY | b634a7d |
| dhanlaxmi | 15/0/0 | 0‡ | post-spec: 5/15 v2 REVIEW (fp-B); fp-A unsupported | n/a | 0 | SHADOW_ONLY | 89274a7 |
| apgb | 2/0/0 | — | — | — | — | NOT_POSSIBLE | 312dd1d |
| cosmos | 2/0/0 | — | — | — | — | NOT_POSSIBLE | db6fa88 |
| deutsche | 2/0/0 | — | — | — | — | NOT_POSSIBLE | efbdce4 |
| fincare_sfb | 3/0/0 | — | — | — | — | NOT_POSSIBLE | e5c72bb |
| fino_pb | 1/0/0 | — | — | — | — | NOT_POSSIBLE | 8d5d3e6 |
| tmb | 2/0/0 | — | — | — | — | NOT_POSSIBLE | 3065b2c |

\* audit flagged files only by the dated-amount-line heuristic (`row_gap=1`): the flagged
line is the closing-balance/header anchor itself — chain unbroken and printed anchors
matched in every flagged file. One BoM file shows `row_gap=4`, all four lines are dated
amount-bearing header furniture ("total balance", statement dates), not transactions.
Zero real disagreements.

† federal shows 5 "cross-bank accepts" from the CSB folder — all five were verified to
be genuine Federal Bank statements mislabeled into the CSB folder (documents print
"Federal"); routing them to the federal spec is correct behavior, not a false accept.
One canara-detector hit inside the APGV folder is likewise a mislabeled Canara document
(prints "canara"). One ujjivan hit sits in the non-bank "Human Verification" folder.

‡ pre-spec or detector-only numbers; see per-bank doc for post-spec measure.

## New work

- **5 new extractor packages** (spec + registry + detector map entry + banks JSON +
  synthetic tests + doc): `csb`, `uco`, `airtel_pb`, `ippb`, `dhanlaxmi`.
- **19 pre-existing spec'd banks** measured, tested (synthetic), audited, documented.
- **6 banks** documented NOT_POSSIBLE (<5 usable text files each; see per-bank reasons).
- ~120 new synthetic onboarding tests committed under
  `backend/tests/statement_engine/extraction/test_onboard_*.py` — coordinate-based,
  no PDFs, no PII.
- Tooling under `tools/onboarding/` (README included); `.local/` gitignored.

## Regression gate — PASS

- Full backend suite: **639 passed, 18 skipped, 8 failed**. Base tree: **519 passed,
  18 skipped, 8 failed** — the same 8 failures, all pre-existing fixture/environment
  issues (missing corpus PDFs on axis/canara/icici/hdfc tests, finbit analytics,
  api-key rate-limit). Branch adds ~120 green tests.
- Corpus compare: seeded **400-file** sample from the 15 protected banks, base tree vs
  branch, identical config — **0 diffs** across status/bank/layout/fallback/rows/verdict.
- Product-code diff vs base: empty above onboarding additions; no existing LayoutSpec,
  detector entry, engine file, flag, or allowlist touched.
- Cross-bank pool check: **415 probes**, zero genuine false accepts (see †).
- Wrong-bank probes: synthetic tests cover foreign-marker rejection for every new spec.

## Proposed SERVE_BANKS

No bank met READY_TO_SERVE. Proposed `STATEMENT_ENGINE_V2_SERVE_BANKS` = **unchanged**
(keep current allowlist). Closest candidates for a later wave, if the user wants to
re-gate with updated specs/evidence: `au_sfb` (det 94.4, 15/15 VERIFIED+audit clean —
det below 100%), `bank_of_maharashtra` (det 100, VERIFIED share below bar).

To enable a bank later: set `STATEMENT_ENGINE_V2_SERVE_BANKS` in the stack env to the
allowlist including the bank id, restart backend, re-run its folder probe to confirm
serve-tier output, keep detector tests green. Decision left to the user.

## Collision matrix (tested)

- Union vs City Union: no cross accepts.
- Bank of India vs Baroda vs Maharashtra vs Central vs Indian vs IOB: no cross accepts
  (note: several *detector* misdetections exist on base config — see triage report —
  unchanged by this branch).
- Karnataka vs KVB vs APGV: kvb det-ok only 5.1% (detector weakness, pre-existing).
- Kotak vs Kotak Mahindra folders: merged under `kotak`, routes correctly.
- AU/Equitas/Ujjivan/Fincare/Fino/Airtel/IPPB: new detector entries do not collide;
  pooled xcheck clean.

## Surprises / defects found

- **CSB folder contains ~6 mislabeled Federal Bank statements** (documents print
  Federal; correctly routed to federal). Real CSB fingerprints differ — new csb spec
  covers the dominant genuine one.
- **APGV folder contains ≥1 mislabeled Canara statement**; **Human Verification** holds
  real bank statements. Corpus labeling, not engine.
- **kvb detector det-ok 5.1%** — registry/spec exist but detection almost never fires;
  recorded, not silently fixed.
- **dhanlaxmi fp-A unsupported**: balance values printed on continuation lines — needs
  an engine capability for balance-on-continuation; spec deliberately not broadened.
- **dcb**: 8/15 FAILED on multi-account fingerprint — real reference-check failures on a
  second account's summary block, not spec crashes.
- **uco**: 4/8 v2-routed files FAILED with genuine chain/amount mismatches.
- **hsbc**: 66/103 files scanned/image-only — only 37 text-usable.

## NOT RUN

- Legacy-tier verdicts for fallback files (shadow probe yields no v2 verdict by design).
- Multi-account detection (scan heuristic unreliable — needs account hashing).
- 16 pooled xcheck records of 431 did not complete before cutoff (files at tail; all
  completed records show zero genuine false accepts).

## Time

~10h total. Triage data reused from `devin/onboarding-triage` (identical engine).
Per-bank box respected; NOT_POSSIBLE banks documented in minutes, new-spec builds took
the largest share (csb re-targeting after discovering mislabeled federal files, ippb
merged-token header, dhanlaxmi zero-cell handling).
