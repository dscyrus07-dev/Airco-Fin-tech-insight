# PROMOTE_RESULTS — prompt 27 outcomes (base `integration/v2-waves @ c550bac`, branch `devin/promote-1`)

All measurements re-run in shadow mode against the real corpus (`runA` + per-bank
fresh measurements). Gates: det 100% on readable files · 0 cross-bank accepts ·
≥90% text-file yield (VERIFIED or REVIEW w/ rows) · ≥80% VERIFIED where printed
balances exist · clean spec-independent audit (≤40 VERIFIED files).

## Candidates

| bank | before | after | gates | status |
|---|---|---|---|---|
| au_sfb | det 94.1%, 14V, yield 82.4% | 16/17 v2 VERIFIED, yield 94.1%, Vshare 100% | det caveat: 1 file has zero own-bank evidence (correctly unroutable); audit 16/16 clean; cross 0/388 | **READY_TO_SERVE_CANDIDATE** |
| bank_of_maharashtra | det 100%, yield 63.0%, Vshare 47% | 26/27 routed: 21V+5R, yield 96.3%, Vshare 80.8% | audit 19 clean + 2 sign-regex artifacts (anchors verified to match); cross 0/388 | **READY_TO_SERVE_CANDIDATE** |

## Improved, still SHADOW_ONLY

| bank | before | after | why not candidate |
|---|---|---|---|
| dbs | yield 84.8%, 0V | 110V+4R+6F, yield 87.0% (114/131 text), audit 40/40 clean | <90%: 9 balance-less-layout files = engine gap (single amount, no balance column) |
| airtel_pb | 4/4 FAILED (schema) | 4/4 VERIFIED, audit 4/4 clean | corpus 7 files, 3 are billing docs (different document class); thin evidence |
| uco | 4R+3F+2 fallback, yield 44.4% | 5R+4F, yield 55.6% | corpus 9 files; remaining FAILEDs are real doc defects (see below) |

## Parked (engine gap / corpus problem — no spec-level fix)

| bank | finding |
|---|---|
| bandhan | 5 unrouted files are label:value advice documents (non-columnar); 3 foreign_bank refusals are multi-bank docs correctly refused |
| pnb | dominant missing variant lifts yield only to ~82–87%; the untitled-leading-date-column shape (8 files) is an engine gap; gate unreachable |
| dcb | multi-account exports: printed `TotalNumberofTransactions` (22–9,328) far exceeds extracted rows (4–121); sub-table continuation is an engine gap; `reference failed` is honest |

## Fixes applied (spec/detector only — no engine/checks/registry-policy changes)

- **au_sfb** `AU_LAYOUT_2`: wrapped two-line header (`Transaction|Date` merge via
  `("transaction",)` date alternative), `header_wraps`, per-column `band_left_pad`,
  `amount_sign_gap` for `- 39,457.19`, `AUBANK.IN` furniture marker (replaces bare-IFSC-class evidence).
- **dbs**: `opening_balance_re` on L1 (undated `Opening Balance` line now anchored → 109/112 REVIEW→VERIFIED); new `DBS_LAYOUT_2` (Branch Code variant, INR-prefixed summary anchors).
- **bank_of_maharashtra**: ref-title alternatives widened on L1/L2 (+ anchors on L2); new `BOM_LAYOUT_3` (no cheque col) and `BOM_LAYOUT_4` (withdrawals/deposits, dd/mm/yy, `0.00` empties, `Cr`-suffix balances, `B/F` opening row, 3-figure Total line).
- **airtel_pb**: `opening_row_balance_only`, `Closing(?:Day)?Balance`, credit-first `Total Credits/Debits` totals line.
- **uco**: `row_order="auto"` on L1/L2 (newest-first exports); wider opening/closing anchors (surfaced genuine doc inconsistencies → honest FAILED); `UCO_LAYOUT_3` (CHQ.NO., WITHDRAW/ALS wrap, left-aligned amounts, `x.xx CR` balances), `UCO_LAYOUT_4` (dd-MMM-yyyy, integer amounts).

## Regression proof

- statement-engine suite: **391 passed** (was 383 at base; +8 new tests).
- non-engine suite: 336 passed / 18 skipped / 8 failed — identical 8 pre-existing failures (missing sample PDFs, rule-engine fixture count, api-key event loop) as on base.
- corpus compare base `c550bac` vs tip, 613 files across 14 of the 15 existing banks:
  **0 diffs** at the 3-bank gate; **3 diffs** at tip — all in the karnataka folder and all
  `fallback -> v2/FAILED` under `UCO_LAYOUT_3`. Verified: the 3 files print their own-account
  `UCBA` IFSC and no karnataka text — they are UCO statements misfiled in the karnataka
  folder. Routing is correct-by-evidence and the verdict is honest FAILED (space-glyph
  amount cells), not an acceptance. L3 kept; documented here rather than reverted.
- cross-bank: 388-file pooled sample across 50 folders — **0** accepts under `au_sfb`/`dbs`/`bank_of_maharashtra`/`airtel_pb`/`uco` specs.
- `app.main` import smoke: ok. Marker collisions test: in suite (no new markers; `AUBANK.IN` is ≥7-char furniture evidence, not a bare IFSC).

## Wiring

Candidates wired the same as other onboarded banks (spec-key aliases already present
from prompt-25 wiring). New `ONB_EXTRA_SERVE_BANKS` compose variable appends candidate
banks to the shipped `ONB_SERVE_BANKS` default without editing code:
`ONB_EXTRA_SERVE_BANKS=au_sfb,bank_of_maharashtra`. `SERVE_BANKS` defaults unchanged.
