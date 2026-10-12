# Phase 2b classification migration status

**Updated:** 2026-07-15  
**Rule:** one bank = one commit; no deletions of legacy engines until all banks green.

## Dict-table engines → JsonRuleEngine (done)

| Bank | Commit | Goldens | cat_diffs | Notes |
|------|--------|---------|-----------|-------|
| hdfc | Phase 2b HDFC | 4 | 0 | first bank; exact/pattern/upi/amount |
| axis | Phase 2b Axis | 5 | 0 | merchant_map + debit_positive |
| canara | Phase 2b Canara | 5 | 0 | debit_truthy; ATM/subscription amounts |
| icici | Phase 2b ICICI | 5 | 0 | Axis-style layers |
| kotak | Phase 2b Kotak | 5 | 0 | upi_path_merchant; 2 zero-txn goldens |
| sbi | Phase 2b SBI | 5 | 0 | post words.json merge + generic_fallback |

Shared pieces:

- `backend/scripts/dev/extract_bank_rules.py` — mechanical dump only
- `backend/app/services/pipeline/classification/rule_engine.py` — JsonRuleEngine
- Per-bank `banks/{bank}/rules.json`

## Not migrated to JsonRuleEngine (schema / architecture)

These do **not** use class-level `DEBIT_RULES`/`CREDIT_RULES` tables. Migrating them
into the same JSON schema would require inventing rules or wrapping a different
engine. Per plan: **stop and flag — do not approximate.**

| Bank | Engine shape | Action |
|------|--------------|--------|
| bank_of_baroda | GenericRuleEngine / keywords.json | Keep as-is; optional later generic→JSON |
| bank_of_india | BankOfIndiaClassifier (keywords.json) | Keep as-is |
| indian_bank | IndianBankClassifier (keywords.json) | Keep as-is |
| idfc | GenericRuleEngine wrapper | Keep as-is |
| karnataka | GenericRuleEngine wrapper | Keep as-is |
| paytm | GenericRuleEngine wrapper | Keep as-is |
| union | GenericRuleEngine wrapper | Keep as-is |
| unknown | GenericRuleEngine wrapper | Keep as-is |

## Deletion policy (end of Phase 2b)

**Do not delete** the 14 bank `rule_engine.py` / classifier modules yet.

Safe later (separate final commit, only after product sign-off):

1. All dict-table banks remain green on goldens.
2. Generic/keyword banks either stay on their classifiers **or** get an explicit
   second migration path (not inventing DEBIT_RULES).
3. Then remove dead private methods only if nothing imports them; prefer keeping
   thin wrappers forever as bank entry points.

## Coverage hygiene

- Zero-transaction goldens do not count toward coverage (Kotak effective ≈ 3).
- Phantom `hdfc/61XXXXX357` golden already removed (duplicate of Kotak sample).
