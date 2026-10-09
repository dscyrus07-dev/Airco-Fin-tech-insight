# Wave 1 — ten priority banks onboarded

Scope: the ten priority banks only; Wave 2 not started. Every bank is a
configuration-driven `LayoutSpec` in `extractors/<bank>/layout_spec.py`, registered in
`extractors/registry.py`, routed via `DETECTOR_TO_SPEC_BANK` in `v2_router.py`.
Baseline before Wave 1 (commit `29b84ce`, 14,445-file corpus): `comparison/wave1/BASELINE.md`.

## Results table

| # | Bank | Commit | Layout(s) | Build | Hold-out | G2 | G3 forced | G6 evidence |
|---|------|--------|-----------|-------|----------|----|-----------|-------------|
| 1 | DBS | `46c95f2` | `dbs_transactiondate_valuedate_detailsoftransaction_debit_credit_balance` | 66/68 | 38/46 | 12/12 | 0 foreign | `region` ×118 |
| 2 | Citibank | `2046b2b` | `citibank_date_transactiondetails_withdrawals_deposits_balance` | 36/36 | 23/24 | 12/12 | 0 foreign | `region`/`document` |
| 3 | Karur Vysya | `c611d3f` | `kvb_txn_value_brn_particulars_refno_debit_credit_balance` | 36/36 | 1/29 | 12/12 | 0 foreign | `document` |
| 4 | HSBC | `f4d5e8d` | `hsbc_date_description_credit_debit_balance` | 12/13 | 8/10 | 12/12 | 0 foreign | `region` |
| 5 | IndusInd | `b8357ec` | `indusind_date_particulars_chqrefno_withdrawl_deposit_balance` | 47/51 | 34/34 | 15/15 | 0 foreign | `region`/`document` ×81 |
| 6 | Punjab National Bank | `8b66887` | `pnb_date_instrumentid_amount_type_balance_remarks` | 33/33 | 23/23 | 15/15 | 0 foreign | `detector` ×56 |
| 7 | IDBI | `88a2c76` | `idbi_date_particulars_chqno_withdrawals_deposits_balance` + `idbi_sno_txndate_valuedate_description_chequeno_withdrawals_deposits_balance` | 20 + 12 | 8/14 + 8/8 | 15/15 ×2 | 0 foreign | `document`/`region` ×45 |
| 8 | Yes Bank | `af4b2dd` | `yes_transaction_valuedate_chequenoreferenceno_description_withdrawals_deposits_runningbalance` | 19/19 | 13/13 † | 15/15 | 0 foreign | `detector` ×54 |
| 9 | Indian Overseas Bank | `0c8aee9` | `iob_datevalue_particulars_ref_transaction_debitrs_creditrs_balancers` + `iob_date_chq_naration_cod_debit_credit_balance` | 18 + 13 | 12/12 + 9/9 | 15/15 ×2 | 0 foreign | `detector` ×53 |
| 10 | South Indian Bank | `109fd4b` | `south_indian_date_particulars_chqno_withdrawals_deposits_balance` | 14/17 | 11/12 | 15/15 | 0 foreign* | `detector` ×28 |

\* One Bank of Baroda file matches under raw forced `extract_pages` (SIB shares BoB's
fixed-pitch header), but it prints `BANKOFBARODA` so `registry.resolve()` returns
`no_layout` — production routing can never reach the SIB spec for it. Probe artifact only.

† Yes Bank 13/13 was later shown to overfit: Wave 5 re-measurement on a fresh
97-file corpus gave L1 36 VERIFIED, the new `referencenumber` variant (L3) 8/9,
and the wrapped-running-balance variant (L2) only 5/21 — L2 is defined but
parked. See `WAVE5_RESULTS.md`.

## Engine commits

| Commit | Capability |
|--------|-----------|
| `7595e68` | `side_marker_column` — standalone Dr/Cr word in a text column supplies the side of `single_amount_column` (PNB). |
| `b8c1a43` | `continuation_amounts` — money cells on a continuation line fill the row's empty money cells (SIB split rows). |

## Evidence modes

- `document`/`region` evidence: DBS, Citibank, KVB, HSBC, IndusInd, IDBI (`IDBIBANK` marker).
- `detector`-only (`bank_markers=()`, brand never prints in the text layer): PNB, Yes, IOB, SIB.
  Registry test exception `_NO_TEXT_BRAND` documents this explicitly.

## Parked / honest residuals

- **DBS**: multi-account bundles break the chain at account boundaries mid-page (capability gap); one legitimately empty statement (NO_ROWS).
- **Citibank**: 5-file `(INR)` variant omits balance on most rows — unverifiable by chain check, parked. 1 image-insert page file.
- **KVB**: transaction text arrives as CID glyph dumps — Wave 5 re-examination
  showed 19/20 sampled files DO have a ToUnicode map, but the *transaction rows*
  map to `(cid:NN)` glyphs while headers stay readable. Decoding needs per-glyph
  cmap resolution (new algorithm, not a spec field) — parked, see
  `KVB_DESIGN_NOTE.md`.
- **HSBC**: `ddMMMyyyy` sub-variant prints amounts on separate lines — falls back to legacy, parked.
- **IndusInd**: 2 files end mid-page (truncation artifact → honest FAILED), 2 REVIEW.
- **PNB**: headerless/pdfminer-broken residuals parked (`PNB_DESIGN_NOTE.md`).
- **IDBI**: L3 (`SRL|Txn Date|Value Date|…|Cr/Dr|CC|Amount INR|Balance INR`) parked — separate side-marker column shape unsupported; L1 parked sub-variant prints both money columns nonzero; 3 files have split-decimal damage.
- **Yes Bank**: B/C variants carry a third unexplained money column — ambiguous, parked (18 files route to FAILED rather than silently mis-extract).
- **IOB**: small sub-5-file clusters, pdfminer-locked, scanned/no-text.
- **SIB**: 2 REVIEW (non-monotonic dates), 1 FAILED (single damaged row missing a side).

## Tests

- `test_generic_engine.py` + `test_spec_codec.py`: 53/53 pass, including codec round-trip for all new layouts and synthetic tests for both new engine fields.
- G2 probe re-derives opening/closing/Σdebits/Σcredits independent of the engine; all banks 12/12 or 15/15 MATCH.
- G3 = each spec forced over a 774-file sample spanning every corpus folder; zero production-relevant foreign accepts.
