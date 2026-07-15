# Phase 5 reporting consolidation status

**Status:** landed (parity-preserving move)  
**Commit target:** Phase 5 FormulaExcelEngineBase → pipeline.reporting

## What was already shared (Phase 2a)

- Production free-mode path uses `LiteExcelGenerator` (9-sheet) from
  `pipeline.reporting` (shim at `banks/_shared/lite_excel_generator.py`).
- `BaseBankProcessor` primary Excel path always calls Lite first.

## Phase 5 changes

1. Moved `FormulaExcelEngineBase` implementation to
   `pipeline/reporting/formula_excel_engine.py` (Lite-only).
2. `banks/_shared/formula_excel_engine_base.py` is a re-export shim.
3. `BaseBankProcessor` imports `LiteExcelGenerator` from
   `app.services.pipeline.reporting` (not the shim path).
4. Bank `formula_excel_engine.py` wrappers unchanged (still subclass base).

## Explicitly NOT moved / deleted

| Module | Why |
|--------|-----|
| `report_generator_base.py` (~100KB) | Heavy HDFC-era 9-sheet path with classifier hooks; still referenced by bank `report_generator.py` wrappers. Moving would be a large behavioral risk without Excel golden fixtures. |
| per-bank `excel_generator.py` | Legacy openpyxl fallback only; used if Lite + formula both fail. |
| per-bank `report_generator.py` | Thin wrappers around base; keep until formula path fully drops module string. |

## Verification

- `tests/pipeline/test_lite_excel_export.py` — pass
- HDFC + Axis free-mode goldens — SNAPSHOT OK; xlsx produced non-empty
