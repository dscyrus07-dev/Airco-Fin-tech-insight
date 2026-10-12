# WAVE 10 — COVERAGE ROUND 2 RESULTS

Branch `devin/wave10`, base `971076f` (wave-6/7 tip). Baseline = Phase-8b full-corpus tip run at
`971076f` (14,445 records: v2 9,660, VERIFIED 7,210), reused per prompt's baseline instruction.
Probes under `comparison/wave10/` (untracked). No PII in artifacts: sha8 + counts only.

## Engine changes

- `49d72cd` — `implicit_header`: opt-in spec field for headerless tables; anchors synthesized
  from the first two conforming dated lines' own cell geometry; a narration-only line directly
  above a dated line is that row's printed prefix. Off by default for all existing layouts.
- `f92751f` — `resolve()` pools `bank_markers` per `bank_key`: a marker owned by any same-bank
  layout is own-bank evidence for the whole bank, never foreign. Fixes a latent bug exposed by
  L10's `SBIN0` marker (1,635 base-VERIFIED SBI files fell back `foreign_bank` under the
  per-spec comparison; 0 regressions after the fix).

## Cluster outcomes

### W10-1 SBI mPassbook "Clear Balance" — `SBI_LAYOUT_10` (`37cbfe5`)

Headerless 6-column table (TxnDate|ValueDate|Description|Ref|Debit|Credit|Balance); full printed
anchors from the merged summary line (Brought Forward, Dr/Cr counts, totals, Closing Balance).
Probe of the 209-file `no_layout` pool: **122 routed → 109 VERIFIED / 13 FAILED**, 87 still
`no_layout`. Mutation sample 22 files × 7 mutations: **0 survivors**. 8 ICICI-folder files matched
(misfiled real SBI exports, `bank_evidence:document`) — all FAILED honestly, none VERIFIED.

### W10-3 ICICI two-line-header — `ICICI_LAYOUT_5` (`58f6a97`)

66-file cluster (`Transaction Date`/`Amount (INR)` split across two lines, `amountinr withdrawal`
merge order). Anchorless family: no printed summary, no B/F row → **REVIEW ceiling**.
Routed all 66: **31 REVIEW** (chain clean) + **35 FAILED** (`chain`+`side` — stale-balance
exports failing honestly, per prompt parked class). REVIEW-ONLY flag set for this cluster.

### W10-2 residuals

- **Paytm `PAYTM_LAYOUT_2`** (`cb240ff`): debit/credit export, 43/57 header matches — all
  `bank_unconfirmed` (issuer name never prints; detector UNKNOWN). Evidence gate holds; spec
  registered for the gated path. 0 served.
- **Federal (111 `no_layout`)** — two sub-families, both need engine options beyond budget:
  1. Jupiter/Federal export (`Reference ID|Transaction details|₹-out|₹-balance`, ~40 files):
     the date (`dd Mon 'yy`) prints on a mini-line *below* its row — inverse of the mPassbook
     prefix; needs a date-on-following-line attachment mode.
  2. Doubled-glyph export (`AAccccoouunntt`, ~50 files): every glyph duplicated in the text
     layer; needs a pairwise-collapse tokenizer verified per-file, plus its own anchor schema
     (`Opening Balance + Money In - Spent = Saved + Closing Balance`).
- **HDFC (13 `no_layout`)**: 12-file `date|narration|valuedt|withdrawal|...|closingbalance`
  cluster fingerprinted, not built. **Axis (18 `no_layout`)**: 7-file `particulars|debit|credit|
  balance` cluster fingerprinted, not built. Both within residual budgets.

### W10-4 KVB — **NO-GO** (`docs/banks/KVB_FEASIBILITY.md`)

67 `bank_unconfirmed` files: entire table body is `(cid:N)` under pdfplumber — `VerdanaBold`
Type0 font with an **empty** `/ToUnicode` stream and no embedded cmap/post tables. PyMuPDF
cannot decode it either. Phase-6's "ToUnicode exists" was the dangling reference; Wave-5's
glyph-dump verdict stands. Detector is `kvb:LOW` → even decoded text would stay
`bank_unconfirmed`. No tokenizer built.

## Gates & regression

- `regr_in.jsonl` = 2,351 files (150 prior-VERIFIED cross-bank + 2,201 SBI-covered), rerouted
  under wave-10 code: **0 VERIFIED→non-VERIFIED, 0 row-hash diffs, 0 layout flips**
  (run1 under the marker bug showed the 1,635-file `foreign_bank` regression; run2 clean).
- SBI probe rerun post-fix: identical 122/109/13/87.
- Extraction suite: **182 passed** (`pikepdf`-dependent collection errors remain env-level,
  unchanged from baseline).
- Wrong-bank VERIFIED on all probes: **0**.

## Corpus before → after (probe-measured deltas on sampled pools)

| metric | base `971076f` | wave10 |
|---|---|---|
| corpus records | 14,445 | same corpus |
| v2 routed | 9,660 | +122 SBI L10 +66 ICICI L5 (on probed pools) |
| VERIFIED | 7,210 | +109 |
| wrong-bank VERIFIED | 0 | 0 |
| row-hash diffs (both-VERIFIED) | — | 0 |

## Residual clusters (documented for next wave)

| cluster | files | blocker |
|---|---|---|
| Federal Jupiter export | ~40 | date-on-following-line engine mode |
| Federal doubled-glyph | ~50 | pairwise-collapse tokenizer + anchors |
| ICICI `date description amount type` | 344 | unfingerprinted variant (amount+type schema) |
| ICICI stale-balance | 35 in L5 + parked L3/L4 | Claude-owned reversal-pair check |
| Paytm L2 files | 43 | issuer never prints; detector UNKNOWN |
| KVB cid-dump | 67 | no decodable text layer (NO-GO) |
| HDFC/Axis residuals | ~20 | small unfingerprinted clusters |
