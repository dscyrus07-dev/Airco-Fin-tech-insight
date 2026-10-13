# ONB stack rebuild from merged tip — Part A results (prompt 27)

Base: `integration/v2-waves @ c550bac` (merge of onboarding + wiring + verification +
Claude fixes `f870876` IPPB marker drop, `d58bcf8` Statement Check Needs-review honesty).
Branch: `devin/promote-1`. Rebuilt: `onb-backend:pr1`, `onb-frontend:pr1` → tagged `:latest`.
Leftovers removed: `onb-auth-service:latest` (551 MB, unused) + 2 dangling onb images.
All identifiers below: bank ids / sha8 / counts only.

## Image verification

| check | result |
|---|---|
| spec count inside image | **81** — identical to repo registry |
| IPPB marker | `INDIAPOSTPAYMENTSBANK` — bare `IPPB` marker gone (fix present) |
| Statement Check fix | `needs_review` logic + `"Needs review" yes` row present in `serve.py` |

## Stack health

`onb_backend` healthy :8401 · `onb_frontend` 200 :3400 · `onb_redis`, `onb_rabbitmq` healthy.
Protected containers before/after — **identical IDs, uninterrupted uptime**:

`airco_auth_service` 8e2e980a8292 · `keycloak` fb9949a38cac · `keycloak-postgres`
9b188150407d · `ue_backend` bafad1db0191 · `ue_frontend` 8370c7f6fe09 ·
`ue_rabbitmq` 6aa001419890 · `ue_redis` b48f553aa2b6.

## End-to-end checks (real authenticated HTTP)

| check | sha8 | bank | result |
|---|---|---|---|
| (a) prior-regression file | `d4de1ead` | paytm | **PASS** — analyze→confirm→process→completed→download; shadow `v2/VERIFIED/103 rows`; workbook Transactions = **103** (matches engine exactly) |
| (b) Statement Check honesty | `0a05a1f7` | hdfc | **PASS** — `Engine: legacy`, `Verdict: FAILED`, `Needs review: yes`, `Advisory verdict: FAILED` with reason codes + explanatory note |
| (c) 7 served banks ×1 file | `04bf0571` | axis | PASS — completed, 583 rows, valid workbook |
| | `64e104f2` | citibank | PASS — 455 rows |
| | `7ef6e782` | city_union | PASS — 163 rows |
| | `08962736` | hdfc | PASS — 50 rows |
| | `06077ac4` | idfc | PASS — 144 rows |
| | `d4de1ead` | paytm | PASS — 103 rows |
| | `008dd08d` | sbi | PASS — 204 rows |
| (d) non-allowlisted | `019d7c3f` | standard_chartered | **PASS** — `UNSUPPORTED`, confirm refused `BANK_REQUIRED`, no job |
| (e) browser, port 3400 | 2 files (hdfc + scb) | — | **PASS** — sign-in OK; HDFC row DETECTED w/ bank select + Confirm; UNSUPPORTED row has **no select, no default bank, no Confirm**; no hscroll at 360 and 1280; 0 console errors |

## Residual (reported, not a new defect)

`0a05a1f7` workbook contains 38 transaction rows where the v2 advisory engine read 49 —
now **disclosed** on the Statement Check sheet (`FAILED` + `Needs review: yes` + note)
instead of silently served. The row-count divergence itself is the known legacy-vs-engine
gap, not fixed by `d58bcf8` (whose scope was honesty, not extraction parity).

Verdict: **Part A PASS** — both merged fixes verified live end-to-end.
