"""N9 demo kit: fully synthetic statement PDFs, one per served bank's main spec.

No real customer data anywhere: holder "Test Holder", fake account/IFSC numbers,
arithmetic-consistent dated rows with running balance, opening/closing anchors
where the spec declares them. Iterated locally against route_pdf until each
file's verdict matches the bank's expected serve semantics (VERIFIED-capable or
REVIEW for review-only banks).
usage: python tools/final/gen_demo_pdfs.py <backend_dir> <out_dir>
"""
import os, re, sys, json
import pikepdf
from pikepdf import Name, Dictionary, Array

backend, OUT = sys.argv[1], sys.argv[2]
sys.path.insert(0, backend)
os.makedirs(OUT, exist_ok=True)
os.environ.setdefault("STATEMENT_ENGINE_V2_MODE", "serve")

from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY as REG
from app.services.statement_engine.v2_router import route_pdf

SERVED = "hdfc,sbi,axis,idfc,paytm,citibank,city_union,au_sfb,bank_of_maharashtra,airtel_pb,iob,apgv,south_indian,pnb,bob,canara,icici,indian_bank,karnataka,kotak".split(",")

# bank display text + ifsc for detection evidence (header text only, never narration)
BANK_TXT = {
 "hdfc": ("HDFC BANK LTD", "HDFC0001234"), "sbi": ("STATE BANK OF INDIA", "SBIN0012345"),
 "axis": ("AXIS BANK LTD", "UTIB0001234"), "idfc": ("IDFC FIRST BANK", "IDFB0012345"),
 "paytm": ("PAYTM PAYMENTS BANK", "PYTM0123456"), "citibank": ("CITIBANK N A", "CITI0012345"),
 "city_union": ("CITY UNION BANK LTD", "CIUB0001234"), "au_sfb": ("AU SMALL FINANCE BANK", "AUBL0001234"),
 "bank_of_maharashtra": ("BANK OF MAHARASHTRA", "MAHB0001234"), "airtel_pb": ("AIRTEL PAYMENTS BANK", "AIRP0012345"),
 "iob": ("INDIAN OVERSEAS BANK", "IOBA0001234"), "apgv": ("AP GRAMEENA VIKAS BANK", "APGV0001234"),
 "south_indian": ("SOUTH INDIAN BANK LTD", "SIBL0001234"), "pnb": ("PUNJAB NATIONAL BANK", "PUNB0012345"),
 "bob": ("BANK OF BARODA", "BARB0012345"), "canara": ("CANARA BANK", "CNRB0001234"),
 "icici": ("ICICI BANK LTD", "ICIC0001234"), "indian_bank": ("INDIAN BANK", "IDIB0012345"),
 "karnataka": ("KARNATAKA BANK LTD", "KARB0001234"), "kotak": ("KOTAK MAHINDRA BANK", "KKBK0001234"),
}

def esc(s): return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

def build_pdf(lines, path, pw=None):
    pdf = pikepdf.new()
    font = pdf.make_indirect(Dictionary(Type=Name.Font, Subtype=Name.Type1, BaseFont=Name.Helvetica))
    y = 780
    ops = []
    for row in lines:
        for x, text in row:
            if text:
                ops.append(f"BT /F1 9 Tf {x} {y} Td ({esc(text)}) Tj ET")
        y -= 12
        if y < 40:
            break
    content = pdf.make_stream("\n".join(ops).encode("latin-1"))
    page = pdf.make_indirect(Dictionary(
        Type=Name.Page, MediaBox=Array([0, 0, 595, 842]),
        Resources=Dictionary(Font=Dictionary(F1=font)), Contents=content))
    pdf.pages.append(pikepdf.Page(page))
    kwargs = {}
    if pw:
        kwargs["encryption"] = pikepdf.Encryption(user=pw, owner="owner", R=6)
    pdf.save(path, **kwargs)

