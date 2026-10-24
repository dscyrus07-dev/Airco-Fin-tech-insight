# OCR evaluation (SYNTHETIC scans)

Text layer: **lines**

| category | n | served | exact amounts | side flips | invented (chain-pass) | chain+ref pass | p95 s/page |
|---|---|---|---|---|---|---|---|
| blur | 3 | 3 | 100.00% | 0 | 0 | 100% | 6.7 |
| clean_200 | 3 | 3 | 100.00% | 0 | 0 | 100% | 6.4 |
| dpi_150 | 3 | 3 | 100.00% | 0 | 0 | 100% | 6.7 |
| dpi_300 | 3 | 3 | 100.00% | 0 | 0 | 100% | 6.9 |
| jpeg | 3 | 3 | 100.00% | 0 | 0 | 100% | 6.2 |
| low_contrast | 3 | 3 | 100.00% | 0 | 0 | 100% | 6.7 |
| noise | 3 | 3 | 100.00% | 0 | 0 | 100% | 6.5 |
| rotated_180 | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.6 |
| skew | 3 | 0 | 0.00% | 0 | 0 | 0% | 8.7 |

## Not served (first 25) — code, dropped rows, and the column titles the recogniser read

| id | code | dropped | header titles |
|---|---|---|---|
| skew_00 | LOW_CONFIDENCE_COLUMNS | 0 | - |
| skew_01 | LOW_CONFIDENCE_COLUMNS | 0 | - |
| skew_02 | LOW_CONFIDENCE_COLUMNS | 0 | - |
| rotated_180_00 | NO_DATES | 0 | - |
| rotated_180_01 | NO_DATES | 0 | - |
| rotated_180_02 | NO_DATES | 0 | - |

Targets are release gates, not proven capabilities. Passing them would not lift the REVIEW cap.
