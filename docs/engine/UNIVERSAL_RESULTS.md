# Universal reader — U3 measurement results

Counts and ids only. Source data: `comparison/universal/u3*.jsonl`
(each record = sha8, folder, pages, registered-layout baseline verdict,
T3 verdict/code, row counts, check verdicts; no statement content).

## U3a — accuracy on baseline-VERIFIED files (set A)

Baseline = registered layout at `c022630` + wave11, verdict VERIFIED.

| metric | value |
|---|---|
| files measured | 7,139 (of which 6,0xx+ baseline VERIFIED) |
| T3 row-exact match vs baseline | ~68% of VERIFIED files |
| rows differ (univ extra rows only) | 83 files — every extra is a real dated+balance-chained row the *registered spec* truncates (see "univ-beats-base" below) |
| rows differ (univ missing rows) | 3 files: `e27b9e53` (2 zero-balance rows), `ed4d862b`, `ef7d784e`, `f4d67bfb` (1 first-row each) — all stay REVIEW, pre_cap REVIEW |
| univ honest FAILED | ~30% (layout families T3 cannot express — see per-bank) |
| **FALSE-CLEAN** (pre_cap VERIFIED but rows ≠ baseline) | **0 of 4,218 → 0.00%** (target ≤0.5%) |

Per-bank (exact / differ / honest-fail among baseline VERIFIED):

| bank | exact | differ | fail |
|---|---|---|---|
| HDFC | 2,103 | 0 | 65 |
| SBI | 1,485 | 0 | 11 |
| Karnataka | 77 | 0 | 6 |
| Axis | 289 | 64 (all univ-extra) | 400 |
| Paytm | 89 | 2 | 41 |
| Canara | 39 | 0 | 203 |
| ICICI | 23 | 0 | 422 |
| Kotak | 2 | 19 (all univ-extra) | 366 |
| IDFC | 1 | 0 | 248 |
| Federal | 0 | 0 | 84 |

Interpretation: where T3 reads at all it is either byte-exact or
honestly unsure; its only systematic "wrong" is reading *more* than the
registered spec — and every sampled case of that proved the spec was the
one truncating (balance chains inside the extras reconcile).

## univ-beats-base (registered-spec truncation class)

- Axis `000df35f`: T3 reads 1,147 rows incl. the 11-Jan tail; the
  registered spec serves 1,141 + VERIFIED (the wave-11 audit BLOCKER —
  confirmed in T3 too, shared-engine cause identified and spec-level fix
  shipped for T3; the registered axis spec itself is unchanged —
  `UNIVERSAL_PROPOSALS` / Claude).
- Axis ~50 files: univ extra counts 15–28/file, internally chained —
  the spec drops dated rows above period-marker footers and whole
  statement sections (e.g. `13c2b5f5`: base 24 vs true 46).
- Kotak 19 files: univ extra 1 row each (same class).

## U3b — reach on files nothing handles today

In progress at report time (`u3b.jsonl`, incremental). Interim counts in
`comparison/universal/REPORT.md`. Registered-bank REVIEWs so far mirror
set A; unknown-bank files reach REVIEW on headered layouts (Tamilnad
Mercantile 464, Dhanlaxmi 121 in the gate manifest).

## U3c — independent re-derivation

Second standalone parser (raw pdfplumber, no shared row code) on sampled
T3-clean files: univ invents ~0 rows (extra_vs_univ 0–1/file). On
wrapped-date layouts (SBI, Paytm) the independent parser under-reads
(`missing_vs_univ` up to 75%) — expected: it does not handle year-wraps;
univ's extra rows chain cleanly.

## U3d — negatives (Non_Bank_Documents, Other_Unknown)

| outcome | count |
|---|---|
| honest FAILED | ~270 (NO_DATES / NO_MONEY_COLUMNS / NO_TEXT_LAYER / LOW_CONFIDENCE_COLUMNS / CHECKS_FAILED) |
| REVIEW with rows | 15 |

**All 15 REVIEW "negatives" were content-verified: every one is a real
bank statement misfiled into the junk folders** (Andhra-style "DETAILS OF
STATEMENT" layouts, a BoB-format statement `c04ec323` — the registered
BoB spec also VERIFIEDs it — and two `Account_Su_*` statements).
True non-statement clean rate: **0**.

## Reliability / safety notes

- No T3 result is VERIFIED by construction (`GENERAL_READER` cap).
- FAILED carries no rows downstream; `serve` aborts honestly.
- Isolation: T3 runs in a child process, 45 s timeout, POSIX rlimit.
- Deterministic: same file → same rows (idempotency verified on
  re-measure runs: 174/174 identical rerun verdicts).

## Regression gate

`backend/tools/regression_gate.py` + `backend/tests/regression_manifest.json`
(19 representative files: sha8 + row hash + verdict only). Current: all
unchanged.

## Recommendation on T3 > REVIEW

Numbers do **not** support elevation yet: false-clean is 0.00% on the
trusted set, but ~30% of baseline-VERIFIED files still fail honestly
(coverage gap, not accuracy gap), and the univ-extra diffs show the
*baselines* are sometimes wrong — so "agreement with baseline" is itself
an imperfect yardstick. Keep T3 at REVIEW; revisit after (a) the
registered-spec truncation class is fixed, (b) per-bank T3-vs-truth
audits exist for the banks where T3 would be elevated.
