# ICICI "Transactions List" exports (L3/L4) — stale-balance reversal pairs — DESIGN NOTE ONLY

Wave 4 parked `icici_sno_valuedate_transactiondate_chequenumber_remarks_withdrawal_deposit_balance_vd`
and `icici_sno_transactiondate_chequenumber_transactionremarks_withdrawal_deposit_balance`:
corpus trusted rate ~38–41% (vd: 13 VERIFIED / 19 FAILED of 32; transactionremarks: 25 VERIFIED /
35 FAILED / 6 REVIEW of 66). Both layouts extract cleanly; they fail `chain`/`side` because these
exports are *search-result lists*, not ledger statements: the printed "balance" column repeats a
stale balance (often the export-time balance) and periodically reprints a reversal pair — two
adjacent rows carrying the same amount on opposite sides that cancel and restore the printed
balance.

## What a reversal-pair-aware check would look like

In `checks.py` (Claude-owned — NOT touched by this wave):

1. When the balance chain breaks at row `i`, look at rows `i` and `i+1`: if they carry equal
   amounts on opposite sides **and** the printed balance after the pair equals the balance before
   it (the pair nets to zero in the chain), classify the pair as a printed reversal pair.
2. Resume chain verification after the pair; count files as VERIFIED only if the residual chain
   (excluding marked reversal pairs) is exact and every marked pair is truly self-cancelling.
3. Guard rails: a pair must be adjacent, same absolute amount, opposite printed sides, and the
   post-pair balance must equal the pre-pair balance — anything looser is a break, not a pair.

This is a *detection* of a known print defect, not a repair: rows are still printed exactly as the
bank wrote them; the check only stops treating a provably self-cancelling pair as a chain break.

## Affected volume

- `*_vd` layout: 32 files (13 VERIFIED today — those files' chains happen to stay clean).
- `*_transactionremarks` layout: 66 files.
- So at most ~73 files could move from FAILED/REVIEW to VERIFIED if the check proves every pair
  is self-cancelling; real reach is smaller — some of these exports are simply inconsistent and
  must stay FAILED.

## Why it stays a note

`checks.py` is out of scope for Devin and the two layouts stay parked: re-enabling them without a
pair-aware check would put ~50 provably-inconsistent files through REVIEW/FAILED churn for ~35%
trusted gain. If the check lands, the layouts can be re-registered and re-measured on a fresh
split.
