# Demo Script — 15 minutes (Wave 11)

> **[N9 update — `devin/n9-final`]** This document predates the N5–N7 night
> wave. Where it says a bank is "legacy", "not eligible", "fails honestly", or
> "not supported" for `bob` (Bank of Baroda), `canara`, `icici`,
> `indian_bank`, `karnataka`, or `kotak`, that is now stale: all six are
> v2-VERIFIED-capable (SERVE_V2_WITH_LEGACY_FALLBACK, GO per
> `docs/onboarding/N7_REPORT.md`). The proposed served list is the 14-bank
> default plus those six (carried on the `rc` stack via env var; the shipped
> default is unchanged). Statements about `union`, `bank_of_india`, IndusInd,
> and the other unlisted banks still stand.

Prep: stack up per `RUNBOOK.md`, flags

```
STATEMENT_ENGINE_V2_MODE=serve
STATEMENT_ENGINE_V2_SERVE_BANKS=hdfc,sbi,axis,idfc,paytm,citibank,city_union
```

**Update `411f6ca` (rollout):** `onb` now defaults to the 14-bank list —
`…,au_sfb,bank_of_maharashtra,airtel_pb` (VERIFIED-capable; airtel thin
corpus) + `iob,apgv,south_indian,pnb` (review-only — always "Needs review",
`NO_INDEPENDENT_ANCHOR`). **Axis caveat:** served, but the audit found a
truncated statement (`000df35f`) that printed VERIFIED on 1,141/1,147 rows;
the completeness guard now lands it REVIEW (`unread_transaction_lines:6`).
Don't present Axis as unconditionally clean — the line is "verified, with
completeness checks that catch truncated statements."

Browser: `http://localhost:3000` — sign in with the dev-realm account (see RUNBOOK).
All flows run on the **Analyze statements** page (`/analyze`).

Candidate statements (sha8 + folder only — no PII):

| sha8 | folder | role in demo |
|---|---|---|
| `0000d106` | HDFC Bank | VERIFIED hero — v2 engine |
| `0f28d0b0` | City Union Bank | the deliberate "Needs review" moment |
| `00ae22c1` | Citibank | previously "not supported" — now works via v2 |
| `00d70d3a` | IndusInd Bank | the honest unsupported message |

## 1. Landing + login (1 min)

Home → sign in → Analyze statements. Say: "The product detects the bank and
layout before anything is processed — nothing runs on a guess."

## 2. HDFC — verified end to end (4 min)

Upload the HDFC file → **Analyze** → DETECTED with evidence chips (IFSC in the
header, bank domain) → Confirm → Process.
When it completes, download the Excel and open the **Statement Check** sheet:
`Engine: v2`, `Verdict: VERIFIED`, `Independently verified: yes`. The badge
reads "Verified · independently checked".
Say: "Verified means the numbers were checked independently of the parser —
a tampered amount would fail this check; we tested that on seven banks."

## 3. Citibank — a bank that used to fail (4 min)

Upload the Citibank file → it lands in **REVIEW** ("This looks like a Citibank
statement. Please confirm to continue.") — the picker already shows
"Citibank · verified engine". Confirm → Process → VERIFIED.
Say: "Before this wave this bank had no parser at all — it was refused at the
gate. The new engine covers it, the evidence gate passed, so it is served.
Bank by bank, only after proof."

## 4. City Union — the deliberate "Needs review" (3 min)

Upload the City Union file → confirm → process → it completes with a
**Needs review** badge, reason: *"No printed opening/closing summary to
verify against"* (`NO_INDEPENDENT_ANCHOR`).
Say: "This is a completed report, not a failure — the engine extracted the rows
but this statement prints no closing-balance chain to anchor against, so the
product says so instead of pretending. Review means 'a person should look',
and the Excel still downloads."

## 5. IndusInd — the honest "not supported yet" (2 min)

Upload the IndusInd file → "This looks like an IndusInd Bank statement. That
bank is not supported yet."
Say: "The engine covers this bank in testing, but one of our safety probes
found a case its checks don't catch — so it stays off until that's fixed.
We'd rather show 'not supported' than a number we can't stand behind."

## 6. Dashboard (1 min)

Show history: Verified and Needs-review badges persist on past jobs
(`statement_engine` is stored with each job).

## What NOT to show

- Bank-of-X-as-bank-Y overrides — the job fails by design; a failure is not a
  demo moment.
- Locked/passworded PDFs (out of scope).
- Bank of Baroda / Indian Bank / Canara / Union — the legacy parser fails
  honestly; they are not eligible for v2 serving yet (see `V2_ENABLEMENT.md`).

## Reset procedure

```bash
python comparison/demo/reset_demo.py   # clears the demo user's history
```

## Fallback if a service dies

```bash
docker compose -f infra/docker/docker-compose.yml --env-file local.env up -d backend   # or frontend / keycloak
```

If the v2 path misbehaves: flip `STATEMENT_ENGINE_V2_MODE=off` in `local.env`,
`up -d backend`, and every bank is back to legacy — the HDFC flow then shows
the normal "everyday" path instead of a verified badge. Last resort: roll back
to the tagged images — see RUNBOOK "Rollback".

## 9. Unified entry (flag-gated — do not enable for the standard demo)

When `NEXT_PUBLIC_UNIFIED_ENTRY=on` is set on the frontend build, `/dashboard`
becomes the single entry: Upload (drag up to 20 PDFs, optional holder name +
"I already know the bank" hint) → Review (per-file detected bank, evidence,
override dropdown, statement type, inline password unlock) → Processing
(parallel jobs, one progress card per file) → Report (the existing report
view with the verification badge and downloads, per file). `/analyze`
redirects to `/dashboard` and the header loses the Analyze link. The Mode
step is skipped (free mode). With the flag off, everything in sections 1–8
applies unchanged.
