"""verify4 mutation: brand-matched synthetic PDFs; clean + 3 tampered each.
tamper legs: (a) amount inflated -> chain/anchors break (b) date gap/invalid order
(c) running balance inconsistent. Engine must flip to REVIEW/FAILED or refuse —
never a presented-as-clean workbook.
usage: python tools/verify4/mutate4.py <out_dir>"""
import os, sys
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
out = sys.argv[1]; os.makedirs(out, exist_ok=True)

def make(path, brand_lines, header, rows):
    c = canvas.Canvas(path, pagesize=A4); c.setFont("Helvetica", 8)
    y = 800
    for line in brand_lines: c.drawString(30, y, line); y -= 13
    y -= 8
    xs = [30, 110, 250, 330, 410, 480, 550]
    for x, h in zip(xs, header): c.drawString(x, y, h)
    y -= 18
    for r in rows:
        for x, v in zip(xs, r): c.drawString(x, y, str(v))
        y -= 16
    c.showPage(); c.save()

BASE_ROWS = [
    ("05-01-2024", "NEFT SALARY ACME", "R001", "", "25000.00", "27500.00"),
    ("06-01-2024", "UPI GROCERY", "R002", "500.00", "", "27000.00"),
    ("08-01-2024", "ATM WDL", "R003", "2000.00", "", "25000.00"),
    ("10-01-2024", "NEFT REFUND", "R004", "", "1500.00", "26500.00"),
]
BANKS = {
 "dbs": (["DBS Bank India Ltd", "eStatement of Account", "IFSC: DBSS0IN0811"],
         ["Date","Transaction Description","Ref No","Withdrawal","Deposit","Balance"]),
 "federal": (["The Federal Bank Limited", "Statement of Account", "IFSC: FDRL0001234"],
         ["Txn Date","Description","Ref No","Debit","Credit","Balance"]),
 "dhanlaxmi": (["Dhanlaxmi Bank Ltd", "Account Statement", "IFSC: DLXB0001234"],
         ["Date","Particulars","Cheque No","Withdrawals","Deposits","Balance"]),
}
for bank,(brand,hdr) in BANKS.items():
    make(os.path.join(out, f"mut_{bank}_clean.pdf"), brand, hdr, BASE_ROWS)
    # (a) amount tamper: credit inflated but balance left as printed
    ra = [list(r) for r in BASE_ROWS]; ra[0][4] = "250000.00"
    make(os.path.join(out, f"mut_{bank}_amount.pdf"), brand, hdr, [tuple(r) for r in ra])
    # (b) date tamper: out-of-order/malformed sequence
    rd = [list(r) for r in BASE_ROWS]; rd[2][0] = "32-13-2024"
    make(os.path.join(out, f"mut_{bank}_date.pdf"), brand, hdr, [tuple(r) for r in rd])
    # (c) balance tamper: running balance inconsistent with dr/cr
    rb = [list(r) for r in BASE_ROWS]; rb[1][5] = "99999.99"
    make(os.path.join(out, f"mut_{bank}_balance.pdf"), brand, hdr, [tuple(r) for r in rb])
print("written", len(BANKS)*4, "pdfs ->", out)
