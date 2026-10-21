# Universal OCR tier (T4): setup, flow, limits, troubleshooting

Status (2026-10-21): **implemented behind a flag, off by default. Verified only against synthetic fixtures. Never run on a real
GPU or on a real scanned statement yet.** See `UNIVERSAL_OCR_PHASE1.md` for the analysis and decisions.

## What it does
Scanned or mixed PDFs (no usable text layer) are read by PaddleOCR-VL-1.6 in a separate `ocr-service`. The OCR tables are turned
into the same word/line structure that pdfplumber produces (`statement_engine/ocr/grid.py`), so the existing universal reader,
column inference, engine and **all existing balance checks** run unchanged. PP-OCRv5 (same service) independently re-reads the
page; every printed amount must appear in its output (`ocr/verify.py`). Disagreements are flagged, never corrected.

## Policy (decided 2026-10-21)
- OCR results are **never VERIFIED**: verdict is REVIEW at best (code `OCR_READER`), `anchored=false`; the pre-cap verdict is stored.
- Pages that fail OCR or a guard (repetition loop, empty, oversized) are listed; other pages' rows are kept only if the existing
  checks do not FAIL. `OCR_PARTIAL_PAGES` is always added, and the Statement Check sheet says the workbook is incomplete.
- Text PDFs never reach OCR. With the flag off nothing OCR-related runs, not even a capability check.
- 20 MB file limit unchanged; the orchestrator now reads it from `core.config.settings` (was a duplicated constant).
- No statement is sent to a third-party OCR API. The service is internal-only.

## Configuration (environment only)
| Variable | Default | Meaning |
|---|---|---|
| `STATEMENT_ENGINE_OCR_MODE` | `off` | `off` / `shadow` (record block, serve nothing) / `serve` |
| `STATEMENT_ENGINE_OCR_URL` | unset | `http://ocr-service:8090`, or `mock:<dir>` for fixtures |
| `STATEMENT_ENGINE_OCR_MAX_PAGES` | 60 | refuse OCR above this page count |
| `STATEMENT_ENGINE_OCR_PAGE_TIMEOUT_S` | 8 | sizes the request timeout (15 s + 8 s per page) |
| `STATEMENT_ENGINE_OCR_DETECT_TIMEOUT_S` | 5 | analysis-time OCR of pages 1-2 for bank detection |
| `STATEMENT_ENGINE_OCR_LOOP_RATIO` | 4.0 | compression-ratio threshold for repetition loops |
| `STATEMENT_ENGINE_OCR_MIN_SCORE` | 0.90 | PP-OCR line score needed to confirm an amount |

## Flow
analyze: SCANNED + serve -> OCR pages 1-2 (5 s cap) -> bank detector, confidence capped at MEDIUM (user confirms); no text -> user picks bank.
process: orchestrator -> T1/T2 as today -> if file is SCANNED/MIXED and T4 serving and nothing served -> `ocr.serve.attempt` -> rows via
the same downstream steps as T3 (`unknown` processor, `V2RowSource`) -> response `statement_engine.engine == "ocr"` with an `ocr` block.
When T4 is serving and fails, the job fails with the OCR code (T3 is deliberately not tried: on MIXED files it would drop image pages silently).

## Local development without a GPU
`STATEMENT_ENGINE_OCR_URL=mock:<dir>` serves `<dir>/<sha256 of the PDF>.json` (an OcrDocument). Unknown files get `OCR_NO_FIXTURE`; nothing is fabricated.
Tests: `tests/statement_engine/ocr/` (synthetic statements in PaddleOCR-VL's output shape).

## Running the real service (needs an NVIDIA GPU >= 8 GB)
`docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.ocr.yml up --build ocr-service`, then set MODE=shadow first.
First-run checklist (not yet done): model loads once; `/health` ok; one image -> JSON; confirm `parsing_res_list` and `rec_scores` field names
in `ocr-service/app.py::_Models`; measure s/page, VRAM, repetition-loop rate.

## Known limitations
- Table text is only as good as the VLM: it can misread digits or signs. The second reader catches many, not all. Hence REVIEW-only.
- VLM block output has no per-cell coordinates or confidence; the grid adapter uses synthetic columns.
- Layouts the universal reader cannot infer (e.g. no repeated date shape, several accounts in one file) fail honestly (`NO_DATES`, `MULTI_STATEMENT`).
- Not validated on Hindi/regional-language headers, handwriting, or heavily degraded scans.
- Upside-down pages need orientation classification (enabled in the service; untested).

## Troubleshooting
| Symptom | Likely cause |
|---|---|
| Scanned file still "not supported" | `OCR_MODE` not `serve`, or `OCR_URL` unset (both are required) |
| Job fails `OCR_SERVICE_UNAVAILABLE` / `OCR_TIMEOUT` | service down / GPU busy; check `/health` |
| `OCR_REPETITION_LOOP` pages | model looped; page is excluded and listed; retry or rescan |
| Statement REVIEW with `OCR_UNCONFIRMED_AMOUNTS` | second reader disagrees with some amounts: check those rows against the PDF |

## Rollback
Set `STATEMENT_ENGINE_OCR_MODE=off`. No schema or API contract changed; the response only gains additive `ocr` keys when the tier runs.
