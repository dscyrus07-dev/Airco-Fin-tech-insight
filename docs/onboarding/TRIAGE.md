# Corpus Triage - all-banks onboarding plan

Base `8b57e0d` (`integration/v2-waves`). Read-only measurement; no product code changed.
Shipped mode probed per file: `V2_MODE=shadow` + mismatch guard; then one pass with the
universal tier on for files v2 did not serve. PII-free: bank ids, counts, sha8 only.
Sample paths live in `tools/onboarding/.local/manifest*.jsonl` (gitignored).

Corpus: 15513 PDFs - 13227 text-readable, 624 scanned/no-text,
1662 locked (counted, not opened), 0 corrupt. 45 bank ids,
4 non-bank folders with files (+1 empty: Others).

## Summary (one row per bank)

| bank | folders | pdf | text | scanned | locked | fps | top-fp% | anchors% | run-bal% | det-ok% | tier (shadow) | verdicts | univ. verdicts | coverage | diff | blockers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| axis | 1 | 1144 | 1041 | 10 | 93 | 20 | 88.4 | 96.9 | 97.1 | 96.3 | fallback:68 unreadable:103 v2:973 | FAILED:17 REVIEW:188 VERIFIED:768 | FAILED:42 | banks/axis.json, extractors/axis/layout_spec.py, extractors/axis/, legacy processor | low | heavy multi-line narration; 20 layout families; multi-currency x3 |
| canara | 1 | 496 | 469 | 8 | 19 | 10 | 72.3 | 98.7 | 95.1 | 98.5 | fallback:29 unreadable:27 v2:440 | FAILED:39 REVIEW:26 VERIFIED:375 | FAILED:22 | banks/canara.json, extractors/canara/layout_spec.py, extractors/canara/, legacy processor | low | heavy multi-line narration; 10 layout families |
| paytm | 2 | 252 | 241 | 1 | 10 | 11 | 67.2 | 73.9 | 20.7 | 73.4 | fallback:77 unreadable:11 v2:164 | FAILED:4 VERIFIED:160 | FAILED:32 | banks/paytm.json, extractors/paytm/layout_spec.py, extractors/paytm/, legacy processor | low | no running balance column; 11 layout families |
| standard_chartered | 1 | 245 | 210 | 1 | 34 | 3 | 99.0 | 72.9 | 3.3 | 91.9 | fallback:28 unreadable:35 v2:182 | FAILED:24 VERIFIED:158 | FAILED:18 | banks/standard_chartered.json, extractors/scb/layout_spec.py, extractors/scb/ | low | no running balance column; multi-currency x6 |
| dbs | 1 | 137 | 131 | 4 | 2 | 3 | 91.6 | 84.0 | 91.6 | 99.2 | fallback:13 unreadable:6 v2:118 | FAILED:6 REVIEW:112 | FAILED:11 | banks/dbs.json, extractors/dbs/layout_spec.py, extractors/dbs/ | low | heavy multi-line narration; multi-currency x17 |
| citibank | 1 | 113 | 90 | 4 | 19 | 4 | 71.1 | 93.3 | 72.2 | 76.7 | fallback:26 unreadable:23 v2:64 | FAILED:1 VERIFIED:63 | FAILED:26 | banks/citibank.json, extractors/citibank/layout_spec.py, extractors/citibank/ | low | heavy multi-line narration; 4 layout families; multi-currency x6 |
| ujjivan_sfb | 1 | 39 | 39 | 0 | 0 | 4 | 74.4 | 76.9 | 79.5 | 76.9 | fallback:10 v2:29 | FAILED:5 REVIEW:24 | FAILED:9 | banks/ujjivan_sfb.json, extractors/ujjivan/layout_spec.py, extractors/ujjivan/ | low | 4 layout families |
| au_sfb | 1 | 18 | 18 | 0 | 0 | 3 | 83.3 | 94.4 | 0.0 | 94.4 | fallback:3 v2:15 | VERIFIED:15 | FAILED:3 | banks/au_sfb.json, extractors/au_sfb/layout_spec.py, extractors/au_sfb/ | low | no running balance column |
| dcb | 1 | 16 | 15 | 1 | 0 | 1 | 100.0 | 100.0 | 100.0 | 100.0 | unreadable:1 v2:15 | FAILED:8 VERIFIED:7 | - | banks/dcb.json, extractors/dcb/layout_spec.py, extractors/dcb/ | low | heavy multi-line narration |
| hdfc | 1 | 2482 | 2395 | 24 | 63 | 18 | 97.1 | 1.9 | 98.0 | 99.2 | fallback:47 unreadable:87 v2:2348 | FAILED:34 REVIEW:13 VERIFIED:2301 | FAILED:51 | banks/hdfc.json, extractors/hdfc/layout_spec.py, extractors/hdfc/, legacy processor | medium | weak balance anchors; heavy multi-line narration; 18 layout families; multi-currency x3 |
| icici | 1 | 1590 | 1439 | 31 | 120 | 23 | 42.3 | 45.3 | 58.7 | 66.3 | fallback:556 unreadable:151 v2:883 | FAILED:202 REVIEW:184 VERIFIED:497 | FAILED:691 | banks/icici.json, extractors/icici/layout_spec.py, extractors/icici/, legacy processor | medium | weak balance anchors; heavy multi-line narration; 23 layout families; multi-currency x2 |
| kotak | 2 | 1208 | 1123 | 31 | 54 | 25 | 38.3 | 55.7 | 2.7 | 69.3 | fallback:363 unreadable:85 v2:760 | FAILED:36 REVIEW:152 VERIFIED:572 | FAILED:484 | banks/kotak.json, extractors/kotak/layout_spec.py, extractors/kotak/, legacy processor | medium | no running balance column; 25 layout families; multi-currency x1 |
| union | 1 | 806 | 655 | 12 | 139 | 27 | 47.5 | 48.9 | 84.9 | 96.9 | fallback:67 unreadable:151 v2:588 | FAILED:34 REVIEW:531 VERIFIED:23 | FAILED:59 | banks/union.json, extractors/union/layout_spec.py, extractors/union/, legacy processor | medium | weak balance anchors; heavy multi-line narration; 27 layout families; multi-currency x2 |
| idfc | 1 | 380 | 348 | 7 | 25 | 11 | 55.7 | 96.0 | 82.5 | 98.3 | fallback:32 unreadable:32 v2:316 | FAILED:12 REVIEW:8 VERIFIED:296 | FAILED:44 | banks/idfc.json, extractors/idfc/layout_spec.py, extractors/idfc/, legacy processor | medium | heavy multi-line narration; 11 layout families |
| federal | 1 | 360 | 308 | 1 | 51 | 13 | 37.3 | 72.1 | 52.6 | 95.5 | fallback:114 unreadable:52 v2:194 | FAILED:13 REVIEW:37 VERIFIED:144 | FAILED:114 | banks/federal.json, extractors/federal/layout_spec.py, extractors/federal/ | medium | heavy multi-line narration; 13 layout families; non-English text present; multi-currency x3 |
| bank_of_baroda | 1 | 326 | 255 | 9 | 62 | 15 | 53.7 | 81.2 | 78.0 | 51.8 | fallback:181 unreadable:71 v2:74 | FAILED:16 VERIFIED:58 | FAILED:71 | banks/bank_of_baroda.json, extractors/bob/layout_spec.py, extractors/bob/, legacy processor | medium | 15 layout families |
| indian_bank | 1 | 185 | 166 | 5 | 14 | 8 | 51.8 | 48.2 | 3.0 | 98.8 | fallback:28 unreadable:19 v2:138 | FAILED:10 REVIEW:79 VERIFIED:49 | FAILED:47 | banks/indian_bank.json, extractors/indian_bank/layout_spec.py, extractors/indian_bank/, legacy processor | medium | weak balance anchors; no running balance column; heavy multi-line narration; 8 layout families |
| karnataka | 1 | 185 | 163 | 8 | 14 | 5 | 58.3 | 97.5 | 97.5 | 91.4 | fallback:68 unreadable:22 v2:95 | FAILED:6 VERIFIED:89 | FAILED:5 | banks/karnataka.json, extractors/karnataka/layout_spec.py, extractors/karnataka/, legacy processor | medium | heavy multi-line narration; 5 layout families |
| indusind | 1 | 154 | 148 | 3 | 3 | 9 | 37.8 | 33.1 | 36.5 | 93.2 | fallback:48 unreadable:6 v2:100 | FAILED:2 REVIEW:3 VERIFIED:95 | FAILED:62 | banks/indusind.json, extractors/indusind/layout_spec.py, extractors/indusind/ | medium | weak balance anchors; no running balance column; heavy multi-line narration; 9 layout families; multi-currency x9 |
| idbi | 1 | 119 | 109 | 6 | 4 | 13 | 31.2 | 35.8 | 29.4 | 72.5 | fallback:54 unreadable:10 v2:55 | FAILED:9 REVIEW:31 VERIFIED:15 | FAILED:63 | banks/idbi.json, extractors/idbi/layout_spec.py, extractors/idbi/ | medium | weak balance anchors; no running balance column; heavy multi-line narration; 13 layout families |
| yes | 1 | 137 | 106 | 9 | 22 | 13 | 36.8 | 51.9 | 50.0 | 85.8 | fallback:24 unreadable:31 v2:82 | FAILED:29 REVIEW:37 VERIFIED:16 | FAILED:24 | banks/yes.json, extractors/yes/layout_spec.py, extractors/yes/ | medium | heavy multi-line narration; 13 layout families; multi-currency x1 |
| pnb | 1 | 109 | 88 | 1 | 20 | 7 | 83.0 | 0.0 | 77.3 | 98.9 | fallback:31 unreadable:21 v2:57 | REVIEW:57 | FAILED:50 | banks/pnb.json, extractors/pnb/layout_spec.py, extractors/pnb/ | medium | weak balance anchors; 7 layout families |
| kvb | 1 | 89 | 79 | 7 | 3 | 3 | 94.9 | 98.7 | 8.9 | 5.1 | fallback:75 unreadable:10 v2:4 | FAILED:1 VERIFIED:3 | FAILED:73 | banks/kvb.json, extractors/kvb/layout_spec.py, extractors/kvb/ | medium | no running balance column |
| iob | 1 | 71 | 62 | 3 | 6 | 5 | 50.0 | 4.8 | 93.5 | 100.0 | fallback:4 unreadable:9 v2:58 | FAILED:3 REVIEW:55 | FAILED:4 | banks/iob.json, extractors/iob/layout_spec.py, extractors/iob/ | medium | weak balance anchors; heavy multi-line narration; 5 layout families |
| bank_of_india | 1 | 82 | 60 | 4 | 18 | 10 | 46.7 | 18.3 | 33.3 | 65.0 | fallback:60 unreadable:22 | - | FAILED:27 | banks/bank_of_india.json, legacy processor | medium | weak balance anchors; no running balance column; 10 layout families |
| central_bank | 1 | 56 | 49 | 2 | 5 | 5 | 75.5 | 14.3 | 83.7 | 89.8 | fallback:12 unreadable:7 v2:37 | FAILED:9 REVIEW:28 | FAILED:9 | banks/central_bank.json, extractors/central_bank/layout_spec.py, extractors/central_bank/ | medium | weak balance anchors; 5 layout families |
| city_union | 1 | 40 | 40 | 0 | 0 | 1 | 100.0 | 20.0 | 100.0 | 100.0 | v2:40 | REVIEW:32 VERIFIED:8 | - | banks/city_union.json, extractors/city_union/layout_spec.py, extractors/city_union/ | medium | weak balance anchors; heavy multi-line narration |
| equitas_sfb | 1 | 42 | 38 | 1 | 3 | 6 | 44.7 | 5.3 | 89.5 | 89.5 | fallback:9 unreadable:4 v2:29 | FAILED:6 REVIEW:23 | FAILED:9 | banks/equitas_sfb.json, extractors/equitas/layout_spec.py, extractors/equitas/ | medium | weak balance anchors; heavy multi-line narration; 6 layout families |
| bank_of_maharashtra | 1 | 36 | 33 | 0 | 3 | 6 | 39.4 | 78.8 | 90.9 | 100.0 | fallback:13 unreadable:3 v2:20 | REVIEW:11 VERIFIED:9 | FAILED:2 | banks/bank_of_maharashtra.json, extractors/bom/layout_spec.py, extractors/bom/ | medium | heavy multi-line narration; 6 layout families |
| bandhan | 1 | 19 | 18 | 0 | 1 | 5 | 44.4 | 66.7 | 72.2 | 94.4 | fallback:8 unreadable:1 v2:10 | REVIEW:5 VERIFIED:5 | FAILED:5 | banks/bandhan.json, extractors/bandhan/layout_spec.py, extractors/bandhan/ | medium | heavy multi-line narration; 5 layout families |
| csb | 1 | 17 | 16 | 0 | 1 | 4 | 50.0 | 100.0 | 50.0 | 18.8 | fallback:8 unreadable:1 v2:8 | REVIEW:8 | FAILED:5 | banks/csb.json | medium | heavy multi-line narration; 4 layout families |
| uco | 1 | 11 | 11 | 0 | 0 | 3 | 72.7 | 63.6 | 72.7 | 100.0 | fallback:11 | - | - | banks/uco.json | medium | - |
| airtel_pb | 1 | 7 | 7 | 0 | 0 | 3 | 57.1 | 57.1 | 57.1 | 57.1 | fallback:7 | - | FAILED:3 | banks/airtel_pb.json | medium | heavy multi-line narration |
| ippb | 1 | 6 | 6 | 0 | 0 | 2 | 83.3 | 83.3 | 83.3 | 100.0 | fallback:6 | - | FAILED:3 | banks/ippb.json | medium | multi-currency x1 |
| tmb | 1 | 2 | 2 | 0 | 0 | 1 | 100.0 | 100.0 | 100.0 | 100.0 | fallback:2 | - | - | banks/tmb.json | medium | - |
| deutsche | 1 | 2 | 2 | 0 | 0 | 1 | 100.0 | 0.0 | 100.0 | 100.0 | fallback:2 | - | FAILED:2 | banks/deutsche.json | medium | weak balance anchors; heavy multi-line narration |
| fino_pb | 1 | 1 | 1 | 0 | 0 | 1 | 100.0 | 0.0 | 100.0 | 100.0 | fallback:1 | - | - | banks/fino_pb.json | medium | weak balance anchors; heavy multi-line narration |
| sbi | 1 | 3271 | 2792 | 100 | 379 | 52 | 72.3 | 9.0 | 13.3 | 96.6 | fallback:172 unreadable:479 v2:2620 | FAILED:62 REVIEW:511 VERIFIED:2047 | FAILED:149 | banks/sbi.json, extractors/sbi/layout_spec.py, extractors/sbi/, legacy processor | high | weak balance anchors; no running balance column; 52 layout families; multi-currency x6 |
| hsbc | 1 | 103 | 37 | 66 | 0 | 4 | 67.6 | 0.0 | 67.6 | 97.3 | fallback:12 unreadable:66 v2:25 | REVIEW:25 | FAILED:14 | banks/hsbc.json, extractors/hsbc/layout_spec.py, extractors/hsbc/ | high | mostly scanned; weak balance anchors; heavy multi-line narration; 4 layout families; multi-currency x9 |
| south_indian | 1 | 33 | 29 | 1 | 3 | 1 | 100.0 | 3.4 | 0.0 | 100.0 | fallback:1 unreadable:4 v2:28 | REVIEW:28 | FAILED:1 | banks/south_indian.json, extractors/south_indian/layout_spec.py, extractors/south_indian/ | high | weak balance anchors; no running balance column; heavy multi-line narration |
| apgv | 1 | 19 | 19 | 0 | 0 | 3 | 84.2 | 10.5 | 15.8 | 84.2 | fallback:3 v2:16 | REVIEW:16 | - | extractors/apgv/layout_spec.py, extractors/apgv/ | high | weak balance anchors; no running balance column; heavy multi-line narration |
| dhanlaxmi | 1 | 15 | 15 | 0 | 0 | 3 | 53.3 | 100.0 | 46.7 | 0.0 | fallback:15 | - | FAILED:13 | none | high | no running balance column |
| fincare_sfb | 1 | 3 | 3 | 0 | 0 | 1 | 100.0 | 100.0 | 33.3 | 0.0 | fallback:3 | - | FAILED:3 | none | high | no running balance column |
| apgb | 1 | 2 | 2 | 0 | 0 | 1 | 100.0 | 0.0 | 0.0 | 0.0 | fallback:2 | - | FAILED:2 | none | high | weak balance anchors; no running balance column; heavy multi-line narration |
| cosmos | 1 | 2 | 2 | 0 | 0 | 2 | 50.0 | 0.0 | 0.0 | 0.0 | fallback:2 | - | FAILED:2 | none | high | weak balance anchors; no running balance column; non-English text present |

