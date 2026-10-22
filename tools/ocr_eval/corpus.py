"""Synthetic scan corpus with exact ground truth. No real data, no PII.

    python corpus.py --out <dir> [--per-category 6]

Each statement is drawn with reportlab (two layouts), rendered with pdfplumber/pdfium, degraded per category,
and saved as an IMAGE-ONLY PDF (no text layer). Ground truth is written next to the manifest.
Categories report separately; real scans are NOT in this corpus (none were available) and are a separate run.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import random
import zlib
from datetime import date, timedelta
from decimal import Decimal

import cv2
import numpy as np
from PIL import Image

NARR = ["UPI/SWIGGY/402911/food order", "NEFT CR ACME PAYROLL SALARY", "ATM WDL CASH 4401", "UPI/ZOMATO/883120/dinner",
        "IMPS/P2P/RAMESH/rent", "POS AMAZON RETAIL", "ACH DR LIC PREMIUM", "UPI/PHONEPE/ELECTRICITY BILL",
        "INT CREDITED", "CHQ DEP 000123", "UPI/GPAY/GROCERY/778120", "NACH DR LOAN EMI"]

# category -> (render dpi, degradation)
CATEGORIES = {
    "clean_200": (200, None), "dpi_150": (150, None), "dpi_300": (300, None),
    "skew": (200, "skew"), "noise": (200, "noise"), "blur": (200, "blur"),
    "jpeg": (200, "jpeg"), "low_contrast": (200, "low_contrast"), "rotated_180": (200, "rot180"),
}
LAYOUTS = ("split", "signed")
ROWS_PER_PAGE = 22


def indian(d: Decimal) -> str:
    s = f"{abs(d):.2f}"
    whole, frac = s.split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts + [tail])
    return f"{whole}.{frac}"


def make_rows(n: int, seed: int):
    rnd = random.Random(seed)
    bal = Decimal(rnd.randint(5, 400)) * 1000 + Decimal(rnd.randint(0, 99)) / 100
    opening, rows, d0 = bal, [], date(2026, 4, 1)
    for i in range(n):
        amt = (Decimal(rnd.choice([rnd.randint(50, 5000), rnd.randint(5000, 90000), rnd.randint(100000, 400000)]))
               + Decimal(rnd.randint(0, 99)) / 100)
        credit = rnd.random() < 0.38 or amt > bal
        bal = bal + amt if credit else bal - amt
        rows.append({"date": (d0 + timedelta(days=i)).isoformat(), "narr": rnd.choice(NARR),
                     "ref": f"R{rnd.randint(100000, 999999)}", "debit": None if credit else str(amt),
                     "credit": str(amt) if credit else None, "balance": str(bal)})
    return opening, rows


def draw_pdf(opening, rows, layout: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4
    chunks = [rows[i:i + ROWS_PER_PAGE] for i in range(0, len(rows), ROWS_PER_PAGE)]
    for pi, chunk in enumerate(chunks):
        y = H - 50
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, "SAMPLE COOPERATIVE BANK LTD"); y -= 18
        c.setFont("Helvetica", 8)
        if pi == 0:
            c.drawString(40, y, f"Statement of account from {rows[0]['date'][8:]}/{rows[0]['date'][5:7]}/2026 to "
                                f"{rows[-1]['date'][8:]}/{rows[-1]['date'][5:7]}/2026   Account No : XXXXXXXX1234"); y -= 12
            c.drawString(40, y, f"Opening Balance {indian(opening)}"); y -= 16
        else:
            y -= 10
        cols = ([("Date", 40), ("Narration", 100), ("Chq./Ref.No.", 290), ("Withdrawal Amt.", 370),
                 ("Deposit Amt.", 450), ("Closing Balance", 520)] if layout == "split" else
                [("Date", 40), ("Narration", 100), ("Chq./Ref.No.", 300), ("Amount", 400), ("Balance", 500)])
        c.setFont("Helvetica-Bold", 7.5)
        for name, x in cols:
            c.drawString(x if name in ("Date", "Narration", "Chq./Ref.No.") else x - 20, y, name)
        y -= 6; c.line(36, y, W - 30, y); y -= 12
        c.setFont("Helvetica", 7.5)
        for r in chunk:
            dd = f"{r['date'][8:]}/{r['date'][5:7]}/{r['date'][:4]}"
            c.drawString(40, y, dd); c.drawString(100, y, r["narr"]); c.drawString(300 if layout == "signed" else 290, y, r["ref"])
            if layout == "split":
                if r["debit"]: c.drawRightString(440, y, indian(Decimal(r["debit"])))
                if r["credit"]: c.drawRightString(520, y, indian(Decimal(r["credit"])))
                c.drawRightString(W - 35, y, indian(Decimal(r["balance"])))
            else:
                amt = f"-{indian(Decimal(r['debit']))}" if r["debit"] else indian(Decimal(r["credit"]))
                c.drawRightString(480, y, amt); c.drawRightString(W - 35, y, indian(Decimal(r["balance"])))
            y -= 15
        if pi == len(chunks) - 1:
            y -= 14
            dr = sum(Decimal(r["debit"]) for r in rows if r["debit"]); cr = sum(Decimal(r["credit"]) for r in rows if r["credit"])
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(40, y, f"Debits {indian(dr)}   Credits {indian(cr)}   Closing Balance {indian(Decimal(rows[-1]['balance']))}")
        c.showPage()
    c.save()
    return buf.getvalue()


def render(pdf_bytes: bytes, dpi: int):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return [p.to_image(resolution=dpi).original.convert("RGB") for p in pdf.pages]


def degrade(img: Image.Image, kind, rnd: random.Random) -> Image.Image:
    if kind is None:
        return img
    a = np.array(img)
    if kind == "skew":
        h, w = a.shape[:2]
        ang = rnd.choice([-1, 1]) * rnd.uniform(0.8, 1.6)
        m = cv2.getRotationMatrix2D((w / 2, h / 2), ang, 1.0)
        a = cv2.warpAffine(a, m, (w, h), borderValue=(255, 255, 255))
    elif kind == "noise":
        a = np.clip(a.astype(np.int16) + np.random.RandomState(rnd.randint(0, 9999)).normal(0, 14, a.shape), 0, 255).astype("uint8")
    elif kind == "blur":
        a = cv2.GaussianBlur(a, (0, 0), 1.1)
    elif kind == "jpeg":
        ok, enc = cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, 35])
        a = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    elif kind == "low_contrast":
        a = (255 - (255 - a.astype(np.float32)) * 0.5).astype("uint8")
    elif kind == "rot180":
        a = cv2.rotate(a, cv2.ROTATE_180)
    return Image.fromarray(a)


def save_image_pdf(images, path: str, dpi: int):
    images[0].save(path, "PDF", resolution=float(dpi), save_all=True, append_images=images[1:])


def build(out: str, per_category: int, rows_n: int = 40):
    os.makedirs(out, exist_ok=True)
    manifest = []
    for cat, (dpi, kind) in CATEGORIES.items():
        os.makedirs(os.path.join(out, cat), exist_ok=True)
        for k in range(per_category):
            seed = (zlib.crc32(cat.encode()) % 1000) * 100 + k
            sid = f"{cat}_{k:02d}"
            opening, rows = make_rows(rows_n, seed)
            layout = LAYOUTS[k % 2]
            imgs = [degrade(im, kind, random.Random(seed + j)) for j, im in enumerate(render(draw_pdf(opening, rows, layout), dpi))]
            path = os.path.join(out, cat, sid + ".pdf")
            save_image_pdf(imgs, path, dpi)
            manifest.append({"id": sid, "category": cat, "dpi": dpi, "layout": layout, "pages": len(imgs),
                             "pdf": os.path.join(cat, sid + ".pdf"), "opening": str(opening),
                             "rows": [{k2: r[k2] for k2 in ("date", "narr", "ref", "debit", "credit", "balance")} for r in rows]})
    with open(os.path.join(out, "manifest.json"), "w") as fh:
        json.dump({"synthetic": True, "statements": manifest}, fh)
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-category", type=int, default=6)
    ap.add_argument("--rows", type=int, default=40)
    a = ap.parse_args()
    m = build(a.out, a.per_category, a.rows)
    print(f"wrote {len(m)} synthetic image-only statements to {a.out}")
