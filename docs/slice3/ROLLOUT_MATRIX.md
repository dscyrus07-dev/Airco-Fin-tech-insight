# ROLLOUT MATRIX — turning v2 on behind `STATEMENT_ENGINE_V2_MODE`

Branch `devin/wave3` tip. Corpus: 14,445 files (12,249 readable). "Verified %" =
VERIFIED / v2-routed on the wave3 full run; coverage column counts folder total.
GO = safe to serve behind flag; GO-WITH-FIXES = works but has a named defect;
NO-GO = do not enable; LEGACY-HOLD = pinned to legacy parser by decision.

| Bank | Files | v2 | VERIFIED | Verified % | Decision | Top failure / gap | Next action |
|------|------:|---:|---------:|-----------|----------|-------------------|-------------|
| HDFC | 2,433 | 2,288 | 2,263 | 98% | GO | uncovered layout variants (no_layout ×51) | fingerprint the 51 fallbacks |
| SBI | 2,956 | 1,641 | 1,613 | 98% | GO | variant gap (no_layout ×814) | cluster the 814 |
| ICICI | 1,504 | 800 | 639 | 79% | GO-WITH-FIXES | 161 FAILED + big variant gap | classify FAILED cohort |
| Axis | 1,023 | 813 | 801 | 98% | GO | no_layout ×103 | variant census |
| Canara | 420 | 310 | 257 | 82% | GO-WITH-FIXES | REVIEW ×24, FAILED ×29 | check-date classes |
| Kotak | 1,096 | 480 | 409 | 85% | GO-WITH-FIXES | no_layout ×519, REVIEW ×57 | variant census is the gap |
| Bank of Baroda | 317 | 72 | 56 | 77% | GO-WITH-FIXES | bank_unconfirmed ×100 (brand is image-only) | `allow_header_only` opt-in per layout |
| Federal | 344 | 102 | 95 | 93% | GO-WITH-FIXES | no_layout ×189 | variant census |
| Indian Bank | 177 | 85 | 62 | 72% | GO-WITH-FIXES | REVIEW ×17 + variants | classify REVIEW |
| Karnataka | 178 | 93 | 88 | 94% | GO | variant gap | — |
| IDFC First | 334 | 276 | 258 | 93% | GO | — | — |
| Paytm PB | 223 | 141 | 139 | 98% | GO | — | — |
| Union Bank | 783 | 306 | 305 | 99% | GO | no_layout ×294 | variant census |
| SCB | 232 | 169 | 147 | 86% | GO-WITH-FIXES | foreign_bank ×22 over-fires | narrow foreign markers |
| DBS | 137 | 118 | 109 | 92% | GO | — | — |
| Citibank | 106 | 61 | 60 | 98% | GO | — | — |
| Karur Vysya | 83 | 4 | 3 | 75% | NO-GO | bank_unconfirmed ×67 (weak text brand) | needs evidence path or header opt-in |
| HSBC | 91 | 22 | 21 | 95% | GO | small corpus | — |
| IndusInd | 136 | 85 | 81 | 95% | GO | — | — |
| PNB | 107 | 56 | 56 | 100% | GO | — | — |
| IDBI | 104 | 54 | 45 | 83% | GO | parked L3 side-marker shape | design note exists |
| Yes Bank | 128 | 54 | 36 | 66% | NO-GO | FAILED ×18 | classify FAILED before enabling |
| IOB | 66 | 53 | 53 | 100% | GO | — | — |
| South Indian | 33 | 28 | 25 | 89% | GO | — | — |
| Central Bank of India | 46 | 28 | 24 | 85% | GO-WITH-FIXES | L1 partial (damaged rows stay FAILED) | — |
| Equitas SFB | 40 | 28 | 23 | 82% | GO-WITH-FIXES | isolated chain breaks | — |
| City Union | 37 | 2 | 2 | 100% | NO-GO (routing) | union detector FP blocks all routing | fix detector yes/union precision |
| Ujjivan SFB | 33 | 24 | 20 | 83% | GO-WITH-FIXES | side-marker cluster parked | needs sample or marker col support |
| Bank of Maharashtra | 30 | 17 | 17 | 100% | GO | — | — |
| Bandhan | 19 | 10 | 10 | 100% | GO | — | — |
| AU SFB | 17 | 14 | 14 | 100% | GO | — | — |
| DCB | 16 | 15 | 14 | 93% | GO | 1 honest FAILED (source damage) | — |
| APGV | 15 | 13 | 13 | 100% | GO | — | — |
| Bank of India | 73 | 0 | 0 | — | LEGACY-HOLD | `legacy_only:bank_of_india` enforced | exit criteria in BANK_STATUS.md |
| Refused/insufficient banks | — | 0 | 0 | — | NO-GO by design | correct refusal verified corpus-wide | more samples per BANK_STATUS.md |
