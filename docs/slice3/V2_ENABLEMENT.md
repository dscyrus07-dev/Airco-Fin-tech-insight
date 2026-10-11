# V2 enablement — candidate table (E1)

Computed from `comparison/phase8c/after_{0,1,2}.jsonl` (14,445 corpus files at
AFTER pin `89c7b21`) + `c5_forced.jsonl` (9,522 forced cross-bank outcomes over
3,148 sha-sorted files, 7 specs swept). No corpus re-run.

Thresholds: ≥30 v2 files · trusted rate over anchored ≥94% · FAILED share <5%
· wrong-bank-verified 0 · cross-bank VERIFIED 0 · detector-only banks also
need 0 foreign VERIFIED on the forced sweep.

Columns:

- `anch%` = share of v2 files with a printed independent anchor (reference check pass)
- `trust%` = VERIFIED / anchored files
- `wb` = files VERIFIED under a spec that **contradicts the detector's own
  HIGH/VERY_HIGH verdict** (the true wrong-bank-acceptance measure; files whose
  folder label disagrees but the detector agrees are misfiled real statements,
  correctly identified)
- `xb` = foreign files VERIFIED under this spec's layouts in the forced sweep
  (`n/a` = spec not covered by the sweep; corpus wb=0 is the only evidence)
- `evidence` = marker evidence class split across v2 files
  (`document`/`region` = printed marker; `detector` = detector-only)
- `legacy` = legacy processor exists; `ok` = legacy succeeded on its demo sample,
  `fails` = legacy rejected its own sample in the demo run

| spec | v2 | VER | REV | FAIL | anch% | trust% | fail% | wb | xb | evidence (v2) | legacy | eligible |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hdfc | 2309 | 2267 | 8 | 34 | 99.3 | 98.9 | 1.5 | 0 | 0 | document 1822, region 483, detector 4 | ok | **YES** |
| sbi | 2326 | 1771 | 494 | 61 | 77.8 | 97.9 | 2.6 | 0 | 0 | region 2296, document 30 | ok | **YES** |
| axis | 857 | 830 | 11 | 16 | 98.1 | 98.7 | 1.9 | 0 | 0 | document 709, detector 144, region 4 | ok | **YES** |
| idfc | 275 | 258 | 6 | 11 | 97.5 | 96.3 | 4.0 | 0 | n/a | document 265, region 9, detector 1 | ok | **YES\*** |
| paytm | 142 | 139 | 0 | 3 | 98.6 | 99.3 | 2.1 | 0 | 0 (of 866) | detector 141, document 1 | ok | **YES** (detector-only class — sweep gate met: 0 foreign VERIFIED) |
| indusind | 85 | 81 | 2 | 2 | 100.0 | 95.3 | 2.4 | 0 | n/a | region 50, document 35 | none | **BLOCKED** — E3 mutation probe: first-row amount +1 stayed VERIFIED (row 0 unconstrained: pairwise chain has no predecessor, reference check derives from balances only, totals not printed). Rows 1/5 mutations correctly FAILED. Fix belongs to checks layer (NOT-ALLOWED) → owner: Claude |
| citibank | 61 | 60 | 0 | 1 | 100.0 | 98.4 | 1.6 | 0 | n/a | region 61 | none | **YES\*** |
| city_union | 37 | 6 | 31 | 0 | 16.2 | 100.0 | 0.0 | 0 | n/a | region 37 | none | **YES\*** (all 6 anchored files VERIFIED; most files land REVIEW — honest product state) |
| icici | 849 | 480 | 173 | 196 | 74.1 | 76.3 | 23.1 | 0 | 0 | region 703, document 146 | ok | NO — trusted 76.3 < 94, fail 23.1 > 5 |
| kotak | 670 | 520 | 121 | 29 | 87.9 | 88.3 | 4.3 | 0 | 0 | document 316, region 273, detector 81 | ok | NO — trusted 88.3 < 94 |
| union | 569 | 20 | 516 | 33 | 3.5 | 100.0 | 5.8 | 0 | n/a | document 463, region 69, detector 37 | fails | NO — fail 5.8 > 5, anchored share 3.5% |
| canara | 370 | 316 | 24 | 30 | 92.7 | 92.1 | 8.1 | 0 | n/a | document 254, detector 87, region 29 | fails | NO — trusted 92.1 < 94, fail 8.1 |
| scb | 169 | 147 | 0 | 22 | 97.6 | 89.1 | 13.0 | 0 | n/a | detector 130, region 13, document 26 | none | NO — trusted 89.1 < 94, fail 13.0 |
| federal | 179 | 130 | 36 | 13 | 77.7 | 93.5 | 7.3 | 0 | 0 | region 102, document 77 | none | NO — trusted 93.5 < 94, fail 7.3 |
| indian_bank | 130 | 42 | 79 | 9 | 34.6 | 93.3 | 6.9 | 0 | n/a | document 84, region 45, detector 1 | fails | NO — trusted 93.3 < 94, fail 6.9, anchored 34.6% |
| dbs | 118 | 0 | 112 | 6 | 0.0 | n/a | 5.1 | 0 | n/a | region 118 | none | NO — 0 anchored files, fail 5.1 |
| karnataka | 93 | 88 | 0 | 5 | 96.8 | 97.8 | 5.4 | 0 | n/a | detector 93 | ok | NO — fail 5.4 > 5 (detector-only class) |
| yes | 76 | 15 | 34 | 27 | 21.1 | 93.8 | 35.5 | 0 | n/a | detector 76 | none | NO — fail 35.5, trusted 93.8 < 94 |
| bob | 72 | 56 | 0 | 16 | 83.3 | 93.3 | 22.2 | 0 | n/a | detector 48, document 24 | fails | NO — trusted 93.3 < 94, fail 22.2 |
| pnb | 56 | 0 | 56 | 0 | 0.0 | n/a | 0.0 | 0 | n/a | detector 56 | none | NO — 0 anchored |
| iob | 53 | 0 | 50 | 3 | 0.0 | n/a | 5.7 | 0 | n/a | detector 53 | none | NO — 0 anchored, fail 5.7 |
| idbi | 43 | 15 | 20 | 8 | 39.5 | 88.2 | 18.6 | 0 | n/a | document 42, region 1 | none | NO — trusted 88.2, fail 18.6 |
| equitas_sfb | 28 | 0 | 23 | 5 | 0.0 | n/a | 17.9 | 0 | n/a | detector 16, document 12 | none | NO — <30 v2, 0 anchored |
| central_bank | 28 | 0 | 24 | 4 | 0.0 | n/a | 14.3 | 0 | n/a | region 28 | none | NO — <30 v2, 0 anchored |
| south_indian | 28 | 0 | 28 | 0 | 0.0 | n/a | 0.0 | 0 | n/a | detector 28 | none | NO — <30 v2, 0 anchored |
| ujjivan_sfb | 24 | 0 | 20 | 4 | 0.0 | n/a | 16.7 | 0 | n/a | document 24 | none | NO — <30 v2 |
| hsbc | 22 | 0 | 22 | 0 | 0.0 | n/a | 0.0 | 0 | n/a | region 21, document 1 | none | NO — <30 v2 |
| bank_of_maharashtra | 17 | 8 | 9 | 0 | 47.1 | 100.0 | 0.0 | 0 | n/a | document 17 | none | NO — <30 v2 |
| dcb | 15 | 7 | 0 | 8 | 53.3 | 87.5 | 53.3 | 0 | n/a | region 15 | none | NO — <30 v2, fail 53.3 |
| au_sfb | 14 | 14 | 0 | 0 | 100.0 | 100.0 | 0.0 | 0 | n/a | region 14 | none | NO — <30 v2 |
| bandhan | 10 | 5 | 5 | 0 | 50.0 | 100.0 | 0.0 | 0 | n/a | document 10 | none | NO — <30 v2 |
| kvb | 4 | 3 | 0 | 1 | 100.0 | 75.0 | 25.0 | 0 | n/a | document 4 | none | NO — <30 v2 |

