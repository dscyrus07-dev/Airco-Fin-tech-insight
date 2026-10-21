# Universal OCR Parser: Phase 1 analysis and plan

Status: **analysis and proposal only. Nothing is implemented.** Prepared on 2026-10-21 against `integration/v2-waves` @ `830d161`.
Every file and function named below was read in the repository. Any figure not measured here says where it came from.

---

## Part A: What the current system does

### A1. Processing flow (as it runs today)

```
Upload (UI / API)
  └─ /statements/analyze  ─ analysis_service.py
       ├─ size cap (MAX_FILE_SIZE_MB=20, core/config.py) and page cap (MAX_PDF_PAGES=500, rate_limit.py)
       ├─ capability.check_pdf()           → TEXT | MIXED | SCANNED | LOCKED | UNREADABLE
       ├─ analyzer.analyze_text_pages()    → detector.detect_bank() (IFSC, header name, domain, running header…)
       ├─ layouts.detect_layout()          (TEXT/MIXED only)
       └─ analyzer.decide_state()          SCANNED → UNSUPPORTED_SCANNED_PDF (blocked)
  └─ confirm → RabbitMQ → event_consumer._handle_file_uploaded → pipeline_orchestrator.process_statement()
       ├─ input validation (20 MB, .pdf)
       ├─ T1  v2 engine     serve.route_for_serve → v2_router → extraction.engine.extract_pages(pages, LayoutSpec)
       │                    → checks.run_checks → VERIFIED | REVIEW | FAILED   (flag STATEMENT_ENGINE_V2_MODE)
       ├─ T2  legacy parser banks/<bank>/parser.py (pdfplumber; returns SCANNED_PDF on no text)
       ├─ T3  universal reader  universal.reader.read() in a child process (isolated.py, 45 s, 1.5 GB)
       │                    infers a runtime LayoutSpec, runs the same engine + checks, verdict capped at REVIEW
       │                    (flag STATEMENT_ENGINE_UNIVERSAL_MODE=off|shadow|serve)
       └─ downstream (shared): _run_pipeline(row_source=V2RowSource) → reconcile → classify (rules.json, words.json,
          AI fallback) → Excel (14 sheets + Statement Check sheet) → history / audit / 7-day retention
```

### A2. The key interface: words with coordinates

All text-based extraction, bank-specific (T1) and universal (T3), runs on one pure data contract:

- `extraction/words.py`: `Word(text, x0, x1, top, bottom)`
- `extraction/rows.py`: `Page(words: List[Word], width)`
- `extraction/pdf_extractor.read_pages()` is the **only** place a PDF library makes these (pdfplumber `extract_words`).
- `universal/reader.read(..., pages=None)` **already accepts pre-built pages** instead of a PDF path.
- `extraction/engine.extract_pages(pages, spec)` is equally PDF-free.

So any OCR engine that can produce `Page`/`Word` lists plugs into the existing engine, the inference and every check without changing them. This is the most important finding for the design.

### A3. Bank detection and routing

- `statement_engine/detector.py` scores document evidence (`EvidenceKind`: IFSC, header name, running header, domain…). Filename, metadata and user hints are supporting evidence only. Output: `DetectionResult` with a `Confidence` (rule-based, not a probability).
- `statement_engine/registry.py` and `bank_status.py` hold the support states shown in the UI (verified / review_required / legacy / coming_soon / unsupported). The UI reads these from the catalog API, and the OCR work must not change them.
- `serve.decide_serve` picks v2 or legacy per bank. `_get_bank_processor` maps the bank key to the legacy class. Manual bank selection reaches the same path through `bank_key`.

### A4. Transaction schema actually used

- Engine level: `extraction/normalize.NormalizedRow { txn: NormalizedTransaction, page, printed_side, reversal, row_warnings, printed_kind, segment }`. Page provenance already exists per row.
- Hand-off to downstream: `serve.V2RowSource { transactions[dict], opening_balance, closing_balance, total_debits, total_credits, dr_count, cr_count, statement_from, statement_to, account_number, ifsc }`. T1 review rows and T3 already use this, and OCR should too. **No new schema is needed.**
- Debit/credit: a separate debit and credit column, a single signed column (`single_amount_column` + `derive_side_from_balance`), and DR/CR suffixes (`_merge_drcr_suffix`) are all supported by `LayoutSpec`.
- Currency is implicitly INR. There is no currency field.

