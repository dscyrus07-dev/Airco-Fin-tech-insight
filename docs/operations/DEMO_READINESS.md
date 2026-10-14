# Demo Readiness — Wave 11 (v2 enablement)

Branch: `devin/wave11` (local only). Demo stack: `..\wt-demo` compose project.
Recommended flags:

```
STATEMENT_ENGINE_V2_MODE=serve
STATEMENT_ENGINE_V2_SERVE_BANKS=hdfc,sbi,axis,idfc,paytm,citibank,city_union
STATEMENT_ENGINE_V2_SERVE_TIMEOUT_S=30
```

**Update `411f6ca` (rollout):** `onb` now defaults to the 14-bank list —
append `au_sfb,bank_of_maharashtra,airtel_pb` (VERIFIED-capable; airtel thin
corpus — 3 usable files) and `iob,apgv,south_indian,pnb` (review-only: always
needs-review, `NO_INDEPENDENT_ANCHOR`). **Axis caveat:** the audit found a
truncated-statement file (`000df35f`) that printed VERIFIED on 1,141 of 1,147
rows. On the current tip the completeness guard catches it — it lands REVIEW
with `unread_transaction_lines:6`. Do not demo Axis as unconditionally clean;
the correct line is "verified, with automated completeness checks that catch
truncated statements."

Every bank shows exactly what is true today — v2 VERIFIED, v2 needs review,
legacy processed, or not supported. Nothing unverified is presented as verified.
IndusInd is deliberately **not** allowlisted: it passed every corpus gate but
failed the live mutation probe (see `V2_ENABLEMENT.md`), so it stays off until
the checks-layer fix lands.

## Per-bank table (recommended config)

| Bank | Serving | What the demo shows | Evidence |
|---|---|---|---|
| HDFC Bank | **v2** | VERIFIED badge + `Statement Check` sheet | 3/3 VERIFIED E3 picks; mutation caught → FAILED |
| State Bank of India | **v2** | VERIFIED; REVIEW files defer to legacy | 3/3 VERIFIED E3 picks |
| Axis Bank | **v2** | VERIFIED | 3/3 VERIFIED E3 picks — **caveat**: audit-WRONG truncated file (`000df35f`); now caught by completeness guard → REVIEW |
| IDFC First | **v2** | VERIFIED; REVIEW files defer to legacy | 3/3 VERIFIED E3 picks |
| Paytm Payments | **v2** | VERIFIED (detector-only evidence class — sweep gate met) | 5/5 VERIFIED E3 picks |
| Citibank | **v2** | VERIFIED — was "not supported" before this wave (no legacy processor) | 5/5 VERIFIED E3 picks; UI leg PASS incl. Excel download |
| City Union | **v2** | VERIFIED, or honest "Needs review" (`NO_INDEPENDENT_ANCHOR`) | 3 VERIFIED + 2 REVIEW E3 picks; UI leg PASS |
| ICICI Bank | legacy | Processes as today | v2 not eligible (trusted 76.3 < 94) |
| Kotak / Kotak Mahindra | legacy | Processes as today | v2 not eligible (trusted 88.3 < 94) |
| Karnataka Bank | legacy | Processes as today | v2 not eligible (fail 5.4 > 5) |
| Bank of India | legacy | Processes as today | not in v2 spec set |
| Bank of Baroda | legacy | Fails honestly ("PDF does not appear to be a Bank of Baroda statement") | v2 not eligible (trusted 93.3 < 94, fail 22.2) — **not a demo "review" moment, it is a failure** |
| Indian Bank | legacy | Fails honestly (issuer validation) | v2 not eligible (trusted 93.3, fail 6.9, anchored 34.6%) |
| Canara Bank | legacy | Fails honestly (no transaction table) | v2 not eligible (trusted 92.1, fail 8.1) |
| Union Bank | legacy | Fails honestly (row extraction) | v2 not eligible (fail 5.8, anchored 3.5%) |
| IndusInd Bank | **off** | "This looks like an IndusInd Bank statement. That bank is not supported yet." | BLOCKED — first-row amount mutation stayed VERIFIED; removed from eligibility |
| ~29 other folders | — | Detector UNKNOWN / unsupported — refused cleanly | not in the product set |

## What E3 verified (live API + browser, w11 stack :8005/:3001)

- **V2-only banks end-to-end**: Citibank and City Union have no legacy processor —
  analyze → confirm → process → Excel works through the generic downstream path.
- **Counts**: API txn counts equal the v2 corpus result for every v2-served file.
- **Excel**: 48 workbooks recalculated headless in LibreOffice — 0 formula
  errors; `Statement Check` sheet present in all 48.
- **UI legs** (5 banks through a real browser): HDFC, SBI, Axis → DETECTED →
  confirm → process → completed → Excel download; Citibank + City Union →
  REVIEW chip → per-doc confirm → completed → download. Console clean.
- **Mutation probes** (first-row amount +1 through the v2 checks): HDFC, SBI,
  Axis, IDFC, Paytm, Citibank, City Union all **fail** verification — tampered
  numbers never stay VERIFIED. **IndusInd fails this test** → blocked.
- **Wrong-bank probes** (file of bank X explicitly submitted as bank Y via
  OVERRIDE): all 8 tested banks → job FAILED, never VERIFIED.
- **Kill switch**: `STATEMENT_ENGINE_V2_MODE=off` produces byte-identical output
  to the `880b5e2` baseline (3-file check, sheet names + numeric hash).

## Honest claims only

- Say "verified by an independent check" for v2 VERIFIED banks only.
- Do **not** say "counts match independent parsing" — the evidence is the
  corpus comparison in `V2_ENABLEMENT.md`, phrased as trusted rate over
  anchored files.
- A "Needs review" result is a completed, downloadable report with review
  reasons — never a failure and never a verified badge.
