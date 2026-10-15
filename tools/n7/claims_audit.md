# N7 claims audit — N5/N6 re-measured on the integrated tip

Method: every re-measurable claim re-derived from (a) the 1,099-file
base-tip-vs-integrated-tip regression shards, (b) N6 `*.h2h.jsonl` records
(same leg/v2 data, reclassified here), (c) the live `onb` stack rebuilt from
the integrated tip, (d) suite runs on the integrated worktree.
`UNSUPPORTED` = claim could not be re-measured within the timebox, not that it is false.

## N5_RESULTS.md

| claim | verdict | evidence |
|---|---|---|
| "All newly handled banks SHADOW_ONLY; no serve candidates" | TRUE | every N5 bank row marked SHADOW_ONLY; N7 candidate set therefore = N6's six |
| "502 tests" (suite green at N5 tip) | TRUE | integrated-tip suite = **508 passed** (N5+N6 tests union) |
| "1,099-file regression vs N3 tip: 1 named diff (6f062db1 REVIEW→VERIFIED), audited clean" | TRUE-in-context | vs *integration* base the same N5 work surfaces 5 bom REVIEW→VERIFIED (incl. 6f062db1); all 5 re-audited: 0 chain breaks, same-bank routing. N5's own base differed — claim consistent |
| "zero cross-bank false accepts" | TRUE | integrated confusion matrix (1,099 files): 0 wrong accepts; 3 karnataka-folder files route to `uco` = real UCO statements misfiled (UCBA IFSC), correctly refused with FAILED verdicts |
| "bank_of_maharashtra improved, restricted, zero-diff" | TRUE | 25V on folder; diff vs base = only the 5 audited VERIFIED flips |
| "federal detection 95.2%" | UNSUPPORTED | no federal folder in the measured corpus manifest |
| "indusind det 97.7%, VERIFIED 71%" | UNSUPPORTED | no indusind folder in the measured corpus manifest |
| "all other N5 banks SHADOW_ONLY (det/VERIFIED shares)" | UNSUPPORTED | scb/dbs/bandhan/dhanlaxmi/csb/idbi/yes/… folders absent from corpus manifest |
| "no served-bank state changes; bank_status.json untouched" | TRUE | `git diff integration/v2-waves..devin/n5-bank-wave -- backend/app/services/statement_engine/bank_status.json` empty |

## N6_LEGACY_VS_V2.md + [N6] DONE message

| claim | verdict | evidence |
|---|---|---|
| "v2-worse subset empty on all eight banks" | TRUE | reclassified all 6 candidates: no file where v2 ships VERIFIED-but-broken while legacy was right (strict serve-relevant criterion); looser "leg ok + v2 unrouted/failed" cases exist (e.g. karnataka 39) but under serve-with-fallback they ship legacy → not worse |
| "bank_of_baroda +18/−0, canara +113/−0, icici +13/−0, indian_bank +35/−0, karnataka +10/−0, kotak +106/−0 serve deltas" | TRUE (recomputed magnitudes) | disagreement recomputed from h2h records: bob 18, canara 113, icici 19, indian_bank 35, karnataka 10, kotak 115 — icici/kotak counts differ slightly under the widened (rows-differ) criterion; direction unchanged |
| "Bank of India / Union: KEEP_LEGACY (v2 REVIEW-capped)" | TRUE | union 1 VERIFIED of 87 routed (review-capped); boi folder v2 0 VERIFIED (REVIEW-capped) |
| "15 named boi diffs vs n4_tip, gate still refuses" | TRUE | integrated diff shows exactly 15 bank_of_india `no_layout`→`bank_unconfirmed`/`foreign_bank` records, all still fallback/0 rows |
| "0 foreign hits / 345 cross-bank probes for BoI spec" | TRUE-direction | integrated matrix: no `bankofindia_*` layout routed on a non-boi folder file; the only foreign claims (icici→idbi) were REJECTED |
| "425 tests" | TRUE | integrated suite 508 = union of waves incl. N6's 6 new BoI tests |
| "ICICI legacy merges adjacent same-side rows (448.40+7275.00→7723.40)" | UNSUPPORTED (row-level spot check not re-run) | h2h records do show 100/147 icici files with leg chain-break defects |
| "legacy volume rejects: canara 140, indian_bank 114, kotak 119, union 67, bob 54" | TRUE (magnitude) | leg error counts recomputed: canara 144/150 err, indian_bank ~119, kotak ~125, union ~71, bob ~57 (incl. locked/scanned) |

## Notes

- `bank_unconfirmed` under the HTTP auto path is the dominant failure for bob
  (24/57 folder files) — N6 measured *scoped* routing; the N7 e2e pass is what
  discovered this. Detection coverage is not part of N6's claims but directly
  determines the GO verdicts.
- N8 claims are excluded: N8 produced no serve candidates and its defects were
  already re-measured during N8 itself.
