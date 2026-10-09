# Wave 5 — detector precision, parked engine items, honest hold-outs, coverage round

Base: `b2bb4a4` (last `READY FOR DEVIN:` on `feature/statement-engine-v2-foundation`).
Branch: `devin/wave5`. Corpus: 14,445 files (readable pool routed by `v2_router`,
production defaults, 4 workers). Working artifacts: `comparison/wave5/` (untracked).

## Commits

| Commit | Type | What |
|--------|------|------|
| `3c8db15` | detector | issuer-line evidence tightening: amount/date-at-start/UPI-NEFT-IMPS lines can no longer carry issuer-name evidence; `city_union` bank entry added (`banks/city_union.json`) — fixes union→CUB false block and Yes-Bank false positives on ICICI/Axis files |
| `12d5921` | detector | `RoutedExtraction.notes` now carry `detector:<id>:<conf>:<score>` + `runner_up:<id>:<score>`; marker-less (`bank_markers=()`) banks route only at HIGH/VERY_HIGH confidence, or MEDIUM + header found + runner-up ≤ half winner's score (`_DETECTOR_ONLY_GATE` in `v2_router.py`) |
| `0a6f371` | detector | sub-threshold detections no longer fall back to `other_bank:<id>` — they return UNKNOWN instead of a wrong-bank refusal |
| `ca24929` | engine | opt-in `header_only_ok` (default off, codec round-tripped, synthetic test); set on **no** layout |
| `7fe013e` | engine | opt-in `clipped_drcr_suffix` — a lone trailing `C`/`D` on a balance token completes clipped `Cr`/`Dr`; chain check still governs |
| `ecea5aa` | engine | `_add_years` leaves dates already completed by `date_tail` alone; `|`-alternation date formats supported; candidate years tried in order until one fits the printed period |
| `94db5e0` | feat | Indian Bank L2 `indianbank_postdate_remitter_description_chequeno_dr_cr_balance_yearless` — 42/45 cluster VERIFIED, G3 0 foreign, G7 0 diffs |
| `44fd191` | feat | Yes Bank L3 `yes_transaction_valuedate_referencenumber_*_runningbalance` (8/9 on the referencenumber sub-cluster; **13/30 = 43% corpus-wide**, see Phase 7 correction); L2 wrapped-running-balance defined but **parked** (5/21 = 24% trusted) |

## Part A — detector precision

Confusion-matrix inputs: every readable corpus file, `detect_bank` per file
(`comparison/wave5/det_before_*.jsonl` / `det_after_*.jsonl`).

Fixes (evidence tightening, no exceptions added):

1. A line carrying an amount, a strong date at position 0, or a narration token
   (`UPI/`, `NEFT/`, `IMPS/`, `RTGS`) can never carry issuer-name evidence —
   kills the Yes-Bank false positives caused by repeating running-header lines
   that also carry amounts.
2. A bank name inside a line that also holds an amount never counts.
3. `city_union` detector entry added; "City Union Bank" now wins over `union`
   on CUB files (DOMAIN + HEADER_NAME + IFSC kinds).
4. Marker-less banks (PNB, Yes, IOB, SIB, …): HIGH/VERY_HIGH only, or MEDIUM
   with table header found and runner-up ≤ half the winner — named gate
   `_detector_only_gate` in `v2_router.py`.
5. LOW/sub-threshold detections return UNKNOWN rather than a wrong
   `other_bank:` short-circuit.

Matrix diff (before → after, on the compared subset — full table below):

| Move | Count | Assessment |
|------|-------|------------|
| union(MEDIUM) → city_union(VH/HIGH) on CUB folder | 19 | **fix** — CUB unblocked |
| yes(MEDIUM) → UNKNOWN on Axis folder | 2 | **fix** — the known FP pair |
| axis/idfc/dbs/sbi MEDIUM/LOW → UNKNOWN | 5 | FP suppression; files now unconfirmed instead of wrong-bank |
| same-bank confidence reshuffles (axis/icici/federal) | ~21 | recalibration only, no bank change |
| UNKNOWN → city_union(VH) | 1 | recovery |

Full-matrix diff (12,249 files, before → after):