## Proposed onboarding order (recommendation)

1. **axis** — 1041 text, 20 fp, anchors 96.9%, det-ok 96.3%, low — layout exists, dominant fingerprint, anchored
2. **canara** — 469 text, 10 fp, anchors 98.7%, det-ok 98.5%, low — layout exists, dominant fingerprint, anchored
3. **paytm** — 241 text, 11 fp, anchors 73.9%, det-ok 73.4%, low — layout exists, dominant fingerprint, anchored
4. **standard_chartered** — 210 text, 3 fp, anchors 72.9%, det-ok 91.9%, low — layout exists, dominant fingerprint, anchored
5. **dbs** — 131 text, 3 fp, anchors 84.0%, det-ok 99.2%, low — layout exists, dominant fingerprint, anchored
6. **citibank** — 90 text, 4 fp, anchors 93.3%, det-ok 76.7%, low — layout exists, dominant fingerprint, anchored
7. **ujjivan_sfb** — 39 text, 4 fp, anchors 76.9%, det-ok 76.9%, low — layout exists, dominant fingerprint, anchored
8. **au_sfb** — 18 text, 3 fp, anchors 94.4%, det-ok 94.4%, low — layout exists, dominant fingerprint, anchored
9. **dcb** — 15 text, 1 fp, anchors 100.0%, det-ok 100.0%, low — layout exists, dominant fingerprint, anchored
10. **hdfc** — 2395 text, 18 fp, anchors 1.9%, det-ok 99.2%, medium — partial coverage or layout diversity
11. **icici** — 1439 text, 23 fp, anchors 45.3%, det-ok 66.3%, medium — partial coverage or layout diversity
12. **kotak** — 1123 text, 25 fp, anchors 55.7%, det-ok 69.3%, medium — partial coverage or layout diversity
13. **union** — 655 text, 27 fp, anchors 48.9%, det-ok 96.9%, medium — partial coverage or layout diversity
14. **idfc** — 348 text, 11 fp, anchors 96.0%, det-ok 98.3%, medium — partial coverage or layout diversity
15. **federal** — 308 text, 13 fp, anchors 72.1%, det-ok 95.5%, medium — partial coverage or layout diversity
16. **bank_of_baroda** — 255 text, 15 fp, anchors 81.2%, det-ok 51.8%, medium — partial coverage or layout diversity
17. **indian_bank** — 166 text, 8 fp, anchors 48.2%, det-ok 98.8%, medium — partial coverage or layout diversity
18. **karnataka** — 163 text, 5 fp, anchors 97.5%, det-ok 91.4%, medium — partial coverage or layout diversity
19. **indusind** — 148 text, 9 fp, anchors 33.1%, det-ok 93.2%, medium — partial coverage or layout diversity
20. **idbi** — 109 text, 13 fp, anchors 35.8%, det-ok 72.5%, medium — partial coverage or layout diversity
21. **yes** — 106 text, 13 fp, anchors 51.9%, det-ok 85.8%, medium — partial coverage or layout diversity
22. **pnb** — 88 text, 7 fp, anchors 0.0%, det-ok 98.9%, medium — partial coverage or layout diversity
23. **kvb** — 79 text, 3 fp, anchors 98.7%, det-ok 5.1%, medium — detection currently fails for most files
24. **iob** — 62 text, 5 fp, anchors 4.8%, det-ok 100.0%, medium — partial coverage or layout diversity
25. **bank_of_india** — 60 text, 10 fp, anchors 18.3%, det-ok 65.0%, medium — partial coverage or layout diversity
26. **central_bank** — 49 text, 5 fp, anchors 14.3%, det-ok 89.8%, medium — partial coverage or layout diversity
27. **city_union** — 40 text, 1 fp, anchors 20.0%, det-ok 100.0%, medium — partial coverage or layout diversity
28. **equitas_sfb** — 38 text, 6 fp, anchors 5.3%, det-ok 89.5%, medium — partial coverage or layout diversity
29. **bank_of_maharashtra** — 33 text, 6 fp, anchors 78.8%, det-ok 100.0%, medium — partial coverage or layout diversity
30. **bandhan** — 18 text, 5 fp, anchors 66.7%, det-ok 94.4%, medium — partial coverage or layout diversity
31. **csb** — 16 text, 4 fp, anchors 100.0%, det-ok 18.8%, medium — detection currently fails for most files
32. **uco** — 11 text, 3 fp, anchors 63.6%, det-ok 100.0%, medium — partial coverage or layout diversity
33. **airtel_pb** — 7 text, 3 fp, anchors 57.1%, det-ok 57.1%, medium — partial coverage or layout diversity
34. **ippb** — 6 text, 2 fp, anchors 83.3%, det-ok 100.0%, medium — partial coverage or layout diversity
35. **tmb** — 2 text, 1 fp, anchors 100.0%, det-ok 100.0%, medium — partial coverage or layout diversity
36. **deutsche** — 2 text, 1 fp, anchors 0.0%, det-ok 100.0%, medium — partial coverage or layout diversity
37. **fino_pb** — 1 text, 1 fp, anchors 0.0%, det-ok 100.0%, medium — partial coverage or layout diversity
38. **sbi** — 2792 text, 52 fp, anchors 9.0%, det-ok 96.6%, high — no printed balances - VERIFIED unreachable
39. **hsbc** — 37 text, 4 fp, anchors 0.0%, det-ok 97.3%, high — majority scanned/image-only
40. **south_indian** — 29 text, 1 fp, anchors 3.4%, det-ok 100.0%, high — no printed balances - VERIFIED unreachable
41. **apgv** — 19 text, 3 fp, anchors 10.5%, det-ok 84.2%, high — no printed balances - VERIFIED unreachable
42. **dhanlaxmi** — 15 text, 3 fp, anchors 100.0%, det-ok 0.0%, high — no detector markers/registration
43. **fincare_sfb** — 3 text, 1 fp, anchors 100.0%, det-ok 0.0%, high — no detector markers/registration
44. **apgb** — 2 text, 1 fp, anchors 0.0%, det-ok 0.0%, high — no printed balances - VERIFIED unreachable
45. **cosmos** — 2 text, 2 fp, anchors 0.0%, det-ok 0.0%, high — no printed balances - VERIFIED unreachable