### A5. Validation (strong, and reusable as is)

`extraction/checks.run_checks` → `decide()`:

| Check | What it proves |
|---|---|
| `chain` / `side` | every row: prev balance ± amount = printed balance; the side agrees with the balance movement |
| `reference` | derived opening/closing = printed summary |
| `totals` | sum and count of debits/credits = printed totals |
| `checkpoints` | in-table printed balances (carried forward / brought forward) |
| `segments` | per-account transaction counts |
| `dates`, `date_outliers`, `period` | monotonic dates, outliers, rows inside the printed period |
| `schema` | rows that could not be normalized |
| `balance_delta` | balance-less layouts: closing − opening = net |

- Verdicts: **VERIFIED** (all pass with an independent anchor), **REVIEW** (no anchor, or warnings), **FAILED** (any hard failure). REVIEW without an independent anchor is already enforced ("balance chain is self-derived").
- `engine._unread_transaction_lines` counts dated lines that never became rows, which catches silently dropped rows.
- `serve.apply_row_count_guard` compares the engine's row count with the workbook's.
- These map directly onto the outcomes the brief asks for: validated = VERIFIED, warnings/manual review = REVIEW, failed = FAILED. "Partially processed" is not a separate state today; see F4.

### A6. Infrastructure

- FastAPI (`uvicorn`, `UVICORN_WORKERS`) and a RabbitMQ consumer (`event_consumer.py`) run `process_statement` asynchronously, with a Redis job store and progress.
- Docker: `infra/docker/docker-compose*.yml`. The backend image is `python:3.11-slim`, CPU only. **No compose file defines a GPU device.** The EC2 compose splits file/pdf/ai/report services.
- Tests: 84 backend test files (`tests/`, `tests/golden`, `tests/banks`, `tests/statement_engine`), plus vitest on the frontend.

---

## Part B: OCR models in the repository

**No OCR model is selected, configured or integrated anywhere in the repository.**

- `requirements.txt` has no OCR dependency (only pdfplumber, pymupdf, pikepdf, pypdf).
- `contracts.py` and `capability.py` say so explicitly: *"Text layer only. There is no OCR and none is planned."*
- Mentions of "OCR" elsewhere are in docs that note its absence.

The only selection is the one you made in conversation on 2026-10-21: **PaddleOCR-VL-1.6**. The table below records what is known about it, with sources. Nothing here has been measured on AirCo statements yet.

| Question | PaddleOCR-VL-1.6 | Source |
|---|---|---|
| What it does | Two-stage document parser: PP-DocLayoutV2 layout detection plus reading order, then a 0.9B VLM (NaViT encoder + ERNIE-4.5-0.3B) reads each region | PaddleOCR-VL paper (arXiv 2510.14528) |
| Scans, images, tables, multi-page | Yes. It is reported state of the art on Real5 (scan, warp, screen photo, lighting, skew); tables come out as HTML; `restructure_pages(merge_tables=True)` merges tables across pages | paddleocr.ai VL-1.5/1.6 pages |
| OCR only or layout too | Layout plus structure. Per-block JSON (`block_label`, `block_bbox`, `block_content`) and Markdown with HTML tables | wikidocs 441137 |
| Word-level boxes | **No.** Block-level boxes only; the table cell text sits inside HTML with no per-cell coordinates | same |
| Confidence scores | **None exposed** for the VLM output | same |
| Accuracy | OmniDocBench v1.6 96.33 (publisher); v1.5 (1.5 model) 94.5, table TEDS ≈ 89.8 / TEDS-S 93.5 | paddleocr.ai, arXiv |
| Languages | 109, including Devanagari (Hindi), Tamil, Telugu | arXiv 2510.14528 |
| Speed | About 2 s/page through a vLLM server on an RTX 3060 (5-page scan: 13.6 s). Direct Paddle mode: 10–24 s/image. 1.5/1.6 share one architecture; publisher figure ≈ 1.2 pages/s on an A100-class GPU | wikidocs 441137; GLM-OCR paper |
| Memory | Weights 1.8 GB; vLLM server about 3.6 GB VRAM at 0.6 utilisation; direct Paddle about 8 GB | wikidocs 441137 |
| CPU | Not practical for the VLM (no published CPU figures; classic PP-OCR alone takes 5–10 s/image on 4 CPU cores) | wikidocs 441124 |
| Deployment | Fully local. vLLM serving is Linux-only (Docker on Windows). `paddleocr[doc-parser]==3.7.0`, `paddleocr genai_server --backend vllm` | wikidocs 441137 |
| Licence | Apache-2.0 | wikidocs 441164 |
| Known failure modes | (1) **repetition loops** on some pages, detectable by output compression ratio; (2) **upside-down pages fail** unless `use_doc_orientation_classify` is on; (3) the VLM without the layout stage hallucinates more; (4) table scores measure structure, not digit correctness | wikidocs 441137; DEV.to financial-tables review |