- Bank-id moves: 58 total; **0 correct→wrong**.
  - `union → city_union` ×35 on City Union folder + `UNKNOWN → city_union` ×2
    (CUB unblocked end-to-end).
  - wrong→UNKNOWN ×12 (yes×4 on Axis, axis×3 + idfc×2 + union×1 on ICICI,
    dbs×1 on Axis, indusind×1 on Yes) — false positives suppressed.
  - correct→UNKNOWN ×3 (one SBI, one HDFC, one PNB file): all three were
    `fallback`/unroutable at baseline — zero routing loss; the detections were
    single-evidence-thin.
- Confidence histogram: VERY_HIGH 6,382→6,416; HIGH 2,875→2,870;
  MEDIUM 1,070→1,042; LOW 204→190; UNKNOWN 1,718→1,731 (+13).
- Routing effect measured in the corpus run: `detector_weak` refuses 10 files
  (7 were baseline-FAILED Yes files, 3 were unrouted anyway); CUB folder
  0→37 VERIFIED.

Correct→wrong moves: **0**.

## Part B — header-only policy

`header_only_ok` shipped opt-in and OFF. Full candidate analysis, collision
table and forced wrong-accept proof in `HEADER_ONLY_CANDIDATES.md`. Headline:
7 of 10 colliding layouts produce foreign VERIFIED when forced — only the
Kotak family + `sbi_txndate_...` + `canara_date_particulars_deposits_...`
headers hit own-folder exclusively and are defensible candidates; none enabled.

## Part C — parked engine items

| Item | Outcome |
|------|---------|
| KVB (~70 files) | **NO-GO** — transaction rows arrive as `(cid:NN)` glyph dumps; needs a glyph-decoding algorithm, not a spec field. `KVB_DESIGN_NOTE.md`. |
| Indian Bank L2 (45 files) | **DONE** — `clipped_drcr_suffix` + consolidated date-tail shapes; 42/45 forced VERIFIED, G3 clean, G7 clean. |
| Yes Bank wrapped `Running\|Balance` (L2) | **PARKED** — forced probe 5/21 (24%) trusted; registered L3 instead (8/9 on its sub-cluster; 13/30 = 43% corpus-wide). |
| ICICI stale-balance `Transactions List` (L3/L4, ~98 files) | DESIGN NOTE only — `ICICI_STALE_BALANCE_DESIGN_NOTE.md`; needs reversal-pair-aware check, `checks.py` untouched. |
| Kotak K8/K9, Union one-decimal, Federal F-A | no single-field solution found within timebox; remain parked. |
| CSB (18 files) | draft spec forced-probed 0/18 — parked, untracked draft removed. |

## Part D — honesty repairs

Routed re-measurement, whole folders, current code (not build/hold-out —
these banks predate the split requirement; this is the *production* truth):

| Bank | Wave-2 claim | Wave-5 routed re-measure |
|------|--------------|--------------------------|
| City Union | 31/31 + 6/6 hold-out, but detector-blocked | **37/37 VERIFIED** — detector fix unblocked routing |
| DCB | 14/15 | 14/15 (1 FAILED) — confirmed |
| APGV | 13/13 | 13 VERIFIED, 2 unrouted |
| AU SFB | 14/14 | 14 VERIFIED, 3 unrouted |
| Bandhan | 7/8 + 5/5 | **10 VERIFIED, 8 unrouted** — PARTIAL coverage, docs updated |
| Yes Bank | 13/13 hold-out (overall claim not reproduced; Yes L3 alone is 13/30 = 43% on a fresh corpus-wide sample) | 49 VERIFIED / 28 FAILED / 20 unrouted of 97 (L1+L3); L2 parked at 24% |

## Part D-bis — independent re-derivation (SIB / HSBC / PNB)

Bank-aware blind probe (`comparison/wave5/_w5_g2.py`): opening, closing,
Σdebits, Σcredits derived straight from PDF text with per-bank quirks
(SIB `dd-mm-yy` + continuation lines + per-page Page-Total skip; HSBC reverse
row order; PNB single amount+type column; right-aligned amounts via midpoint
bands; decimal-required balance cells).

| Bank | Engine-verified files | Full 4-field match |
|------|----------------------|--------------------|
| South Indian | 25 | **25/25** |
| HSBC | 21 | **21/21** |
| Punjab National | 54 | **54/54** |

## Part E — coverage round