# ---- generic single-page statement in the spec's column order ----
def synth_lines(spec, bank):
    cols = spec.columns or {}
    # canonical column sequence: date,narration then the amount columns in spec order
    order = [k for k in cols.keys()]
    head_names = {k: (" ".join(cols[k][0]) if cols[k] and cols[k][0] else k) for k in order}
    btxt, ifsc = BANK_TXT.get(bank, (bank.upper(), "XXXX0001234"))
    lines = []
    lines.append([(55, btxt + "  Statement of Account")])
    lines.append([(55, "IFSC: " + ifsc + "  A/c: 123456789012  Test Holder")])
    lines.append([(55, "Statement for the period 01-Jan-2024 to 31-Jan-2024")])
    WIDE = {"narration", "particulars", "description", "remarks", "transaction",
            "transactiondetails", "descriptionnarration", "remitter"}
    # spread non-wide columns 55..540; wide cols get a narration slot at 120
    xmap = {}
    x = 55.0
    for k in order:
        xmap[k] = x
        title_w = max(len(t) for t in head_names[k].split()) if head_names[k] else len(k)
        # 9pt Helvetica ~4.7pt/char; narration/data columns need room for the longest cell too
        need = max(title_w * 6.0 + 22, 170.0 if k in WIDE or "narrat" in k or "descrip" in k or "particular" in k or "remark" in k or "details" in k else 78.0)
        x += need
    hdr = [(xmap[k], head_names[k]) for k in order]
    lines.append(hdr)
    # opening anchor: emit text shaped to the spec's own regex where it has one
    bal = 10000.00
    o_pat = (spec.opening_balance_re.pattern if spec.opening_balance_re else "") or ""
    if o_pat:
        if o_pat.startswith("B/F") or "b/f" in o_pat.lower():
            lines.append([(55, f"B/F {bal:,.2f} (Cr)")])
        elif "ason" in o_pat.replace(" ", ""):
            lines.append([(55, f"Balance as on 01-Jan-2024 : {bal:,.2f}")])
        elif "as(?:of|on)" in o_pat:
            lines.append([(55, f"Opening Balance as on 01-01-2024 {bal:,.2f}")])
        elif "INR" in o_pat:
            lines.append([(55, f"Opening Balance - INR {bal:,.2f}")])
        else:
            lines.append([(55, "Opening Balance"), (490, f"{bal:,.2f}")])
    dfmt = spec.date_format or "%d/%m/%Y"
    import datetime
    d = datetime.date(2024, 1, 2)
    rows = []
    for i in range(12):
        amt = 100.00 * (i % 4 + 1)
        is_dr = (i % 3 == 0)
        bal = bal - amt if is_dr else bal + amt
        ds = d.strftime(dfmt)
        row = []
        for k in order:
            x = xmap[k]
            kl = k.lower()
            if k in ("date", "txn_date", "transdate", "postdate", "transactiondate") or kl.endswith("date"):
                row.append((x, ds))
            elif k in WIDE or "narrat" in kl or "descrip" in kl or "particular" in kl or "remark" in kl or "details" in kl or "transaction" == kl or "type" in kl or "mode" in kl:
                row.append((x, f"UPI/TEST{i:03d}/REF{i:06d}"))
            elif kl in ("debit", "withdrawal", "withdrawals", "withdraws", "withdrawaldr", "dr"):
                row.append((x, f"{amt:,.2f}" if is_dr else ""))
            elif kl in ("credit", "deposit", "deposits", "depositcr", "cr", "amountinr"):
                row.append((x, "" if is_dr else f"{amt:,.2f}"))
            elif kl in ("amount", "amount_dr", "amount_cr", "txn_amount"):
                row.append((x, f"{amt:,.2f} {'Dr' if is_dr else 'Cr'}"))
            elif kl in ("type", "drcr", "side"):
                row.append((x, "Dr" if is_dr else "Cr"))
            elif "balance" in kl or "closingbalance" in kl or "available" in kl:
                row.append((x, f"{bal:,.2f}"))
            elif kl in ("srno", "sno", "slno", "hash", "serial"):
                row.append((x, str(i + 1)))
            elif "branch" in kl or "cod" == kl:
                row.append((x, "0123"))
            elif "chq" in kl or "cheque" in kl or "ref" in kl or "instrument" in kl:
                row.append((x, f"{100000 + i}"))
            elif "value" in kl:
                row.append((x, ds))
            else:
                row.append((x, "-"))
        lines.append([c for c in row if c[1]])
        d += datetime.timedelta(days=2)
    c_pat = (spec.closing_balance_re.pattern if spec.closing_balance_re else "") or ""
    if c_pat:
        if "\\(Cr\\)" in c_pat or "(Cr)" in c_pat:
            lines.append([(55, f"Closing Balance {bal:,.2f} (Cr)")])
        elif "INR" in c_pat:
            lines.append([(55, f"Closing Balance - INR {bal:,.2f}")])
        else:
            lines.append([(55, "Closing Balance"), (490, f"{bal:,.2f}")])
    for m in (spec.end_markers or ()):
        lines.append([(55, m.title().replace("Of", "of"))])
        break
    return lines