## Cannot reach VERIFIED (from data)

- **apgb** — anchors 0.0%, run-bal 0.0% (no printed balances - VERIFIED unreachable)
- **apgv** — anchors 10.5%, run-bal 15.8% (no printed balances - VERIFIED unreachable)
- **cosmos** — anchors 0.0%, run-bal 0.0% (no printed balances - VERIFIED unreachable)
- **sbi** — anchors 9.0%, run-bal 13.3% (no printed balances - VERIFIED unreachable)
- **south_indian** — anchors 3.4%, run-bal 0.0% (no printed balances - VERIFIED unreachable)

## Banks detected as a different bank (surprising / review)

- **apgv** — 2 file(s) attributed to: canarax2
- **axis** — 8 file(s) attributed to: south_indianx3, unionx3, canarax1, icicix1
- **bank_of_baroda** — 2 file(s) attributed to: unionx1, deutschex1
- **canara** — 4 file(s) attributed to: central_bankx4
- **csb** — 8 file(s) attributed to: federalx8
- **hdfc** — 4 file(s) attributed to: canarax2, karnatakax1, yesx1
- **icici** — 39 file(s) attributed to: yesx19, hdfcx5, axisx4, unionx3, kotakx2, hsbcx2, idfcx2, bank_of_indiax2
- **idbi** — 1 file(s) attributed to: icicix1
- **karnataka** — 11 file(s) attributed to: ucox11
- **kotak** — 8 file(s) attributed to: unionx4, hdfcx1, central_bankx1, icicix1, canarax1
- **kvb** — 3 file(s) attributed to: canarax3
- **paytm** — 1 file(s) attributed to: unionx1
- **sbi** — 45 file(s) attributed to: rblx26, iobx9, unionx3, indian_bankx3, yesx2, indusindx1, bank_of_indiax1
- **standard_chartered** — 5 file(s) attributed to: paytmx4, karnatakax1
- **ujjivan_sfb** — 1 file(s) attributed to: idbix1
- **union** — 1 file(s) attributed to: deutschex1
- **yes** — 5 file(s) attributed to: au_sfbx4, unionx1