The companion **PP-OCRv5/v6** (same `paddleocr` package, no new dependency) returns **line boxes with real per-line confidence scores** (`rec_texts`, `rec_scores`, `rec_boxes`). It costs about 0.26–0.33 s per image on GPU. It is the only part of the stack with a calibrated confidence signal, which is why the plan uses it as a verifier and not as a second parser.

---

## Part C: Gaps in the current architecture

1. **Hard block at analysis.** `analyzer.decide_state`: SCANNED → `UNSUPPORTED_SCANNED_PDF`, so the job never reaches the pipeline. Legacy parsers also return `SCANNED_PDF`, and `v2_router` returns `scanned_no_text`.
2. **MIXED files lose image pages silently.** `read_pages` returns empty word lists for image pages. Rows on those pages vanish. The balance chain catches this only when a running balance is printed; balance-less layouts can pass with missing rows. **Existing risk, independent of OCR.**
3. **"SCANNED" includes vector-outline text,** where glyphs are drawn as paths so there is no text layer but the page is crisp. In the corpus sample HSBC was 8 of 12. These are the easiest OCR wins.
4. **Bank detection needs text.** For a scanned file `detect_bank` gets nothing, so OCR text from page 1–2 must feed it or the user must pick the bank.
5. **Budgets are sized for text extraction.** T3: 120 pages, 20 s budget, 45 s isolation timeout, 1.5 GB. OCR needs about 2–3 s per page on GPU and a separate budget.
6. **20 MB file cap.** Image PDFs are large, so many real scans will exceed it. The cap is duplicated in `core/config.py` and `pipeline_orchestrator.MAX_FILE_SIZE_BYTES`.
7. **No GPU in any deployment file.** The backend image is slim CPU, so the VLM cannot run inside it.
8. **"Partially processed" has no state.** Today a statement is VERIFIED, REVIEW or FAILED. Page-level partial success has no representation (see F4).
9. **Model output has no per-cell confidence or coordinates.** Confidence must come from validation plus an independent re-read, never be invented (brief §9).

Corpus sample (12 random files per bank folder, first and last 3 pages via `check_pdf`; the run is incomplete because a large folder stalled the scan, so these are indicative only): most banks are 100% TEXT. SCANNED appeared in HSBC (8/12), Bank of India (2/12), Central Bank of India (2/12) and Equitas (1/12). MIXED appeared in Bandhan, Citibank and Fino. LOCKED is common (1–3 of 12 in many banks). **OCR is a fallback for a minority of files, not the main path.** This supports OCR-only-when-needed routing.

---

## Part D: Proposed architecture

### D1. Principle

OCR becomes a **text-layer provider**, not a parallel parser. It produces the same `Page`/`Word` contract that pdfplumber produces. After that, the existing engine, the T3 inference (header lexicon covering Withdrawal/Debit/Dr/Paid out…, date-shape inference, money assignment checked by the balance chain), normalization, every check, `V2RowSource` and all downstream steps run **unchanged**.

