# geo_raw.py — raw word dump restricted to a header band (top range only).
# For spec authoring: column titles are bank template text (as committed in every
# layout_spec.py). NEVER point this at data rows. usage: geo_raw.py <sha8> <page> <top_from> <top_to>
import os, sys, json, glob

HERE = os.path.dirname(__file__)
manifest = {}
for f in glob.glob(os.path.join(HERE, ".local", "manifest*.jsonl")):
    for ln in open(f, encoding="utf-8"):
        try:
            j = json.loads(ln); manifest[j["sha8"]] = j["path"]
        except Exception:
            pass
sha8, page_no, t0, t1 = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
path = manifest.get(sha8)
import pdfplumber
with pdfplumber.open(path) as pdf:
    ws = pdf.pages[page_no].extract_words()
lines = {}
for wd in ws:
    if t0 <= wd["top"] <= t1:
        lines.setdefault(round(wd["top"] / 3.0), []).append(wd)
for key in sorted(lines):
    ws2 = sorted(lines[key], key=lambda w: w["x0"])
    txt = "  ".join(f"{w['text']}@{int(w['x0'])}-{int(w['x1'])}" for w in ws2)
    print(f"y={int(lines[key][0]['top'])}: " + txt.encode("ascii", "replace").decode())