def main():
    specs = []
    try:
        specs = list(REG.specs())
    except Exception:
        specs = list(getattr(REG, "_specs", getattr(REG, "specs", [])))
    by_bank = {}
    for s in specs:
        by_bank.setdefault(getattr(s, "bank_key", ""), []).append(s)
    results = {}
    for bank in SERVED:
        cand = by_bank.get(bank) or []
        # prefer anchor-bearing specs (VERIFIED-capable); keep registry order otherwise
        cand = sorted(cand, key=lambda s: 0 if getattr(s, "opening_balance_re", None) else 1)
        spec = cand[0] if cand else None
        path = os.path.join(OUT, f"demo_{bank}.pdf")
        if spec is None:
            # no spec: generic statement (will route legacy/fallback honestly)
            build_pdf(synth_lines(_Dummy(), bank), path)
            results[bank] = {"file": path, "spec": None}
            continue
        best = None
        tmp = os.path.join(OUT, f".try_{bank}.pdf")
        for s in cand[:4]:
            try:
                lines = synth_lines(s, bank)
                build_pdf(lines, tmp)
                r = route_pdf(tmp, registry=REG)
                res = r.result
                v = getattr(res, "verification_status", None) or getattr(res, "verdict", None)
                st = getattr(r, "status", None)
                rec = {"file": path, "spec": s.layout_id, "verdict": v, "status": st,
                        "rows": len(getattr(res, "transactions", []) or []),
                        "warnings": (getattr(res, "warnings", []) or [])[:3],
                        "fallback_reason": getattr(r, "fallback_reason", None)}
                score = {"VERIFIED": 3, "REVIEW": 2}.get(v, 1 if st == "v2" else 0)
                if best is None or score > best[0]:
                    best = (score, rec, tmp)
                if v == "VERIFIED":
                    break
            except Exception as e:
                if best is None:
                    best = (0, {"file": path, "spec": getattr(s, "layout_id", "?"), "error": str(e)[:120]}, None)
        if best and best[2]:
            import shutil; shutil.copyfile(best[2], path)
            best = best[1]
        elif best:
            best = best[1]
        results[bank] = best or {}
        print(bank, "->", json.dumps(best or {})[:160])
    json.dump(results, open(os.path.join(OUT, "gen_results.json"), "w"), indent=1)

class _Dummy:
    columns = {"date": (("date",),), "narration": (("particulars",),),
               "debit": (("debit",),), "credit": (("credit",),), "balance": (("balance",),)}
    opening_balance_re = re.compile("x"); closing_balance_re = re.compile("x")
    date_format = "%d/%m/%Y"; end_markers = ()

main()
