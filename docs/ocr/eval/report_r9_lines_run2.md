# OCR evaluation (SYNTHETIC scans)

Text layer: **lines**

| category | n | served | exact amounts | side flips | invented (chain-pass) | chain+ref pass | p95 s/page |
|---|---|---|---|---|---|---|---|
| blur | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.4 |
| clean_200 | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.3 |
| dpi_150 | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.3 |
| dpi_300 | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.1 |
| jpeg | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.2 |
| low_contrast | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.4 |
| noise | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.2 |
| rotated_180 | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.5 |
| skew | 3 | 0 | 0.00% | 0 | 0 | 0% | 6.2 |

## Not served (first 25) — code, dropped rows, and the column titles the recogniser read

| id | code | dropped | header titles |
|---|---|---|---|
| clean_200_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| clean_200_01 | TOO_FEW_ROWS | 0 | date:date / narration:narration / ref:chqrefno / amount:amount / balance:balance |
| clean_200_02 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| dpi_150_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| dpi_150_01 | TOO_FEW_ROWS | 0 | date:date / narration:narration / ref:chqrefno / amount:amount / balance:balance |
| dpi_150_02 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| dpi_300_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| dpi_300_01 | TOO_FEW_ROWS | 0 | date:date / narration:narration / ref:chqrefno / amount:amount / balance:balance |
| dpi_300_02 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| skew_00 | LOW_CONFIDENCE_COLUMNS | 0 | - |
| skew_01 | LOW_CONFIDENCE_COLUMNS | 0 | - |
| skew_02 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| noise_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| noise_01 | TOO_FEW_ROWS | 0 | date:date / narration:narration / ref:chqrefno / amount:amount / balance:balance |
| noise_02 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| blur_00 | TOO_FEW_ROWS | 0 | date:date / narration:narration / amount:amt / balance:closing balance |
| blur_01 | TOO_FEW_ROWS | 0 | date:date / narration:narration / ref:chqrefno / amount:amount / balance:balance |
| blur_02 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| jpeg_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| jpeg_01 | TOO_FEW_ROWS | 0 | date:date / narration:narration / ref:chqrefno / amount:amount / balance:balance |
| jpeg_02 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| low_contrast_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| low_contrast_01 | TOO_FEW_ROWS | 0 | date:date / narration:narration / ref:chqrefno / amount:amount / balance:balance |
| low_contrast_02 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| rotated_180_00 | NO_DATES | 0 | - |

Targets are release gates, not proven capabilities. Passing them would not lift the REVIEW cap.
