# Shadow readiness: fixes after Phase 7

Base: Wave 5 tip `e8ab437` (fast-forwarded; rollback tag `rollback/pre-wave5-b2bb4a4` at `b2bb4a4`). Shadow mode is **not** enabled by this work.

## Changes
| Fix | Where | Effect |
|---|---|---|
| Shadow hook fail-safe | `shadow.py`, `pipeline_orchestrator.py` | An unsupported mode (`serve`, anything `v2_mode()` rejects) is logged (setting name + error type only) and v2 is skipped; the legacy result is never changed or interrupted. `v2_mode()` still raises for `serve`. The orchestrator call is also wrapped (defence in depth). |
| No VERIFIED without an independent anchor | `checks.decide` | If the printed summary gives no opening or closing balance, the opening is derived from row 0 and a corrupted first row shifts the chain in lockstep. Such results are capped at REVIEW whether or not the layout expects a summary. |
| SBI layout 2 retired | `extractors/registry.py` | 0 of 12,249 corpus files route to it; 2,497 SBI-related files give identical route, verdict and row hash without it. The spec definition stays in `sbi/layout_spec.py`. |
| Yes L3 claim corrected | `BANK_STATUS.md`, `WAVE5_RESULTS.md` | 13/30 = 43% corpus-wide (8/9 was one sub-cluster). Layout not tightened. |
| Citibank `(INR)` reason corrected | `WAVE1_RESULTS.md`, `BANK_STATUS.md` | Balance(INR) header is present in 5/5 files; the running balance is missing on most dated lines. |

## Cost of the anchor rule (measured, full corpus, 12,249 files)
| | Wave 5 tip | After fixes |
|---|---|---|
| Routed to v2 | 9,435 | 9,435 (0 route changes) |
| VERIFIED | 8,854 | 6,865 |
| Trusted rate (VERIFIED / v2) | 93.84% | 72.76% |
| Trusted rate where an independent anchor exists | | 94.21% (6,865 / 7,287) |

1,989 files moved VERIFIED to REVIEW; 2,148 v2 results have no independent anchor and none is VERIFIED. No row content changed (0 row-hash differences). They still produce output, flagged for review. The loss is concentrated in Union (504), SBI (456), ICICI (159), Paytm (139), Kotak (118), DBS (109). It can be recovered legitimately, layout by layout, by configuring `opening_balance_re` or `closing_balance_re` where the statement prints one.

## Open risks
- One VERIFIED file in the Axis folder resolves to Canara on document-level name evidence (both bank names appear); not resolvable from text alone.
- 12 VERIFIED files in `Non_Bank_Documents` are genuine statements (11 Union with a printed UBIN IFSC, 1 Bank of Baroda with a printed BARB IFSC): misfiled folders, not false trust.
- Large `no_layout` clusters remain (2,069 files); `bank_unconfirmed` 453.
- Golden fixtures with customer PII are still tracked (see `comparison/wave3/GOLDEN_PII_PLAN.md`, not committed). **Pushing stays blocked** until a remediation option is approved and executed.
