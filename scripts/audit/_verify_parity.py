"""Verify Phase 2 banks against HDFC reference implementation."""
import ast
import os

BASE = "backend/app/services/banks/"

KEY_METHODS = [
    "validate", "reconcile", "detect", "aggregate", "classify",
    "_validate_date", "_check_balance_progression", "_detect_patterns",
    "_agg_categories", "_agg_monthly", "_agg_weekly",
    "_aggregate_categories", "_aggregate_monthly", "_aggregate_weekly",
    "_classify_batch", "_known_pattern", "_call_api",
]

FINBIT_CHECKS = ["build_finbit_analytics", "_build_finbit", "_compute_finbit_monthly"]

PROCESSOR_CHECKS = ["ai_results", "ai_fallback", "reconcile", "detect", "aggregate"]


def get_methods(path):
    try:
        src = open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}, src
    except Exception as e:
        return set(), f"ERROR:{e}"


def check_component(bank, fname, label):
    h_methods, h_src = get_methods(BASE + "hdfc/" + fname)
    b_methods, b_src = get_methods(BASE + bank  + "/" + fname)

    if isinstance(b_src, str) and b_src.startswith("ERROR"):
        return "READ_FAIL", b_src, set(), set()

    h_key = {m for m in KEY_METHODS if m in h_methods}
    b_key = {m for m in KEY_METHODS if m in b_methods}
    # HDFC may use _aggregate_* while others use _agg_* — treat as equivalent
    b_normalized = set(b_key)
    if "_agg_categories" in b_normalized or "_aggregate_categories" in h_key:
        if "_agg_categories" in b_normalized:    b_normalized.add("_aggregate_categories")
        if "_agg_monthly" in b_normalized:       b_normalized.add("_aggregate_monthly")
        if "_agg_weekly" in b_normalized:        b_normalized.add("_aggregate_weekly")

    missing = h_key - b_normalized
    extra   = b_key - h_key
    status  = "PASS" if not missing else "FAIL"
    return status, label, missing, extra


def check_formula_excel(bank):
    path = BASE + bank + "/formula_excel_engine.py"
    try:
        src = open(path, encoding="utf-8").read()
    except Exception as e:
        return "READ_FAIL", str(e)
    results = {}
    for sym in FINBIT_CHECKS:
        results[sym] = sym in src
    # PASS if build_finbit_analytics is wired AND _build_finbit exists
    ok = results["build_finbit_analytics"] and results["_build_finbit"]
    return ("PASS" if ok else "FAIL"), results


def check_processor(bank):
    path = BASE + bank + "/processor.py"
    try:
        src = open(path, encoding="utf-8").read()
    except Exception as e:
        return "READ_FAIL", str(e)
    missing = [s for s in PROCESSOR_CHECKS if s not in src]
    return ("PASS" if not missing else "FAIL"), missing


COMPONENTS = [
    ("transaction_validator.py", "TransactionValidator"),
    ("reconciliation.py",        "Reconciliation"),
    ("recurring_engine.py",      "RecurringEngine"),
    ("aggregation_engine.py",    "AggregationEngine"),
    ("ai_fallback.py",           "AIFallback"),
]

overall_pass = 0
overall_fail = 0

for bank in ["idfc", "karnataka", "paytm", "union"]:
    sep = "=" * 62
    print(f"\n{sep}")
    print(f"  {bank.upper()} vs HDFC")
    print(sep)

    for fname, label in COMPONENTS:
        status, lbl, missing, extra = check_component(bank, fname, label)
        mark = "PASS" if status == "PASS" else "FAIL"
        line = f"  {label:28} [{mark}]"
        if missing:
            line += f"  missing={sorted(missing)}"
        print(line)
        if mark == "PASS": overall_pass += 1
        else: overall_fail += 1

    # Finbit / formula_excel_engine
    fe_status, fe_detail = check_formula_excel(bank)
    mark = fe_status
    line = f"  {'FormulaExcelEngine(Finbit)':28} [{mark}]"
    if fe_status == "FAIL":
        missing_fe = [k for k, v in fe_detail.items() if not v]
        line += f"  missing={missing_fe}"
    print(line)
    if mark == "PASS": overall_pass += 1
    else: overall_fail += 1

    # Processor
    proc_status, proc_detail = check_processor(bank)
    mark = proc_status
    line = f"  {'Processor':28} [{mark}]"
    if proc_status == "FAIL":
        line += f"  missing={proc_detail}"
    print(line)
    if mark == "PASS": overall_pass += 1
    else: overall_fail += 1

total = overall_pass + overall_fail
print(f"\n{'='*62}")
print(f"  TOTAL: {overall_pass}/{total} checks passed", end="")
if overall_fail:
    print(f"  ({overall_fail} FAILURES)", end="")
print()
print("=" * 62)
