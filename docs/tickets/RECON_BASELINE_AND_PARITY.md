# Reconciliation baseline & Phase 3 parity notes

**Status:** Phase 3 shared core landed; **RECON-HIGH-MISMATCH accuracy fix landed** (goldens recaptured)  
**Created:** Phase 0 golden capture (2026-07-15)  
**Accuracy fix:** 2026-07-15 (user-approved)

## Phase 3 shared reconciler (landed)

- Core: `backend/app/services/pipeline/reconciliation/engine.py`
- Bank wrappers under `banks/*/reconciliation.py`
- Wired full-grade banks; GenericReconciliation banks still thin wrappers where applicable

## RECON-HIGH-MISMATCH — root cause & fix

### Findings

1. **Parse amount/side errors** dominate (not true statement gaps):
   debit/credit often wrong side or wrong amount vs balance column.
2. **`auto_correct_debit_credit` existed but was never called** in the pipeline.
3. **Classification reordered rows** (`classified + unclassified`), which
   undid any balance-side repairs and re-broke progression for goldens.

### Fix (behavioral, goldens recaptured)

1. `repair_transaction_sides()` — swap when helpful, else set amount from
   balance delta (`prev → bal`).
2. Wire repair in `BaseBankProcessor` STEP 5 **before** `reconcile()`.
3. **Restore statement order** after classification (free + hybrid) so
   repaired debit/credit stay aligned with running balances.

### Results (free-mode goldens, non-zero txn samples)

| Bank | Before (worst sample mismatches) | After (all samples) |
|------|----------------------------------|---------------------|
| axis | 138 | **0** |
| hdfc | 120 | **0** |
| icici | 124 | **0** |
| canara | 44 | **0** |
| sbi | 13 | **0** |
| kotak | 11 | **0** |

All banks with non-zero golden samples: **max mismatch_count = 0**.

Note: `is_reconciled` may still be false if opening/closing header totals
disagree with repaired amounts (final_difference), while **row progression
mismatches are 0**.

## Golden hygiene

- Zero-txn goldens do not count toward coverage.
- Duplicate `61XXXXX357` HDFC golden removed earlier (Kotak sample misfiled).
