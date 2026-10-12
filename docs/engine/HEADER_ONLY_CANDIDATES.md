# Header-Only Routing Candidates (Wave 5, Part B)

`header_only_ok` exists in `LayoutSpec` (engine commit `ca24929`, opt-in, default
`False`). When a spec sets it, `resolve()` accepts a header match with
`bank_evidence = "layout_policy"` even when no marker/detector evidence exists.

**No layout currently sets it.** This document records the safety evidence per
candidate so the flag can be enabled (or not) by decision, not silently.

## Method

1. Pool = every corpus file ending `bank_unconfirmed` or in a non-bank folder
   (667 files), plus the three known marker-silent pools: BoB (~100/248),
   KVB (~67/74), Kotak (~250/1013).
2. For each pool file, run the registered headers (`find_header` only, no
   extraction) and record which layout's header matches.
3. A layout is a candidate only if **every** header hit lands in its own
   bank's folder. Any foreign-folder hit = the header is shared or generic →
   disqualified.
4. For every colliding layout we additionally ran a **forced extraction**
   (header bypassed, spec forced) on the foreign-hit files to measure what a
   wrong header-only acceptance would do.

## Result table

| layout_id | pool hits | own-folder | foreign hits | verdict |
|---|---|---|---|---|
| kotak_date_narration_chqrefno_amountdrcr_balancecr | 205 | 205 Kotak | 0 | **candidate** |
| kvb_txn_value_brn_particulars_refno_debit_credit_balance | 67 | 67 KVB | 0 | candidate† |
| kotak_hash_transactiondate_valuedate_transactiondetails_chqrefno_debitcredit_balance | 33 | 33 Kotak | 0 | **candidate** |
| union_sno_date_transactionid_remarks_amount_balance | 13 | 0 | 6 Human-Verif, 3 Paytm, 2 Other, 1 IDBI, 1 Non-Bank | **rejected** |
| union_si_date_particulars_chqnum_withdrawal_deposit_balance | 11 | 0 | 11 Non-Bank | **rejected** |
| kotak_hash_transaction_transactiondetails_chqrefno_debit_credit_balance_signed | 9 | 9 Kotak | 0 | **candidate** |
| apgv_postdate_valuedate_narration_chequedetails_debit_credit_balance | 6 | 0 | 6 SBI | **rejected** |
| icici_sno_valuedate_transactiondate_chequenumber_remarks_withdrawal_deposit_balance | 6 | 0 | 6 Non-Bank | **rejected** |
| sbi_txndate_valuedate_description_refcheque_debit_credit_balance | 5 | 5 SBI | 0 | candidate |
| sbi_postdate_valuedate_description_cheque_debit_credit_balance | 4 | 0 | 4 Human-Verification | **rejected** |
| kotak_date_narration_chqrefno_withdrawaldr_depositcr_balance{,_ddmmmyy} | 6 | 6 Kotak | 0 | **candidate** |
| yes_transaction_valuedate_chequenoreferenceno_..._runningbalance | 3 | 1 | 2 Non-Bank | **rejected** |
| yes_transaction_valuedate_referencenumber_..._runningbalance | 3 | 1 | 2 Non-Bank | **rejected** |
| canara_date_particulars_deposits_withdrawals_balance | 2 | 2 Canara | 0 | candidate |
| bob_serial_transactiondate_valuedate_description_cheque_debit_credit_balance | 104 | 100 BoB | 4 Non-Bank | **rejected** |
| bob_date_particulars_chqno_withdrawals_deposits_balance | 2 | 0 | 2 Karnataka | **rejected** |
| idbi_date_particulars_chqno_withdrawals_deposits_balance | 2 | 0 | 2 Karnataka | **rejected** |
| south_indian_date_particulars_chqno_withdrawals_deposits_balance | 2 | 0 | 2 Karnataka | **rejected** |

† KVB header matches only its own files, but KVB transaction text arrives as
unmapped CID glyphs — extraction cannot produce rows regardless of the flag.
See `KVB_DESIGN_NOTE.md`. Header-only is moot for KVB until glyph decoding
exists.

## Wrong-accept proof (forced extraction on foreign hits)

`checks.py` verifies *internal* consistency (balance chain, side parity, schema,
totals) — not bank identity. A structurally valid statement from another bank
therefore **does verify** when the layout is forced:

| forced layout | foreign files | VERIFIED | conclusion |
|---|---|---|---|
| SBI postdate L5 | 4 Human-Verification | 4 | unsafe |
| UNION L1 (sno/transactionid) | 13 foreign | 13 fail rows — NO_ROWS | see note |
| UNION L4 (si/date/particulars) | 11 Non-Bank | 11 | unsafe |
| APGV L1 | 6 SBI | 6 | unsafe |
| ICICI L1 | 6 Non-Bank | 4 | unsafe |
| BoB L1 (serial/txn-date) | 4 Non-Bank | 4 | unsafe |
| BoB L3 (fixed-pitch) | 2 Karnataka | 0 | unsafe |
| IDBI L1 | 2 Karnataka | 2 | unsafe |
| SIB L1 | 2 Karnataka | 0 | header match insufficient to extract, still unsafe |
| YES L1 / YES L3 | 2+2 Non-Bank | 0 verified but FAILED rows produced | unsafe |

**Finding:** 7 of 10 colliding layouts produce wrong-document VERIFIED when
header-matched alone. Header-only routing on any layout with even one foreign
folder hit is therefore *provably* unsafe; only layouts with zero foreign hits
(Kotak family, `sbi_txndate_...`, `canara_date_particulars_deposits_...`) are
defensible, and only after a per-layout review of the residual risk (files of
other banks that never entered this pool could still match).

## Recommendation

- Enable `header_only_ok` only on layouts whose entire observed header-hit set
  is own-folder **and** whose recovery value is significant — the Kotak family
  (253 files) is the strongest case.
- Re-run this probe whenever a new layout is registered; a shared header token
  added later would silently invalidate the proof.
