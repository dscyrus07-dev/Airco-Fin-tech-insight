# OCR evaluation (SYNTHETIC scans)

| category | n | served | exact amounts | side flips | invented (chain-pass) | chain+ref pass | p95 s/page |
|---|---|---|---|---|---|---|---|
| blur | 1 | 0 | 0.00% | 0 | 0 | 0% | 6.6 |
| clean_200 | 1 | 0 | 0.00% | 0 | 0 | 0% | 22.2 |
| dpi_150 | 1 | 0 | 0.00% | 0 | 0 | 0% | 9.0 |
| dpi_300 | 1 | 0 | 0.00% | 0 | 0 | 0% | 7.0 |
| jpeg | 1 | 0 | 0.00% | 0 | 0 | 0% | 9.7 |
| low_contrast | 1 | 0 | 0.00% | 0 | 0 | 0% | 11.5 |
| noise | 1 | 0 | 0.00% | 0 | 0 | 0% | 8.4 |
| rotated_180 | 1 | 0 | 0.00% | 0 | 0 | 0% | 9.3 |
| skew | 1 | 0 | 0.00% | 0 | 0 | 0% | 6.9 |

## Not served (first 25) — code, dropped rows, and the column titles the recogniser read

| id | code | dropped | header titles |
|---|---|---|---|
| clean_200_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| dpi_150_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| dpi_300_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| skew_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| noise_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| blur_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| jpeg_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| low_contrast_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |
| rotated_180_00 | AMBIGUOUS_MONEY_COLUMNS | 0 | date:date / narration:narration / ref:chqrefno / debit:withdrawal / amount:amt / balance:c |

Targets are release gates, not proven capabilities. Passing them would not lift the REVIEW cap.
