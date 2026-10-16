"""Tamper the text layer of a real statement PDF via PyMuPDF redaction.
usage: python tools/verify4/mutate_real.py <in.pdf> <out.pdf> <kind>
kind: amount | date | balance  — changes ONE occurrence mid-document."""
import sys, re, fitz

def targets(doc, pat):
    out = []
    for pno in range(doc.page_count):
        for w in doc[pno].get_text("words"):
            if re.fullmatch(pat, w[4]):
                out.append((pno, fitz.Rect(w[:4]), w[4]))
    return out

src, dst, kind = sys.argv[1], sys.argv[2], sys.argv[3]
doc = fitz.open(src)
mid = doc.page_count // 2
if kind == "amount" or kind == "balance":
    ts = [t for t in targets(doc, r"\d{1,3}(?:,\d{3})*\.\d{2}") if t[0] >= mid] or targets(doc, r"\d{1,3}(?:,\d{3})*\.\d{2}")
    pno, rect, txt = ts[len(ts) // 2]
    a, b = txt[:-2], int(txt[-2:])
    new = a + f"{(b + 37) % 100:02d}"          # amount: change paise
elif kind == "date":
    ts = [t for t in targets(doc, r"\d{2}[/-]\d{2}[/-]\d{2,4}") if t[0] >= mid] or targets(doc, r"\d{2}[/-]\d{2}[/-]\d{2,4}")
    pno, rect, txt = ts[len(ts) // 2]
    d = int(txt[:2]); new = f"{(d % 27) + 1:02d}" + txt[2:]   # shift day
page = doc[pno]
page.add_redact_annot(rect, text=new, fontsize=max(4.0, rect.height * 0.72))
page.apply_redactions()
doc.save(dst)
print(f"{kind}: {txt} -> {new} p{pno}")
