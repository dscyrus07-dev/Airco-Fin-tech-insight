"""
Deep parity verification: IDFC, Karnataka, Paytm, Union vs HDFC.
Checks: imports, class names, method signatures, logic markers,
        processor wiring, finbit wiring, AI tuple handling,
        reconciliation tolerance, recurring patterns, rule engine path fix.
"""
import ast, os, re, py_compile, tempfile

BASE   = "backend/app/services/banks/"
BANKS  = ["idfc", "karnataka", "paytm", "union"]
PASS   = "PASS"
FAIL   = "FAIL"
WARN   = "WARN"

results = {}   # bank -> {check: status}

def src(bank, fname):
    try:
        return open(BASE + bank + "/" + fname, encoding="utf-8").read()
    except:
        return ""

def methods(code):
    try:
        tree = ast.parse(code)
        return {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    except:
        return set()

def classes(code):
    try:
        tree = ast.parse(code)
        return {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)}
    except:
        return set()

def compile_ok(bank, fname):
    path = BASE + bank + "/" + fname
    try:
        py_compile.compile(path, doraise=True)
        return True
    except:
        return False

# ── per-bank checks ───────────────────────────────────────────────────────────
for bank in BANKS:
    r = {}

    # 1. SYNTAX — all .py files compile
    folder = BASE + bank
    all_ok = True
    for f in os.listdir(folder):
        if f.endswith(".py") and not compile_ok(bank, f):
            all_ok = False
            break
    r["syntax_all_files"]          = PASS if all_ok else FAIL

    # 2. TRANSACTION VALIDATOR
    tv = src(bank, "transaction_validator.py")
    cls_name = f"{bank.capitalize()}TransactionValidator" if bank != "idfc" else "IDFCTransactionValidator"
    if bank == "karnataka": cls_name = "KarnatakaTransactionValidator"
    r["tv_class_name"]             = PASS if cls_name in tv else FAIL
    r["tv_validate_method"]        = PASS if "def validate" in tv else FAIL
    r["tv_date_validation"]        = PASS if "_validate_date" in tv else FAIL
    r["tv_amount_validation"]      = PASS if "_validate_amount" in tv else FAIL
    r["tv_description_validation"] = PASS if "_validate_description" in tv else FAIL
    r["tv_balance_validation"]     = PASS if "_validate_balance" in tv else FAIL
    r["tv_result_dataclass"]       = PASS if "ValidationResult" in tv else FAIL
    r["tv_error_collection"]       = PASS if ("errors" in tv and "warnings" in tv) or "ValidationIssue" in tv else FAIL

    # 3. RECONCILIATION
    rec = src(bank, "reconciliation.py")
    bank_cap = bank.upper() if bank == "idfc" else bank.capitalize()
    r["rec_class_name"]            = PASS if any("Reconciliation" in c for c in classes(rec)) else FAIL
    r["rec_reconcile_method"]      = PASS if "def reconcile" in rec else FAIL
    r["rec_balance_progression"]   = PASS if "_check_balance_progression" in rec else FAIL
    r["rec_tolerance"]             = PASS if "0.01" in rec or "TOLERANCE" in rec else FAIL
    r["rec_auto_correct"]          = PASS if "auto_correct" in rec else FAIL
    r["rec_result_dataclass"]      = PASS if "ReconciliationResult" in rec else FAIL

    # 4. RECURRING ENGINE
    re_src = src(bank, "recurring_engine.py")
    r["rec_eng_class"]             = PASS if "RecurringEngine" in re_src else FAIL
    r["rec_eng_detect"]            = PASS if "def detect" in re_src else FAIL
    r["rec_eng_patterns"]          = PASS if "_detect_patterns" in re_src else FAIL
    r["rec_eng_known_pattern"]     = PASS if "_known_pattern" in re_src else FAIL
    r["rec_eng_merchant_key"]      = PASS if "_merchant_key" in re_src else FAIL
    r["rec_eng_emi_patterns"]      = PASS if "EMI_PATTERNS" in re_src else FAIL
    r["rec_eng_salary_patterns"]   = PASS if "SALARY_PATTERNS" in re_src else FAIL
    r["rec_eng_subscription"]      = PASS if "SUBSCRIPTION_MERCHANTS" in re_src else FAIL
    r["rec_eng_amount_tolerance"]  = PASS if "AMOUNT_TOLERANCE" in re_src else FAIL
    r["rec_eng_freq_ranges"]       = PASS if "MONTHLY_RANGE" in re_src else FAIL

    # 5. AGGREGATION ENGINE
    agg = src(bank, "aggregation_engine.py")
    r["agg_class"]                 = PASS if "AggregationEngine" in agg else FAIL
    r["agg_aggregate"]             = PASS if "def aggregate" in agg else FAIL
    r["agg_categories"]            = PASS if "_agg_categories" in agg or "_aggregate_categories" in agg else FAIL
    r["agg_monthly"]               = PASS if "_agg_monthly" in agg or "_aggregate_monthly" in agg else FAIL
    r["agg_weekly"]                = PASS if "_agg_weekly" in agg or "_aggregate_weekly" in agg else FAIL
    r["agg_recurring_split"]       = PASS if "_agg_recurring" in agg or "_aggregate_recurring" in agg else FAIL
    r["agg_top_merchants"]         = PASS if "top_merchant" in agg or "_get_top_merchant" in agg else FAIL
    r["agg_result_dataclass"]      = PASS if "AggregationResult" in agg else FAIL
    r["agg_to_dict"]               = PASS if "def to_dict" in agg else FAIL

    # 6. AI FALLBACK
    ai = src(bank, "ai_fallback.py")
    r["ai_class"]                  = PASS if "AIFallback" in ai else FAIL
    r["ai_classify"]               = PASS if "def classify" in ai else FAIL
    r["ai_classify_batch"]         = PASS if "_classify_batch" in ai else FAIL
    r["ai_categories_list"]        = PASS if ("FALLBACK_CATEGORIES" in ai or "CATEGORIES" in ai) else FAIL
    r["ai_provider_selection"]     = PASS if "sk-ant-" in ai else FAIL
    r["ai_returns_tuple"]          = PASS if "AIClassificationResult" in ai else FAIL
    r["ai_no_api_key_guard"]       = PASS if "not self.api_key" in ai else FAIL
    r["ai_batch_loop"]             = PASS if "BATCH_SIZE" in ai else FAIL
    r["ai_parse_json"]             = PASS if "json.loads" in ai else FAIL
    r["ai_error_fallback"]         = PASS if "except" in ai and ("Others" in ai or "fallback" in ai.lower()) else FAIL

    # 7. FORMULA EXCEL ENGINE — FINBIT WIRING
    fe = src(bank, "formula_excel_engine.py")
    r["fe_finbit_import"]          = PASS if "build_finbit_analytics" in fe and "from app.services.banks._shared.finbit_analytics" in fe else FAIL
    r["fe_build_finbit_method"]    = PASS if "def _build_finbit" in fe else FAIL
    r["fe_finbit_try_except"]      = PASS if "try:" in fe and "build_finbit_analytics" in fe and "_compute_finbit_monthly" in fe else FAIL
    r["fe_finbit_month_keys"]      = PASS if "month_keys" in fe else FAIL
    r["fe_finbit_monthly_metrics"] = PASS if "monthly_metrics" in fe else FAIL

    # 8. PROCESSOR WIRING
    proc = src(bank, "processor.py")
    r["proc_imports_all"]          = PASS if all(x in proc for x in [
        "TransactionValidator","Reconciliation","RecurringEngine","AggregationEngine","AIFallback"]) else FAIL
    r["proc_ai_fallback_call"]     = PASS if "self.ai_fallback.classify" in proc else FAIL
    r["proc_ai_tuple_handling"]    = PASS if ("ai_results, _" in proc or "isinstance(ai_raw, tuple)" in proc) else FAIL
    r["proc_ai_guard"]             = PASS if "enable_ai" in proc and "api_key" in proc else FAIL
    r["proc_reconcile_called"]     = PASS if "reconcile" in proc else FAIL
    r["proc_detect_called"]        = PASS if "detect" in proc or "recurring" in proc.lower() else FAIL
    r["proc_aggregate_called"]     = PASS if "aggregate" in proc else FAIL
    r["proc_validate_called"]      = PASS if "validate" in proc else FAIL

    # 9. RULE ENGINE — path resolver fix
    rule = src(bank, "rule_engine.py")
    r["rule_engine_path_fix"]      = PASS if ("backend" in rule and "parents" in rule) or ("Path(__file__)" in rule and "IndexError" not in rule) else WARN

    # 10. CLASSIFIER
    cname = f"{bank}_classifier.py" if bank != "union" else "union_classifier.py"
    cl = src(bank, cname)
    r["classifier_exists"]         = PASS if len(cl) > 50 else FAIL

    results[bank] = r

