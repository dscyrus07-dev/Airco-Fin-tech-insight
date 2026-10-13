"""Synthetic probe PDFs (own implementation, reportlab).

Builds minimal HDFC-layout-A-shaped statements; enough geometry fidelity for
the v2 engine: header tokens give column zones, money cells right-align under
the money headers.

usage: python tools/verify/gen_probe_pdf.py <outdir>
"""
import sys, os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

W, H = A4
X = {"date": 40, "narration": 95, "ref": 265, "valuedt": 320}
XR = {"withdrawal": 430, "deposit": 495, "balance": 570}
HDR = [("date", "Date"), ("narration", "Narration"), ("ref", "Chq/RefNo."),
       ("valuedt", "Value Dt"), ("withdrawal", "Withdrawal Amt"),
       ("deposit", "Deposit Amt"), ("balance", "Closing Balance")]


def emit(c, y, col, text, right=False):
    if right:
        c.drawRightString(XR[col], y, text)
    else:
        c.drawString(X[col], y, text)


def build(path, rows, *, mention="", truncate=0, with_summary=True, closing_line=True):
    """rows: list of (date, narration, wd, dp). wd/dp are strings or ''."""
    c = canvas.Canvas(path, pagesize=A4)
    c.setFont("Helvetica", 9)
    y = H - 60
    c.drawString(40, y, "HDFC Bank Ltd Statement of Account"); y -= 14
    c.drawString(40, y, "IFSC: HDFC0001234  Branch: Test"); y -= 14
    c.drawString(40, y, "Statement From:01/04/2024To:30/04/2024"); y -= 20
    for col, t in HDR:
        emit(c, y, col, t, right=col in XR)
    y -= 14
    c.drawString(40, y, "OPENING BALANCE 10000.00"); y -= 13
    bal = 10000.0
    body = rows[:-truncate] if truncate else rows
    for d, narr, wd, dp in body:
        emit(c, y, "date", d)
        emit(c, y, "narration", narr)
        emit(c, y, "ref", "000123")
        emit(c, y, "valuedt", d)
        if wd:
            emit(c, y, "withdrawal", wd, right=True); bal -= float(wd.replace(",", ""))
        if dp:
            emit(c, y, "deposit", dp, right=True); bal += float(dp.replace(",", ""))
        emit(c, y, "balance", f"{bal:,.2f}", right=True)
        y -= 13
        if y < 80:
            c.showPage(); c.setFont("Helvetica", 9)
            for col, t in HDR:
                emit(c, H - 60, col, t, right=col in XR)
            y = H - 74
    if closing_line:
        c.drawString(40, y, f"CLOSING BALANCE {bal:,.2f}"); y -= 16
    if with_summary:
        c.drawString(40, y, "STATEMENT SUMMARY"); y -= 13
        n_dr = sum(1 for r in body if r[2]); n_cr = sum(1 for r in body if r[3])
        deb = sum(float(r[2].replace(',', '')) for r in body if r[2])
        cred = sum(float(r[3].replace(',', '')) for r in body if r[3])
        c.drawString(40, y, "Opening Balance Dr Count Cr Count Debits Credits Closing Bal"); y -= 13
        c.drawString(40, y, f"10000.00 {n_dr} {n_cr} {deb:,.2f} {cred:,.2f} {bal:,.2f}"); y -= 13
        c.drawString(40, y, "**END OF STATEMENT**")
    c.save()


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    base_rows = [(f"0{i}/04/24" if i < 10 else f"{i}/04/24", f"UPI PAYMENT REF{i}00", "100.00" if i % 2 else "", "" if i % 2 else "250.00")
                 for i in range(1, 9)]
    # clean, complete
    build(os.path.join(outdir, "probe_clean.pdf"), base_rows)
    # wrong-bank narration: narration mentions a different bank
    rows = list(base_rows)
    rows[3] = (rows[3][0], "STANDARD CHARTERED CARD PAYMENT", rows[3][2], rows[3][3])
    build(os.path.join(outdir, "probe_wrongbank_narr.pdf"), rows)
    # truncated: last rows cut, no closing anchor, no summary
    build(os.path.join(outdir, "probe_truncated.pdf"), base_rows, closing_line=False, with_summary=False)
    # summary block after transactions
    build(os.path.join(outdir, "probe_summary.pdf"), base_rows, with_summary=True)
    print("wrote 4 probes to", outdir)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tools/verify/.local/probes")
