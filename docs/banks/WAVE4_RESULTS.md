# WAVE 4 RESULTS — variant coverage inside onboarded banks

Branch `devin/wave4`, base `008e664` (wave 3 tip). Scope: `no_layout`/`v2_failed`
clusters inside already-onboarded bank folders. Deterministic SHA-ordered
60/40 build/hold-out splits per fingerprint cluster; one commit per bank;
engine changes committed separately.

## Final gate (12,249 files, production-default run + supplementary pass over Axis/Canara/Indian Bank/ICICI/Federal under the parked registry)

| Metric | wave 3 baseline | wave 4 |
|--------|-----------------|--------|
| routed v2 | 8,275 | 9,186 |
| VERIFIED | 7,771 | 8,634 |
| FAILED | 368 | 413 |
| REVIEW | 136 | 139 |
| fallback | 3,974 | 3,063 |
| trusted (VERIFIED/routed) | 93.9% | 94.0% |
| wrong-bank VERIFIED | 0 | 0 |

Per-folder VERIFIED deltas: SBI 1,613→2,096, Kotak Mahindra 409→578,
Union 305→395, Canara 257→316, Axis 801→847, Kotak Bank 0→4,
Non_Bank_Documents 5→17, Human Verification 7→9 (evidence-backed misfiles).

Cross-folder VERIFIED = 29, all evidence-backed misfiles (folder label wrong,
PDF content genuinely the verifying bank; e.g. Union statements in
Non_Bank_Documents carry `UBIN` IFSCs). Zero wrong-bank VERIFIED.

Regression: G7 unchanged on every previously-routed file — SBI 1,641/1,641,
ICICI 800/800, Union/Federal all, Kotak 490/490, Axis+IB+Canara 1,204/1,204.
G3 forced-spec cross-bank sweeps: 0 wrong-bank VERIFIED for every new spec.

## Committed layouts

| Commit | Bank | Layouts | Build | Hold-out |
|--------|------|---------|-------|----------|
| e15f5bd | SBI | L2–L8 (7) | e.g. L2 97%, L5 14/15, L7 13/13 | l2 92%, l3 81% PARTIAL, l5–l7 100% |
| 00470fc | ICICI | L3, L4 | — | — (parked post-corpus, below) |
| f5fb427 | Union | L2, L4 | 40/41, 13/14 | 27/27, 10/10 |
| e438a06 | Federal | L2, L3 | — | — (parked post-corpus, below) |
| f9902e0 | Kotak | L4–L7 (4) | 32/33 + 27/52 + 30/32 + 8/9 | 24/24 + 21/36 + 21/22 + 4/10 |
| ac96766 | Canara | L2, L3, L4 | 21/22 + 12/13 + 1/1 | 7/8 + 6/6 + 3/3 |
| 9afddf5 | Axis | L2 | 28/33 (5 foreign refused) | 18/22 |
| 560e683 | Indian Bank | L2, L3 defined, unregistered | parked | parked |
| 6568f68 | — | unregister ICICI L3/L4 + Federal L2/L3 | — | — |

## Engine commits (separate)

- wrapped_amount_tokens + drcr_suffix_decoration (SBI-era)
- a6af0db: merge `side_marker_column` token on continuation lines
- 5b694cc-era SBI support changes

## Parked / refused variants (evidence gates)

| Variant | Reason |
|---------|--------|
| ICICI L3/L4 | corpus trusted 38%/41% — "Transactions List" exports print stale-balance reversal pairs; honest FAILED but below gate |
| Federal L2/L3 | 0 VERIFIED corpus-wide; REVIEW/FAILED only (continuation pages unanchored) |
| Kotak K8 | 0/9 files carried bank evidence |
| Kotak K9 | wrap-line side markers lost on 2 rows/file → honest FAILED, parked |
| Union U-B | PDF truncates amounts to 1 decimal (1882.8 vs needed 1882.84) — unverifiable |
| Federal F-A | single amount column, side unmarked — unverifiable |
| Indian Bank L2 | balance tokens clip at page edge (`750041.02C`) — needs clipped-suffix engine support |
| Indian Bank L3 | 62%/56% trusted; `Jan 01`-first sub-variant embeds balance inside narration line |
| Kotak K4a | 123/142 `bank_unconfirmed` — no letterhead; narration `UPI/KOTAK` not used as marker |

## Verification

- `pytest tests/statement_engine/extraction` — 73 passed; codec round-trip clean on all 66→62 specs.
- `pikepdf` missing locally — `test_analysis_service` / real-PDF module not runnable here (env gap, not a regression).
- G3 cross-bank forced-spec: 0 wrong-bank VERIFIED for every accepted spec.
- Layout assignments: no existing `resolve` assignment silently replaced (G7 0 changes on all previously-routed files).

## Open items → next wave

- Clipped-suffix engine support would unblock Indian Bank L2 (45 files).
- Balance-inside-narration handling for Indian Bank L3 Mmm-first variant.
- ICICI stale-balance exports need a reversal-pair-aware check, not a layout.
- Canara residual ~7 files (2 further header sub-variants, small).
- K4a-class files need per-layout `allow_header_only` or better letterhead evidence.