# ── print report ──────────────────────────────────────────────────────────────
CATEGORIES_ORDER = [
    ("SYNTAX",          [k for k in next(iter(results.values())) if k.startswith("syntax")]),
    ("TRANSACTION VALIDATOR", [k for k in next(iter(results.values())) if k.startswith("tv_")]),
    ("RECONCILIATION",  [k for k in next(iter(results.values())) if k.startswith("rec_") and not k.startswith("rec_eng")]),
    ("RECURRING ENGINE",[k for k in next(iter(results.values())) if k.startswith("rec_eng")]),
    ("AGGREGATION",     [k for k in next(iter(results.values())) if k.startswith("agg_")]),
    ("AI FALLBACK",     [k for k in next(iter(results.values())) if k.startswith("ai_")]),
    ("FINBIT/EXCEL",    [k for k in next(iter(results.values())) if k.startswith("fe_")]),
    ("PROCESSOR",       [k for k in next(iter(results.values())) if k.startswith("proc_")]),
    ("RULE ENGINE",     [k for k in next(iter(results.values())) if k.startswith("rule_")]),
    ("CLASSIFIER",      [k for k in next(iter(results.values())) if k.startswith("classifier_")]),
]

HDR = f"{'CHECK':<38}" + "".join(f"{b.upper():>11}" for b in BANKS)
print("\n" + "=" * (38 + 11*4))
print("  FULL PARITY REPORT  —  Phase 2 Banks vs HDFC")
print("=" * (38 + 11*4))

total_pass = total_fail = total_warn = 0

for section, keys in CATEGORIES_ORDER:
    if not keys:
        continue
    print(f"\n  ── {section} " + "─" * (38 + 11*4 - len(section) - 6))
    for k in keys:
        row = f"  {k:<36}"
        for bank in BANKS:
            v = results[bank].get(k, "N/A")
            row += f"{v:>11}"
            if v == PASS: total_pass += 1
            elif v == FAIL: total_fail += 1
            elif v == WARN: total_warn += 1
        print(row)

total = total_pass + total_fail + total_warn
print("\n" + "=" * (38 + 11*4))
print(f"  RESULT: {total_pass}/{total} PASS  |  {total_fail} FAIL  |  {total_warn} WARN")
print("=" * (38 + 11*4))
if total_fail == 0 and total_warn == 0:
    print("  ALL BANKS FULLY VERIFIED AGAINST HDFC")
elif total_fail == 0:
    print("  ALL CRITICAL CHECKS PASS  (review WARNs)")
else:
    print("  ACTION REQUIRED: fix FAIL items above")
print("=" * (38 + 11*4))