## What the data says about our approach

- 37 of 45 banks have >1 fingerprint — a 1–5-file sample is not
  enough alone; hold-out sets must be re-checked after onboarding.
- 6 banks have <5 usable text files: apgb(2), cosmos(2), deutsche(2), fincare_sfb(3), fino_pb(1), tmb(2)
- Hold-out sizes: median 55, largest 2787.

## Not measured / limitations

- Legacy-tier verdicts: shadow-mode routing produces no v2 verdict for fallback files;
  the legacy engine's own verdict was not re-run per file (verdict columns cover
  v2-served and universal-pass files only).
- Multi-account statements: the scan heuristic was unreliable (per-page account-label
  false positives); not reported. Needs distinct-account hashing in a later pass.
- Locked PDFs counted only; never opened.
- `detected-ok%` = share of probed text files the engine attributed to the folder's
  bank (v2 layout bank or detector-routed fallback), not a detector-only score.

## Non-bank folders

| folder | total | text | scanned | locked | detected-as | shadow tier | universal verdict |
|---|---|---|---|---|---|---|---|
| Human Verification | 60 | 60 | 0 | 0 | icici:6 karnataka:3 none:43 pnb:1 ujjivan_sfb:2 yes:5 | fallback:56 v2:4 | FAILED:40 |
| Non_Bank_Documents | 228 | 227 | 1 | 0 | axis:7 bank_of_baroda:1 citibank:4 dbs:1 hdfc:19 hsbc:1 icici:24 idfc:3 karnataka:2 kotak:5 none:140 paytm:1 sbi:6 standard_chartered:1 union:12 | fallback:210 v2:17 | FAILED:208 |
| Other_Unknown | 794 | 60 | 262 | 472 | none:60 | fallback:60 | FAILED:46 |
| Unknown | 1 | 0 | 1 | 0 | - | - | - |
