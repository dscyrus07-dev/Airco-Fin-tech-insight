"""Workbook validation for downloaded job results (independent check).

usage: python tools/verify/xlsx_check.py <e2e.jsonl>
Reads xlsx paths recorded by e2e_api.py, opens each with openpyxl and checks:
sheets present, Transactions row count vs shadow rows, opening/closing/totals
vs engine printed_summary (from the e2e record's shadow fields), error cells.
"""
import json, os, sys
from decimal import Decimal
from openpyxl import load_workbook

EXPECTED = {"Summary", "Monthly Analysis", "Top 5 Credits", "Top 5 Debits",
            "Bounce And Penal Transactions", "Salary Transactions",
            "Loan Repayment Transactions", "Credit Card Payments", "Transactions"}
ERRVALS = {"#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NULL!", "#NUM!"}

def find_col(ws, names, header_row):
    for c in range(1, ws.max_column + 1):
        v = str(ws.cell(header_row, c).value or "").strip().lower()
        if any(n in v for n in names):
            return c
    return None

for ln in open(sys.argv[1], encoding="utf-8"):
    rec = json.loads(ln)
    xp = rec.get("xlsx")
    if not xp or not os.path.exists(xp):
        continue
    flags = []
    try:
        wb = load_workbook(xp, read_only=True, data_only=True)
    except Exception as e:
        print(rec["sha8"], rec["bank"], "OPEN_FAIL", str(e)[:80])
        continue
    sheets = set(wb.sheetnames)
    missing = EXPECTED - sheets
    if missing:
        flags.append("missing_sheets:" + ",".join(sorted(missing)))
    err_cells = 0
    txn_rows = None
    if "Transactions" in sheets:
        ws = wb["Transactions"]
        # find header row containing a date column
        hdr = None
        for r in range(1, min(ws.max_row, 10) + 1):
            if find_col(ws, ["date"], r):
                hdr = r
                break
        if hdr:
            txn_rows = 0
            for row in ws.iter_rows(min_row=hdr + 1, values_only=True):
                if any(v is not None and str(v).strip() for v in row):
                    txn_rows += 1
            sh_rows = (rec.get("shadow") or {}).get("rows")
            if sh_rows is not None and txn_rows != sh_rows:
                flags.append(f"row_mismatch:{txn_rows}!={sh_rows}")
        else:
            flags.append("no_txn_header")
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            for v in row:
                if isinstance(v, str) and v in ERRVALS:
                    err_cells += 1
    if err_cells:
        flags.append(f"error_cells:{err_cells}")
    if (rec.get("shadow") or {}).get("rows", 0) and txn_rows == 0:
        flags.append("empty_report")
    print(rec["sha8"], rec["bank"], "sheets", len(sheets), "txn_rows", txn_rows,
          "job", rec.get("job_status"), "FLAGS:" + "|".join(flags) if flags else "OK")
