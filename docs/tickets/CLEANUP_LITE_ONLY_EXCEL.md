# Cleanup: Lite-only Excel + dead module removal

**Status:** landed  
**Commit target:** Lite-only Excel; delete per-bank excel/formula/report generators

## What changed

1. `BaseBankProcessor` Excel step uses **only** `LiteExcelGenerator`
   (no formula / legacy excel fallbacks).
2. All bank `processor.py` files no longer construct:
   - `excel_generator`
   - `formula_excel_engine`
3. Deleted per-bank modules (14 banks × 3):
   - `excel_generator.py`
   - `formula_excel_engine.py`
   - `report_generator.py`
4. Deleted shared shims/bases:
   - `_shared/report_generator_base.py`
   - `_shared/lite_excel_generator.py`
   - `_shared/formula_excel_engine_base.py`
5. Kept `pipeline/reporting/formula_excel_engine.py` as optional shared API
   (Lite-backed) for any external import of `FormulaExcelEngineBase`.

## Intentionally kept

| Item | Why |
|------|-----|
| `banks/*/rule_engine.py` | Rule tables / JsonRuleEngine wrappers |
| `banks/*/aggregation_engine.py` | Thin wrappers still constructed |
| `banks/*/recurring_engine.py` | Thin wrappers still constructed |
| `banks/*/reconciliation.py` | Thin wrappers still constructed |
| `generic_bank.GenericExcelGenerator` | GenericProcessor path only |
| `pipeline/reporting/*` | Live shared reporting |

## Verification

- All 14 processor keys import OK
- Pipeline unit tests green
- HDFC free-mode smoke: success, recon passed, Lite xlsx written
