"""n7 mutation: tamper downloaded workbooks and show the independent validator flags it.
Two mutants per source: (a) one amount cell changed, (b) one row deleted.
Validation = tools/verify2/wb_verify.py recomputation (sheet rows, sums, chain, anchors)
against the audit jsonl produced for the same sha8.
usage: python tools/n7/mutate.py <dl_dir> <sha8,sha8,...> <audit.jsonl>
writes mutants into <dl_dir>/mut/ and prints flag comparison (counts only)."""
import json, sys, os
import openpyxl
from decimal import Decimal

dl_dir, sha8s, audit_path = sys.argv[1], sys.argv[2].split(","), sys.argv[3]
audits = {json.loads(l)["sha8"]: json.loads(l) for l in open(audit_path, encoding="utf-8")}

def num(v):
    if v is None or v == '': return None
    try: return Decimal(str(v).replace(',', '').replace('₹', '').strip())
    except Exception: return None

def measure(path):
    wb = openpyxl.load_workbook(path)
    txn = next((n for n in wb.sheetnames if n.lower() == "transactions"), None) or \
          max((n for n in wb.sheetnames if "transaction" in n.lower()),
              key=lambda n: wb[n].max_row, default=None)
    if not txn: return {"err": "no_transactions_sheet"}
    ws = wb[txn]
    rows = [[c.value for c in r] for r in ws.iter_rows(min_row=2)]
    rows = [r for r in rows if r[0] is not None]
    deb = sum(num(r[3]) or 0 for r in rows)
    cred = sum(num(r[4]) or 0 for r in rows)
    imp_open = (num(rows[-1][5]) or 0)
    first = rows[0]
    r0bal = num(first[5])
    if r0bal is not None:
        imp_open = r0bal - (num(first[4]) or 0) + (num(first[3]) or 0)
    brk = 0
    for a, b in zip(rows, rows[1:]):
        side = (num(b[4]) or 0) - (num(b[3]) or 0)
        ab, bb = num(a[5]), num(b[5])
        if ab is not None and bb is not None and abs(bb - ab - side) > Decimal('0.011'):
            brk += 1
    return {"rows": len(rows), "debits": str(deb), "credits": str(cred),
            "implied_open": str(imp_open), "close": str(num(rows[-1][5])), "chain_breaks": brk}

def flags(rec, au):
    f = []
    if not au: return ["no_audit"]
    if au.get("rows") is not None and rec.get("rows") != au["rows"]:
        f.append(f"rows {rec.get('rows')}!={au['rows']}")
    po = [Decimal(v) for v in au.get("printed_open") or []]
    pc = [Decimal(v) for v in au.get("printed_close") or []]
    if po and rec.get("implied_open") is not None:
        if not any(abs(v - Decimal(rec["implied_open"])) <= Decimal('0.011') for v in po):
            f.append("implied_open not in printed anchors")
    if pc and rec.get("close") not in (None, "None"):
        if not any(abs(v - Decimal(rec["close"])) <= Decimal('0.011') for v in pc):
            f.append("close not in printed anchors")
    if rec.get("chain_breaks"): f.append(f"chain_breaks={rec['chain_breaks']}")
    return f

out_dir = os.path.join(dl_dir, "mut"); os.makedirs(out_dir, exist_ok=True)
for s8 in sha8s:
    src = os.path.join(dl_dir, s8 + ".xlsx")
    if not os.path.exists(src):
        print(s8, "SKIP no workbook"); continue
    au = audits.get(s8)
    base = measure(src)
    print(s8, "orig:", json.dumps(flags(base, au)) or "clean")

    # mutant A: bump one amount cell (first row credit col, fallback debit)
    wb = openpyxl.load_workbook(src)
    txn = next((n for n in wb.sheetnames if n.lower() == "transactions"), None) or \
          max((n for n in wb.sheetnames if "transaction" in n.lower()),
              key=lambda n: wb[n].max_row)
    ws = wb[txn]
    from openpyxl.cell.cell import Cell
    row_m, col = 0, 0
    mid = 2 + ws.max_row // 2
    for rr in range(mid, ws.max_row + 1):
        for cc in (5, 4):
            cell = ws.cell(row=rr, column=cc)
            if isinstance(cell, Cell) and num(cell.value) not in (None, Decimal(0)):
                row_m, col = rr, cc; break
        if row_m: break
    if not row_m:
        print(s8, "amt_mut: SKIP no writable amount cell"); continue
    v = num(ws.cell(row=row_m, column=col).value)
    ws.cell(row=row_m, column=col).value = float(v + Decimal("1.00"))
    pa = os.path.join(out_dir, s8 + ".amt.xlsx"); wb.save(pa)
    print(s8, "amt_mut:", json.dumps(flags(measure(pa), au)) or "MISSED")

    # mutant B: delete row 3
    wb = openpyxl.load_workbook(src)
    ws = wb[next((n for n in wb.sheetnames if n.lower() == "transactions"), None) or max((n for n in wb.sheetnames if "transaction" in n.lower()), key=lambda n: wb[n].max_row)]
    ws.delete_rows(3, 1)
    pb = os.path.join(out_dir, s8 + ".del.xlsx"); wb.save(pb)
    print(s8, "del_mut:", json.dumps(flags(measure(pb), au)) or "MISSED")