### D2. Flow

```
check_pdf ── TEXT ─────────────► existing T1 → T2 → T3 (unchanged; OCR never runs)
          ── MIXED ────────────► OCR only the image pages → merge into the page list → T1(spec) / T3
          ── SCANNED ──────────► OCR all pages ───────────────┐
          ── LOCKED/UNREADABLE ► unchanged                     │
                                                              ▼
                             T4 OCR tier (flag STATEMENT_ENGINE_OCR_MODE=off|shadow|serve)
  1. ocr-service: PaddleOCR-VL-1.6 (orientation classify ON) → per page: layout blocks + table HTML
  2. guards: repetition-loop check (compression ratio), empty/oversized output, page timeout → that page = FAILED
  3. table→grid adapter: each HTML table cell → synthetic Word(text, x0/x1 = column band, top = row index × pitch);
     header row kept; merged cells expanded; page number kept for provenance
  4. bank: detect_bank() on OCR text of page 1–2 (+ user choice). If the bank has a v2 LayoutSpec, try
     extract_pages(pages, spec) first; else / on failure → universal.reader.read(pages=…)
  5. checks.run_checks (unchanged) → verdict
  6. verifier (only for rows in chain breaks): PP-OCRv5 re-reads those row regions; amount disagreement → row flagged
  7. verdict policy: OCR output capped at REVIEW, code OCR_READER (like GENERAL_READER); FAILED carries no data
```

### D3. Why a grid adapter, not a new row parser

The VLM gives table structure (rows × cells) without coordinates. The engine needs coordinates only to decide which column a word belongs to. Turning cell (row r, column c) into a word with a fixed x band per column and a fixed y per row gives the engine exactly what it needs. It also reuses about 2,000 lines of tested logic (anchors, wrapped narration, DR/CR suffixes, single signed column, years, segments) instead of writing a second parser with its own bugs. Cells are already separated, so wrapped narration inside one cell becomes one narration. This is the smallest integration that meets §8E.

### D4. Deployment

- New container **`ocr-service`**: official PaddleOCR image, `paddleocr[doc-parser]==3.7.0`, vLLM `genai_server` plus a thin internal HTTP API (`POST /v1/pages` → JSON per page). It needs a GPU (8 GB minimum, 16 GB comfortable). It runs on the internal Docker network only; no document leaves AirCo infrastructure. Models load once at start (about 70 s warm-up).
- Backend: a small client (`statement_engine/ocr/client.py`, httpx is already a dependency) with timeouts, concurrency limits and retries. The backend image stays CPU-only and slim.
- Runs inside the existing RabbitMQ worker path (asynchronous). Analysis-time OCR is limited to pages 1–2 with a 15 s cap, for bank detection only.
- With `OCR_MODE=off`, or the service unreachable, behaviour is identical to today: the honest "scanned PDF not supported" message.

### D5. Routing table (deterministic)

| Capability | Bank parser available | Route | Max verdict |
|---|---|---|---|
| TEXT | any | T1 → T2 → T3 (today) | VERIFIED (T1) |
| MIXED | v2 spec | text pages + OCR pages → T1 spec | REVIEW |
| MIXED | none | merged pages → T3 | REVIEW |
| SCANNED | v2 spec | OCR → T1 spec, else T3 | REVIEW |
| SCANNED | none / unknown | OCR → T3 | REVIEW |
| any | OCR page failures > 0 | pages listed in the result, verdict REVIEW at best, FAILED if checks fail | REVIEW |
| OCR off / service down | — | today's behaviour | — |

---

## Part E: Phased implementation plan

Each slice is a separate local commit and runs behind `STATEMENT_ENGINE_OCR_MODE` (default `off`), so nothing changes until it is switched on.

