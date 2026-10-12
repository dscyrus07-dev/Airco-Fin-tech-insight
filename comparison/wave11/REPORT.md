# Wave 11B Report — v2 enablement, per-bank acceptance, demo refresh

Branch `devin/wave11`, head `bd4cf0c`. Base `demo/rc` `c022630`.
Stack under test: separate `w11` compose project (backend `:8005`,
frontend `:3001`) — demo stack untouched until the E5 gates all passed.

## BLOCKERS

1. **IndusInd first-row amount mutation stays VERIFIED** — E3 mutation probe:
   mutating txn row 0's amount +1 through the v2 checks keeps verdict VERIFIED
   (`sha 00d70d3a`). Rows 1 and 5 mutations correctly FAILED. Root cause is in
   the checks layer: the running-balance chain is pairwise (row 0 has no
   predecessor), the reference check derives from balances only, and this
   layout prints no totals to cross-check. **Owner: Claude** (checks/policy
   layer is a NOT-ALLOWED area this wave). **Action taken: indusind removed
   from the eligible allowlist** — recommended set is 7 banks. Do not re-add
   until the fix lands and this probe is re-run.
2. No other blockers. Flag-off byte-identity vs `880b5e2` holds (3-file check).

## Eligible set (E1 recompute → E3 probes)

`STATEMENT_ENGINE_V2_SERVE_BANKS=hdfc,sbi,axis,idfc,paytm,citibank,city_union`

## Per-bank acceptance (API, `e3_results.jsonl`; 5 picks each, sha-deterministic)

| spec | picks | completed | v2 VERIFIED | v2 REVIEW | legacy* | mutation | wrong-bank |
|---|---|---|---|---|---|---|---|
| hdfc | 5 | 5 | 3 | — | 2 | FAILS (safe) | FAILED (safe) |
| sbi | 5 | 5 | 3 | — | 2 | FAILS (safe) | FAILED (safe) |
| axis | 5 | 5 | 3 | — | 2 | FAILS (safe) | FAILED (safe) |
| idfc | 5 | 5 | 3 | — | 2 | FAILS (safe) | FAILED (safe) |
| paytm | 5 | 5 | 5 | — | 0 | FAILS (safe) | FAILED (safe) |
| citibank | 5 | 5 | 5 | — | 0 (v2-only) | FAILS (safe) | FAILED (safe) |
| city_union | 5 | 5 | 3 | 2 (`NO_INDEPENDENT_ANCHOR`) | 0 (v2-only) | FAILS (safe) | FAILED (safe) |
| ~~indusind~~ | 5 | 5 | 3 | 2 | 0 | **VERIFIED — BLOCKER** | FAILED (safe) |

\* corpus REVIEW picks for banks with a working legacy parser defer to legacy
by product contract; legacy counts differ from v2 (different parser) — expected.
Wrong-bank = file of bank X submitted as bank Y via explicit OVERRIDE.

## Verification performed

- **V2-only banks end to end** (citibank, city_union, indusind): analyze →
  confirm → process → Excel through the generic downstream processor. Found
  and fixed a real crash: `Decimal += float` in
  `banks/_shared/generic_bank.py` reconciliation (`bd4cf0c`).
- **Name/alias round-trips**: detector id → spec key → display name →
  processing key verified for all 8 candidates (`test_v2_only_banks.py`,
  14 tests). `/banks` lists allowlisted v2-only banks; OVERRIDE accepts them.
- **Row counts**: API txn count == v2 corpus result for every v2-served file.
- **Excel**: 48 workbooks → LibreOffice headless recalc → **0 formula errors**;
  `Statement Check` sheet present in all 48.
- **UI legs** (Playwright, real browser on `:3001`): hdfc, sbi, axis →
  DETECTED → confirm → process → completed → Excel download; citibank +
  city_union → REVIEW chip → per-doc confirm → completed → download.
  Console clean.
- **UI bug found + fixed**: v2-servable banks showed "not supported yet"
  alongside "· verified engine" in the picker — contradictory. Message now
  "Please confirm to continue." (`1506e12`)
- **Mutation probes** (first-row amount +1 → v2 checks): 7/8 banks fail
  safely; indusind is the blocker above.
- **Wrong-bank probes** (explicit OVERRIDE to a foreign bank): all 8 → job
  FAILED, never VERIFIED.
- **Flag-off identity**: sheet names + numeric-cell hash byte-identical vs
  `880b5e2` on 3 corpus files; `MISMATCH_GUARD=0` identical too.

## E5 clean-checkout gates (`wt-w11clean` @ `bd4cf0c`, detached)

| gate | result |
|---|---|
| backend suite | 465 pass, 8 fails — identical to unmodified base (missing sample PDFs / env) |
| `npx tsc --noEmit` | 0 errors |
| vitest | 29 pass |
| `npm run lint` (flat config) | 0 problems |
| `npm run build` | pass (Next 16.2.4) |
| docker build (w11 project) | `w11-backend`, `w11-frontend` built from clean checkout |
| smoke (clean image) | hdfc/citibank/city_union → v2 VERIFIED + Excel, counts 184/322/478 |

All gates passed → demo stack rebuilt from `devin/wave11` (backend + frontend
recreated; `demo-rc-stable` tags kept; rollback commands in
`docs/slice3/RUNBOOK.md`). Post-rebuild smoke on `:8000`: same three banks →
v2 VERIFIED, identical txn counts.

## Defects

| # | defect | severity | owner | status |
|---|---|---|---|---|
| 1 | indusind row-0 amount unconstrained → mutation stays VERIFIED | blocker | Claude (checks layer) | bank removed from allowlist |
| 2 | generic reconciliation `Decimal += float` crash (all v2-only banks) | high | Devin | **fixed `bd4cf0c`** |
| 3 | "not supported yet" shown for v2-servable REVIEW banks | medium | Devin | **fixed `1506e12`** |
| 4 | Keycloak `frontend-app` allows only the demo port — browser login on a second port fails `redirect_uri` | note | auth config (NOT-ALLOWED) | UI legs inject a session token instead; demo unaffected |

## Forced-sweep honesty

`c5_forced` covered 7 specs (incl. hdfc, sbi, axis, paytm). idfc, citibank,
city_union, indusind were unswept — their cross-bank `xb` is `n/a`, resting on
0 corpus wrong-bank VERIFIED + the live OVERRIDE probes (all FAILED safely).

## WHAT I COULD NOT CHECK

- Bank-side `statement_engine` badges on the **Dashboard report page** in a
  real browser for this stack (login redirect limited to `:3000`; covered by
  vitest render tests for all four block shapes incl. legacy+BANK_MISMATCH,
  and the analyze page exercised live).
- LibreOffice recalc inside the rebuilt **demo** image specifically — it is
  the same Dockerfile/layers as the w11 image where 48 workbooks passed.
- Full 5-file UI depth per bank (1 file per bank × 5 banks live; API covered
  all 40 picks).
- IndusInd post-fix — pending Claude's checks-layer change.

## Commits this wave

```
bd4cf0c fix(shared): coerce Decimal balances in generic reconciliation
1ef153a docs(slice3): E4 demo pack — 7-bank allowlist, honest per-bank table
1506e12 fix(analyze): correct message for v2-servable banks in REVIEW state
7fadc9e docs(slice3): E1 candidate table — 8 banks eligible for v2 serving
b951fa1 feat(analyze): make allowlisted v2-only banks usable end to end
```
