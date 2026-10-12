# ISSUE (P1, non-blocking for V2): Incorrect `closing_balance` in legacy HDFC parser metadata

Status: OPEN, investigation only. Old parser NOT modified. Not repaired in the capture tool or comparator.

## Finding
On 8/8 captured pilot HDFC statements, `StructureValidator` metadata has `closing_balance` = the balance
*before the first transaction* (really the opening balance) and `opening_balance` = None.
Raw rows, balance chain, and the 4 golden snapshots are correct.
Source: `banks/hdfc/structure_validator.py` L318 (opening regex) / L324 (closing regex).
The parser's own `parse_result.closing_balance` (last row balance) is correct.

## Consumers (read-only trace)
| Consumer | Location | Effect of wrong value |
|---|---|---|
| Result/Excel metadata dict | `_shared/base_processor.py` L551-589 (`structure_meta_dict.get("closing_balance")` wins over aggregation) | USER-VISIBLE WRONG VALUE in `closing_balance` and `currentBalance` |
| Lite metrics account info | `pipeline/reporting/lite_metrics.py` L554 | Shows the wrong current balance |
| Verification v1 | `base_processor.py` L179-185 | Correctly flags it (FAILED on `opening_closing_check`, 8/8). Observe-only |
| Reconciliation | `base_processor.py` L163-168 -> `pipeline/reconciliation/engine.py` L114 (`del expected_closing`) | No effect; uses last row balance |
| Integrity guard | `base_processor.py` L418-425 -> `core/data_integrity_guard.py` L341-372 | No effect; infers from rows |
| Aggregation | `base_processor.py` L389-391 -> `pipeline/aggregation/engine.py` | Wrong value stored in summary opening/closing; no calculation uses it |
| Opening balance | metadata None -> `or` falls to `parse_result.opening_balance` | Correct |
| Categorization, recurring, repair | no use of these fields | none |

## Conclusion
Production calculations do not rely on the wrong field. The reported closing/current balance shown to users
(Excel/API metadata) is wrong for HDFC whenever the regex matches. P1 data-correctness defect in a
customer-facing field. Does not block V2: V2 derives closing from rows; the comparator treats old metadata as diagnostic.

## Not done (by instruction)
No change to old parser, capture tool, or comparator.

## Follow-ups (separate decision)
- Measure the rate on the full Docker corpus.
- Fix the regex (legacy behavior change) or let V2 replace it, before deleting old HDFC code.
- Check other banks using the same `or`-precedence pattern.
