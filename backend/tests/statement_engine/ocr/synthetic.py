"""Synthetic, PII-free statements in the shape PaddleOCR-VL returns (layout blocks + HTML table)."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from app.services.statement_engine.ocr.contracts import OcrBlock, OcrDocument, OcrLine, OcrPage

NARRATIONS = [
    "UPI/SWIGGY/402911/food order", "NEFT CR ACME PAYROLL SALARY", "ATM WDL CASH 4401",
    "UPI/ZOMATO/883120/dinner", "IMPS/P2P/RAMESH/rent", "POS AMAZON RETAIL", "ACH DR LIC PREMIUM",
    "UPI/PHONEPE/ELECTRICITY BILL", "INT CREDITED", "CHQ DEP 000123",
]


def make_rows(n: int = 24, opening: Decimal = Decimal("25000.00"), start: date = date(2026, 4, 1),
              seed: int = 3) -> List[Dict]:
    rows, bal = [], opening
    for i in range(n):
        amt = Decimal(((i * 7919 + seed * 104729) % 900000) / 100 + 10).quantize(Decimal("0.01"))
        credit = (i + seed) % 4 == 1
        if not credit and amt > bal:
            credit = True
        bal = bal + amt if credit else bal - amt
        rows.append({"date": start + timedelta(days=i), "narr": NARRATIONS[(i + seed) % len(NARRATIONS)],
                     "ref": f"R{100000 + i * 37}", "dr": None if credit else amt, "cr": amt if credit else None,
                     "bal": bal})
    return rows


def _fmt(d: Optional[Decimal]) -> str:
    return "" if d is None else f"{d:,.2f}"


def table_html(rows: List[Dict], header: bool = True,
               columns: Tuple[str, ...] = ("Date", "Narration", "Chq./Ref.No.", "Withdrawal Amt.", "Deposit Amt.", "Closing Balance"),
               single_signed: bool = False) -> str:
    out = ["<table>"]
    if header:
        out.append("<tr>" + "".join(f"<th>{c}</th>" for c in columns) + "</tr>")
    for r in rows:
        d = r["date"].strftime("%d/%m/%Y")
        if single_signed:
            amt = f"-{_fmt(r['dr'])}" if r["dr"] is not None else _fmt(r["cr"])
            cells = [d, r["narr"], r["ref"], amt, _fmt(r["bal"])]
        else:
            cells = [d, r["narr"], r["ref"], _fmt(r["dr"]), _fmt(r["cr"]), _fmt(r["bal"])]
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    out.append("</table>")
    return "".join(out)


def make_document(n_rows: int = 24, per_page: int = 12, opening: Decimal = Decimal("25000.00"),
                  summary: bool = True, header_every_page: bool = True, with_lines: bool = True,
                  seed: int = 3) -> Tuple[OcrDocument, List[Dict]]:
    rows = make_rows(n_rows, opening, seed=seed)
    pages: List[OcrPage] = []
    chunks = [rows[i:i + per_page] for i in range(0, len(rows), per_page)]
    for pi, chunk in enumerate(chunks):
        blocks = []
        if pi == 0:
            blocks.append(OcrBlock("header", [40, 30, 900, 60], "SAMPLE COOPERATIVE BANK LTD"))
            blocks.append(OcrBlock("text", [40, 70, 900, 120],
                                   f"Statement of account from {rows[0]['date']:%d/%m/%Y} to {rows[-1]['date']:%d/%m/%Y}\nAccount No : XXXXXXXX1234"))
        blocks.append(OcrBlock("table", [40, 140, 1600, 1900], table_html(chunk, header=header_every_page or pi == 0)))
        if summary and pi == len(chunks) - 1:
            dr = sum((r["dr"] or 0) for r in rows)
            cr = sum((r["cr"] or 0) for r in rows)
            blocks.append(OcrBlock("text", [40, 1950, 1600, 2050],
                                   f"Opening Balance {_fmt(opening)}\nDebits {_fmt(Decimal(dr))}\nCredits {_fmt(Decimal(cr))}\nClosing Balance {_fmt(rows[-1]['bal'])}"))
        lines = []
        if with_lines:
            for r in chunk:
                for v in (r["dr"], r["cr"], r["bal"]):
                    if v is not None:
                        lines.append(OcrLine(_fmt(v), [0, 0, 10, 10], 0.99))
        pages.append(OcrPage(page=pi + 1, width=1654, height=2339, blocks=blocks, lines=lines, elapsed_s=1.9))
    return OcrDocument(pages=pages, engine="PaddleOCR-VL-1.6", verifier="PP-OCRv5" if with_lines else "", dpi=200), rows