| Slice | Objective | Files | Tests and acceptance | Rollback |
|---|---|---|---|---|
| **0. Baseline** | freeze current behaviour | none | full backend suite + golden on 830d161; record pass counts; corpus capability census (complete the scan above) | — |
| **1. Interface** | `OcrPage` contract + grid adapter (pure) | `statement_engine/ocr/contracts.py`, `ocr/grid.py` | unit: HTML table → `Page`/`Word`; merged cells; empty cells; `universal.read(pages=…)` on synthetic grids of known statements reproduces rows exactly | delete package |
| **2. OCR service** | containerised PaddleOCR-VL-1.6 + PP-OCRv5 | `infra/docker/ocr-service/`, compose override `docker-compose.ocr.yml` | health check; 1 image → JSON; warm model reused; per-page timeout; loop guard; orientation on | drop the override |
| **3. Client + guards** | backend client, budgets, isolation | `ocr/client.py`, `ocr/guards.py` | mocked-service tests: timeout, 5xx, loop output, oversized output → page FAILED, never an exception | flag off |
| **4. Routing** | T4 tier in the orchestrator; SCANNED/MIXED no longer hard-blocked when the flag is serve | `pipeline_orchestrator.py` (one block after T3), `analyzer.decide_state`, `analysis_service.py` | test_pipeline_orchestrator: TEXT path byte-identical with the flag on; SCANNED → T4; service down → today's message | flag off |
| **5. Validation + verdict** | `OCR_READER` cap, per-page failure list, verifier re-read | `ocr/verify.py`, `serve.engine_block` (additive keys only) | chain-break rows trigger the re-read; disagreement → row warning; the statement can never be VERIFIED | flag off |
| **6. Evaluation** | measure on real data | `tools/ocr_eval/` | see Part E2; meet thresholds before `serve` | stay on `shadow` |
| **7. Production** | metrics, logs (no PII), docs, runbook | `docs/ocr/`, monitoring | p95 latency, GPU memory, failure rates on the dashboard | flag off |

**Order of risk:** slices 1 and 3 are pure and safe. Slice 4 is the only one that touches shared code: the orchestrator plus the analysis state. It is guarded by a "TEXT path identical" regression test.

### E2. Evaluation plan (ground truth for free)

1. **Synthetic scans from verified statements:** take VERIFIED text PDFs per bank, render them at 150/200/300 dpi, and add skew (±3°), blur, JPEG noise and 90°/180° rotation. The ground truth is the current T1 output. This measures every metric in §10 automatically, per bank.
2. **Real scans:** the SCANNED and MIXED files in the corpus (HSBC, BoI, Central, Equitas, Bandhan, Citi, Fino). Hand-annotate about 20 statements (row count, opening/closing, 30 sampled rows) as the ground truth.
3. **Metrics:** row recall/precision, exact-amount accuracy, **sign/side-flip rate (reported separately)**, date accuracy, balance accuracy, duplicate/dropped rows, % statements passing chain + reference, manual-review rate, s/page, GPU memory.
4. **Proposed thresholds for `serve`:** exact amounts ≥ 99.5% of rows, side flips ≤ 0.1%, invented rows = 0 in statements that pass the chain, ≥ 80% of synthetic 200-dpi statements pass chain + reference, p95 ≤ 4 s/page. These are proposals for you to confirm (F3).

---

## Part F: Questions and decisions for you

1. **GPU hosting.** No deployment file has a GPU. Where will `ocr-service` run? A local GPU box (which card?), an EC2 g5/g6 instance (A10G/L4), or other? This decides slice 2 and the cost.
2. **Verdict cap.** I propose OCR results are **never VERIFIED** (capped at REVIEW, like T3). Do you want VERIFIED allowed later, for example when chain + reference + totals all pass on an OCR statement? I recommend deciding that only after the evaluation.
3. **Acceptance thresholds** (E2 step 4). Accept them as proposed, or change them?
4. **Partial statements.** If some pages fail OCR, should the job (a) fail, or (b) return the readable rows as REVIEW, listing the failed pages in the Statement Check sheet? I recommend (b), and it is never shown as complete.
5. **File size.** Raise the 20 MB cap for scanned PDFs only (for example to 50 MB), or keep 20 MB?
6. **Analysis-time OCR.** Is about 2–5 s extra on the analyze screen for scanned files acceptable for automatic bank detection, or should scanned files skip detection and always ask the user to pick the bank?