Unresolved pools at baseline (12,249 routed records): `no_layout` 2,332,
`bank_unconfirmed` 453, `v2_failed:NO_ROWS` 61, FAILED 410.

Fingerprint clustering of the biggest onboarded-bank pools:

| Pool | Files | Largest clusters | Action |
|------|-------|------------------|--------|
| Union `no_layout` | 202 | `Tran Date|Tran Id|Remarks|Amount(Rs.)|Balance(Rs.)` ×144 | **UNION_LAYOUT_5** — forced 132/144 VERIFIED (92%), G3 770 files 0 foreign accepts (765 NO_TABLE_HEADER), G7 0 existing-layout flips; routed Union folder 519 V (+130). Committed `4183e68`. |
| ICICI `no_layout` | 543 | `Transactions List` family ×344 (parked L3/L4 — reversal-pair design note), `S.No|Txn Date|Value Date|Txn Remarks|Cheque|Withdrawal|Deposit|Balance` ×66 (two-line header: `Transaction`/`Date` split rows — needs multi-line header support; parked), misc <25 | documented |
| SBI `no_layout` | 296 | mPassbook-style `Clear Balance` pages ×~124 (no txn table on page 1-2 — needs deeper fingerprinting), `Date|Value Date|Narration|Ref/Cheque|Debit|Credit|Balance` ×17 | residual |
| Federal `no_layout` | 189 | `Money In/Money Out` app summaries ×~125 (not txn tables), F-A txn family ×36 (parked in wave 4) | residual |
| Union `v2_failed:NO_ROWS` | 31 | `s.no|date|transaction id` family where date format differs from L1/L3 | parked (needs a dash/variant date probe — recorded) |
| ICICI FAILED on `icici_date_mode_*` | 158 | schema+chain+side ×147 — the stale-balance reversal family | design note (`ICICI_STALE_BALANCE_DESIGN_NOTE.md`) |

Per the wave rules, new layouts must hold trusted ≥ previous run; L5 = 132/144
(91.7% trusted), corpus trusted stays ~93.9% (see final table).

## Final full-corpus run (production defaults)

Full corpus routed at base (`b2bb4a4`) and at the post-detector/post-IB/Yes
tree (`after_*.jsonl`); the Union-L5 delta comes from a full Union-folder
re-route (`union_routed.jsonl`, 632 files) since L5 was committed after the
corpus run started — the only folder it can touch.

| Metric | Baseline `b2bb4a4` | After detector+IB L2+Yes L3 | + Union L5 |
|--------|--------------------|----------------------------|------------|
| v2-routed | 9,182 | 9,291 | 9,433 |
| VERIFIED | 8,626 | 8,722 | 8,852 |
| FAILED | 410 | 423 | 435 |
| REVIEW | 146 | 146 | 146 |
| fallback | 3,067 | 2,958 | 2,816 |
| no_layout | 2,332 | 2,213 | ~2,068 |
| trusted (V / v2) | 93.94% | 93.88% | ~93.8% |
| wrong-bank VERIFIED | 0 | 0 | **0** |

Wrong-bank audit: 7 VERIFIED files route to a layout whose bank differs from
their folder — all 7 carry positive `bank_evidence` (`document`/`region`/
`detector`) for the layout's bank; all are misfiled statements (the file
itself prints that bank's name — e.g. an Indian Bank statement in the SBI
folder). 6/7 were identical at baseline; the 7th is the same misfiling class.
No silent accept.

Same-layout row-hash / verdict diffs across all previously-routed files: **0**
(engine changes are no-ops for existing layouts).

## Environment gaps

- `pikepdf` is absent in the local env — `test_capability_and_states.py`
  (pytest-only import) and any pikepdf-dependent suites cannot run locally;
  all runnable statement-engine extraction tests pass (169).


## Phase 7 correction: Yes Bank L3 (added during shadow-readiness fixes)
The "8/9 trusted" figure for Yes L3 was measured on the 9-file `referencenumber` sub-cluster. The layout header matches a
broader family: on a fresh corpus-wide sample it matches 30 files and verifies 13 (43.3%); the other 17 are honest FAILED
(chain/side checks), none falsely VERIFIED. The layout was **not** tightened to raise the score (that would fit the
sample, not the family). Treat Yes L3 as a low-yield, safe layout; Yes Bank statements it cannot verify fall back to the
legacy parser.