## Eligible for serving

```
STATEMENT_ENGINE_V2_MODE=serve
STATEMENT_ENGINE_V2_SERVE_BANKS=hdfc,sbi,axis,idfc,paytm,citibank,city_union
```

**indusind is excluded**: it passed every E1 threshold but failed the E3
mutation gate — see its row above. Do not allowlist it until the checks-layer
fix lands and the mutation probe is re-run.

`*` idfc, citibank, city_union were not covered by the c5 forced
cross-bank sweep — their `xb` is `n/a`, not measured-zero. Eligibility rests on
0 wrong-bank VERIFIED across the full 14,445-file corpus (the detector never
contradicted the routed spec on a VERIFIED file) plus the wave-11 E3 wrong-bank
probes (foreign file submitted under each bank), which all ended FAILED.

Wrong-bank accounting note: the earlier draft counted folder-label mismatches
and flagged SBI (1), ICICI (45), Kotak (43) etc. All of those are *detector-
agreed* routings — misfiled real statements (e.g. a real Indian Bank file in
the SBI folder, `eebb7bcd`, VERIFIED under indian_bank with all anchors
passing). With the corrected measure the corpus has **0 wrong-bank VERIFIED**
in total, matching the 8C adjudication.

## Legacy-failing named banks (prompt task)

| bank | why it stays off | what happens in product |
|---|---|---|
| Bank of Baroda (`bob`) | trusted 93.3 < 94; fail 22.2 > 5 | legacy still attempted; fails honestly today; **not** v2-served |
| Indian Bank | trusted 93.3 < 94; fail 6.9 > 5 | same |
| Canara | trusted 92.1 < 94; fail 8.1 | same |
| Union | fail 5.8 > 5; anchored share 3.5% | same |

These four banks fail the eligibility thresholds, so serving them via v2 is
not allowed by the evidence gate — improving them needs engine work (outside
this wave's scope; see NEXT CLAUDE ACTION in AGENT_STATE).
