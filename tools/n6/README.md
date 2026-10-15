# tools/n6 — legacy-vs-v2 head-to-head (Track B, `devin/n6-legacy-vs-v2`)

Independent of the N1–N5 engine branches: based on `integration/v2-waves`
(tip `5be615d`, contains `411f6ca`). Read-only on the corpus; all output is
PII-free (sha8, counts, verdicts, flags — no text, names, amounts in records).

## Files

- `sample.py` — page-1 header fingerprints per bank, stratified seeded sample
  (seed 29, ≤150 files). Writes `.local/<bank>.fp.jsonl` + `<bank>.sample.txt`.
- `head2head.py` — per file: (a) legacy leg using the bank processor's own
  `pdf_validator → structure_validator → parser → transaction_validator` then
  `DataIntegrityGuard(strict_mode=False)` — the same non-strict mode
  `pipeline_orchestrator` uses in production, so guard failures surface as
  flags on shipped workbooks, not exceptions; (b) v2 leg via
  `route_pdf(bank_key=…)` — scoped to the bank's own specs, the path `serve.py`
  uses for an allowlisted bank; (c) spec-independent audit applied to BOTH row
  sets: dated amount-lines vs rows, forward balance chain recomputed, implied
  first/last balance vs printed anchors (generic label scan).
  Writes `.local/<bank>.h2h.jsonl`, resumable.
- `report.py` — quadrant table (both_right / legacy_right_v2_not /
  v2_right_legacy_not / both_wrong_or_none), legacy-defect classification by
  cause+sha8, and the decide_serve simulation (v2 output iff VERIFIED else
  legacy) giving the serve-Δ counts.
- `redate.py` — one-off recompute of `dated_amt_lines` + `rows_gt_dated_lines`
  on existing records after the DATE/AMT_LINE heuristic was widened
  (serial-glued dates, `(Cr)`-suffixed amounts).

## Definitions

- `leg right`: parsed rows > 0, independent chain recompute clean, row count
  consistent with dated amount-lines (cross-validated by v2 VERIFIED on the
  undated/glued-date families), no failed `DataIntegrityGuard` checks —
  production's non-strict mode ships a workbook even when guard checks fail,
  so a failed check here is a customer-facing defect.
- `v2 right`: routed `v2`, verdict VERIFIED, independent chain clean.
- Generic-scan flags (`open/close_anchor_mismatch`, `rows_gt_dated_lines`) on
  VERIFIED files are auditor precision limits, not engine defects — verified
  mechanisms: empty `--` balance cells (BoB), FD/TDS sub-summary "Closing
  Balance" lines (ICICI), serial-glued dates (union), glued txn/value date
  pairs (indian_bank), `(Cr)`-suffixed amount cells (kotak).

## Reproduce

```
python tools/n6/sample.py backend <bank> 8
python tools/n6/head2head.py backend <bank>
python tools/n6/report.py <bank>
```

Banks: icici kotak union canara bank_of_baroda indian_bank karnataka
bank_of_india.
