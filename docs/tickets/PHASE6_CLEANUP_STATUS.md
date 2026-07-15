# Phase 6 cleanup status

**Status:** landed (safe cleanup only)  
**Rule:** no behavioral changes; no deletion of bank engines/rules/legacy Excel.

## Done

1. **Orchestrator table-driven registry**
   - `_PROCESSOR_IMPORTS` maps package key → `module:Class`
   - `_get_bank_processor` lazy-imports via `importlib` (same classes as before)
   - Added `kotakmahindra` alias in `SUPPORTED_BANK_PROCESSORS` (was only handled
     inside the old if-chain)

2. **Docstring** updated to mention shared `app.services.pipeline` post-parse steps

3. **`.gitignore` hygiene**
   - `.pycache_tmp/`
   - `backend/_*.py`, `backend/_reg_*.txt`, `backend/_wire_*.py` (agent scratch)

## Explicitly NOT deleted (still needed or needs product sign-off)

| Item | Why keep |
|------|----------|
| Bank `rule_engine.py` tables | Extract source for `rules.json` |
| `report_generator_base.py` | Fallback / hybrid report path |
| Per-bank `excel_generator.py` | Tertiary Excel fallback |
| Generic keyword banks | Different architecture |

## Verification

- Pipeline unit tests (lite excel, recon, json rules): green
- `_get_bank_processor` resolves all 14 processor keys
