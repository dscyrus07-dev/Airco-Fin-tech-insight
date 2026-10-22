# OCR evaluation harness (synthetic scans)

Measures the T4 OCR tier against exact ground truth. **Synthetic only** - real scans are a separate run (none were
available; the corpus is never OCR'd). Reports per quality category and never lowers the gates in `scoring.GATES`.

```
python tools/ocr_eval/corpus.py --out <dir> --per-category 6          # image-only PDFs + manifest.json (ground truth)
PYTHONPATH=backend python tools/ocr_eval/run_eval.py --corpus <dir> --url http://localhost:8090 --out <dir>/report
PYTHONPATH=backend python tools/ocr_eval/run_eval.py --corpus <dir> --oracle    # self-check, no model
```
Needs numpy, opencv, Pillow, reportlab, pdfplumber (pdfium) for the corpus; the backend package for the run.
Categories: clean_200 (the 80% chain+reference gate applies here), dpi_150, dpi_300, skew, noise, blur, jpeg,
low_contrast, rotated_180. The oracle mode returns the ground truth as "perfect OCR": it validates the scorer and
the engine plumbing, and is NOT a model result.
