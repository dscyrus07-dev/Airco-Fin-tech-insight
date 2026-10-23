# R10 — Is the scanned-statement path shippable as a product?

**Verdict: not yet.** The pipeline around OCR is honest end-to-end — deterministic
failures with named codes, REVIEW-capped workbooks, a Statement Check sheet that is a
model of disclosure, clean retention purging, and zero content leakage into logs or
audit events. But the **frontend drops all of that provenance**: the report screen
shows "Categorization Complete / 100% categorized" for a scanned, partially-unread
document with no REVIEW badge, no OCR mention, and no missing-page warning. A user
who never opens the Excel file would believe the result was fully verified. That is
the one defect that blocks shipping; everything else is secondary polish.

Branch: `devin/r10-product` @ `ef8c208` (R9 + `integration/v2-waves` @ e52fb24).
Test stack: isolated `-p devin_r10` (Postgres, Redis, RabbitMQ, fake-S3, backend,
auth-service, Keycloak, frontend). OCR via `STATEMENT_ENGINE_OCR_URL=mock:<dir>`
deterministic fixtures — this run tests the **product**, not the model. Synthetic
data only; no real statements; nothing pushed; `airco_*` untouched.

---

## PART 1 — scale and limits

Real API flow `analyze → confirm → process → poll → download`, `OCR_MODE=serve`:

| pages | rows | analyze | job | total wall | backend peak RSS | verdict | workbook |
|---|---|---|---|---|---|---|---|
| 1  | 22  | 1.06 s | 3.05 s | 4.20 s | 177 MiB | REVIEW | 200, 15.7 KB |
| 5  | 110 | 1.11 s | 3.08 s | 4.26 s | 186 MiB | REVIEW | 200, 22.0 KB |
| 20 | 440 | 1.14 s | 3.06 s | 4.31 s | 194 MiB | REVIEW | 200, 44.3 KB |
| 40 | 880 | 1.25 s | ~4.2 s | ~5.5 s | 247 MiB | REVIEW | 200, 48.1 KB |

Wall time is flat (analysis dominates; job time ~3 s regardless of size — mock
fixtures serve pages instantly; a real OCR service adds per-page latency linearly,
measured in R9 at ~0.9 s/page lines-only / ~6 s/page with the VLM).

**Queue/store behaviour:** `file_upload_queue` drains as fast as jobs are submitted;
every processed message is ack'd or dead-lettered once (`handler_rejected`), never
retried-forever. Redis job keys carry a 24 h TTL (`setex 86400`); index sets get
`INDEX_TTL_SECONDS` on write plus a startup backfill. No step timed out anywhere.

**60-page cap (`STATEMENT_ENGINE_OCR_MAX_PAGES=60`):**
- 61-page PDF through `analyze`: **accepted** (HTTP 200, state UNKNOWN, standard
  "scanned — we will read it with OCR" message, no cap warning) → **BUG R10-B3**
- Same file through `confirm → process`: job fails `OCR_TOO_MANY_PAGES` —
  `[ocr_reader] Scanned statement could not be read (OCR_TOO_MANY_PAGES)`
- Same file through `/api/upload/bank-statement-async`: identical failure code.
  Processing-side enforcement is consistent; the analysis path silently accepts.

**20 MB limit:**
- `analyze`: HTTP 200 with the document marked `state: ERROR`, message
  `"File is larger than 20 MB."` — per-document, clear.
- `bank-statement-async`: HTTP 400 `"File size exceeds 20MB limit"` — clear.
  Both enforced; wording/shape differ slightly (cosmetic, R10-B7).

**Largest statement handled within a sensible wait:** 40 pages / 880 rows / 12 MB
in ~5.5 s end-to-end. The configured ceiling is 60 pages / 20 MB; a mock fixture
can't measure real per-page OCR cost, so the honest statement is: **≤60 pages is
the enforced bound; 40 pages is the largest demonstrated working case**.

## PART 2 — concurrency

**2.1 — three scanned jobs submitted simultaneously** (`conc_0/1/2`, distinct
fixtures, distinct seeds):

| job | wall | job time | verdict | rows | cross-contamination |
|---|---|---|---|---|---|
| conc_1 | 4.58 s | 3.12 s | REVIEW | 110 | none — 0 foreign-seed rows |
| conc_2 | 4.58 s | 3.12 s | REVIEW | 110 | none |
| conc_0 | 7.61 s | 6.14 s | REVIEW | 110 | none |

Each workbook was verified against its own fixture's deterministic narration seed:
109–110/110 rows match own seed, 0 rows match either sibling's seed. Timing degrades
predictably (two jobs overlap cleanly, the third queues ~3 s). No deadlock; the
queue holds at most one unacked message at a time.

**2.2 — one scanned + two text-PDF jobs mixed:** text jobs finished in ~4.28 s —
identical to their solo baseline. `demo_hdfc` completed via `engine: "legacy"`,
`reconciliation_passed: true`, `needs_review: false`; `demo_sbi`/`demo_axis` also
completed; `demo_canara` failed honestly (its v2-tuned layout didn't match — a
content outcome, not contention). **Text path is unaffected by concurrent OCR
work.** Note on wording: text jobs carry `verdict: null` (the VERIFIED verdict only
exists on the v2 engine); the legacy equivalent signal is `reconciliation_passed:
true` with `needs_review: false`, which is what was observed.

## PART 3 — failure injection through the real API

| case | result | user-visible |
|---|---|---|
| a. OCR service down before start | job FAILED `OCR_SERVICE_UNAVAILABLE` | clear; no workbook (download 400) |
| b. service killed mid-document (2 s/page delay, container `kill -9` during POST) | job FAILED `OCR_SERVICE_UNAVAILABLE` | clear; no workbook, no hang |
| c. page 5 of 5 fails | job COMPLETED, verdict REVIEW | workbook delivered; `review_codes: [OCR_READER, OCR_PARTIAL_PAGES]`, `failed_pages: {5: OCR_PAGE_TIMEOUT}`, 88/110 rows; Statement Check: "Pages NOT read \| 5 (OCR_PAGE_TIMEOUT) — Some pages could not be read. This workbook does NOT contain every transaction in the statement: check the missing pages in the PDF." |
| d. whole document fails | job FAILED `OCR_NO_USABLE_PAGES` | clear; no workbook (download 400) |
| e. fixture missing | job FAILED `OCR_NO_FIXTURE` | clear; **no fall-through to the text reader** — verified: no text-path processing attempted |

Every injection produced a named code, an honest status, and no partial/misleading
workbook. (One caveat discovered: when the *last* page fails, the balance chain
still holds → workbook is delivered; when an *interior* page fails, the chain
breaks → `CHECKS_FAILED`, no workbook. Both are honest; the policy is "rows kept
only if checks don't FAIL" — documented, not a bug.)

## PART 4 — the user-visible result

**4.1 Workbook (40-page REVIEW case):** 10 sheets — Summary, Monthly Analysis,
Top 5 Credits, Top 5 Debits, Bounce And Penal Transactions, Salary Transactions,
Loan Repayment Transactions, Credit Card Payments, Transactions, **Statement
Check**. Categorization populated (880 rows across 10 categories, 100% coverage of
extracted rows). Statement Check states: engine `ocr`, verdict `REVIEW`,
"independently verified: no", "needs review: yes", OCR engine + verifier
provenance, pages read, unread pages when present, second-reader amount-check
counts, and "figures came from an image — every figure must be checked".

Two spec-vs-build discrepancies (documented, not OCR regressions):
- The prompt's "all 14 sheets" matches no build: the product emits 9 standard
  sheets (+1 Statement Check on OCR jobs). Needs spec clarification.
- **Zero formula cells** in the OCR workbook — and equally zero in a legacy
  demo_HDFC workbook. Reports are materialized values; "formulas intact" is not
  testable because no build emits formulas.

**4.2 VERIFIED never appears for a scanned statement** — job verdict REVIEW,
workbook Statement Check REVIEW, and (per the defect below) the UI shows no badge
at all rather than a wrong one.

**4.3 Real UI walkthrough** (frontend @830d161 + HelpCenter fix; Keycloak login via
Playwright; screenshots in `tmp/r10/shots/`):
- *Analysis step — exemplary:* "This is a scanned statement and we could not
  confidently identify the bank… This statement is a scan, so we will read it with
  OCR. **Results are always marked for review: please check the figures.**"
  Manual bank pick adds "If the PDF is not actually from the selected bank,
  processing may fail validation." (`partial_05b_analyzed.png`, `05c_bank_picked`)
- *Report step — drops every bit of that:* "Categorization Complete — Your
  statement has been categorized and structured." + chips `88 transactions`,
  `100% categorized` + green checks on all four step indicators. No REVIEW badge,
  no OCR mention, no "page 5 unread". Preview lists sheets 1–9 — **Statement Check
  is not even in the list** (`probe_report.png`, `partial_06_step3`). Root cause:
  `ResultStep.tsx:100` `showEnginePanel = engine==='v2' || advisory`;
  `VerificationBadge.tsx:44` renders only `engine==='v2'`/`universal`;
  `lib/statementEngine.ts:95` `engineBadgeLabel` returns null for `engine!=='v2'`.
  OCR blocks have `engine:'ocr'` → everything renders null → **R10-B1, B2**.
- Stale copy: `HelpCenter.tsx:57` still says "Photos, scans and screenshots cannot
  be read" — contradicts the OCR path the product just used (**R10-B8**).

## PART 5 — compliance

**5.1 Seven-day purge (forced-expiry test; sweep runs every 1 min in this stack):**

| artifact | before | after sweep |
|---|---|---|
| `user_file_records` row | active | `deletion_status='deleted'`, reason "retention expired after 7 days" |
| S3 upload PDF | present | **gone** |
| S3 report xlsx | present | **gone** |
| `statement_metadata`, `processing_jobs`, `raw_transactions`, `job_events`, `report_generation_logs` | present | rows deleted (children-first order verified: rt −2, pj −1, je −8, sm −1, rgl −2) |
| Redis job key | exists, TTL 86,268 s | self-expires at 24 h ≪ 7 d |
| `/app/tmp` staged upload | — | deleted in consumer `finally`; temp-dir purge at 24 h age |
| RabbitMQ DLQ | job metadata payloads | **never expires — finding R10-B6** (metadata only: ids, object keys, user name/email; `pdf_password: null`; no statement content) |
| Docker container logs | host-side | outside the app's purge scope (ops note, not app data) |

**5.2 OCR service persists nothing:** mock mode holds the document in memory only;
no page images are written anywhere (none exist on the backend container). The only
OCR-adjacent artifact on disk is the staged upload PDF in `/app/tmp`, cleaned in the
consumer's `finally`.

**5.3 No OCR content in logs/audit:** `docker logs` grepped for fixture narration
(`ACME PAYROLL`, `NEFT CR`), amounts (`894.69`, `25894`) → **0 hits**. Log lines
carry codes, counts, page numbers, timings only. `job_events.extra_data` carries
`{code, mode, rows, tier, detail, engine}` — metadata only.
Note: `raw_transactions` (audit DB) stores full extracted rows including OCR'd
narrations — by design, and inside the 7-day purge set. `api_request_logs` (340
rows) purge by `request_at` on the same cutoff.

**5.4 Diff grep since `f40047d`:** no secrets, tokens, or keys (all "token" hits
are OCR-token terminology). URLs: internal compose names (`vllm:8118`,
`ocr-vllm-server:8080`), localhost test endpoints, one documented PyPI mirror in
`Dockerfile.r6-vllm`. Clean.

## What a user can do today (OCR mode=serve, mock-quality OCR)

| action | works? |
|---|---|
| Upload a scanned statement ≤20 MB | yes — analyzed, flagged SCANNED, OCR disclosed up front |
| Get a workbook for a readable scan ≤60 pages | yes — ~4–6 s, REVIEW-capped, Statement Check disclosure sheet |
| Get a workbook when some pages are unreadable | yes — if the gap doesn't break the balance chain; missing pages named |
| Be told when the scan can't be read at all | yes — named codes, no fake workbook |
| See "verified" on a scanned statement | **never** — nothing claims it |
| Know from the UI alone that the result needs checking | **NO — R10-B1. The Excel tells them; the UI does not.** |
| Upload >60-page or >20 MB file | refused — page cap only *after* confirm (R10-B3); size refused at both doors |
| Trust "100% categorized" as "complete" | **NO — it counts only rows read (R10-B2)** |

## Ranked misleading-risk list

1. **R10-B1 (critical)** — Report screen shows "Categorization Complete / 100%
   categorized" for OCR results with zero provenance; Statement Check sheet absent
   from UI preview. The only REVIEW disclosure lives inside the downloaded Excel.
2. **R10-B2 (high)** — `100% categorized` chip counts extracted rows only; a
   22-transaction gap (unread page) is invisible on screen.
3. **R10-B3 (medium)** — >60-page scans are accepted at analysis; user invests
   clicks (bank pick, confirm) before learning the file can never be served.
4. **R10-B8 (low)** — HelpCenter says scans "cannot be read" while the product
   reads them — erodes trust in the opposite direction.
5. Legacy text jobs show `verdict: null` — consistent, but any future UI that maps
   "no verdict" → "fine" inherits the same trap as B1.

## Bugs for Claude

| id | sev | location | symptom | fix |
|---|---|---|---|---|
| R10-B1 | high | `frontend/app/components/results/ResultStep.tsx:100`; `…/engine/VerificationBadge.tsx:44-98`; `frontend/lib/statementEngine.ts:95` | `engine:'ocr'` blocks render no badge, no engine panel, no provenance anywhere on the result page | treat `'ocr'` like `'universal'`: always-render amber badge "Read by OCR — check every figure against your statement"; include it in `showEnginePanel`, `engineBadgeLabel`; add `failed_pages`/`pages_read` to `EngineDetails` |
| R10-B2 | high | `ResultStep.tsx` stats chips (~:145-160) | "100% categorized" = categorized/extracted, not of statement | when `needs_review` or `failed_pages` non-empty, render "N transactions · P page(s) unread" instead |
| R10-B3 | med | `backend/app/api/routes/statements_analyze.py` (no `STATEMENT_ENGINE_OCR_MAX_PAGES` check); cap enforced only at `ocr/client.py` | 61-pg doc: analysis 200/UNKNOWN → job fails `OCR_TOO_MANY_PAGES` | mark the document `state:ERROR` with the same message at analysis time |
| R10-B4 | med | `backend/app/services/message_queue.py` consumer loop | after a broker connection drop (observed via `docker pause`), consumer loops connect→"Normal shutdown" and never resumes consuming until process restart | add reconnect backoff + health signal; reproduce with pause/resume against dev stack |
| R10-B5 | low | `backend/app/services/pipeline_orchestrator.py:724` | `PipelineAbortError(str(e), stage=e.stage)` re-prefixes `[ocr_reader]` → doubled `[ocr_reader] [ocr_reader]` in `error_message` | strip the existing `[stage]` prefix or pass the raw message |
| R10-B6 | low | RabbitMQ `dead_letter_queue` | failed-job payloads (user name/email, object keys) accumulate forever; nothing purges them | DLQ message TTL or a retention-sweep consumer; contents are metadata-only today |
| R10-B7 | low | `statements_analyze.py` vs `upload_async.py:61` | 20 MB enforced with different shape/wording (200+doc-ERROR vs 400) | unify message text |
| R10-B8 | low | `frontend/app/components/experience/HelpCenter.tsx:57` | "Photos, scans and screenshots cannot be read" contradicts OCR serve | update copy: scans are read with OCR and always require review |
| R10-B9 | info | spec, not code | prompt expects "14 sheets" and "formulas intact"; build emits 10 sheets and 0 formula cells (legacy identical) | clarify the sheet/formula contract, then test it |

## Test-harness artifacts (not product defects)

- Fake-S3 multipart raced once during bring-up (fixed in `tmp/r10/fakes3.py`).
- A paused consumer held one message unacked; force-killing it redelivered the job
  which then failed honestly. This is what surfaced R10-B4.
- `AUTH_ALLOW_INSECURE_FALLBACK=true` enabled **only** in the isolated stack —
  must never ship.
- Frontend image bakes `NEXT_PUBLIC_*` at build time; the walkthrough used a
  browser route-rewrite `:8080→:8180` to reach the isolated Keycloak — equivalent
  result without rebuilding.

## Not run

- Real OCR service at product scale (GPU-side page latency taken from R9 numbers).
- Real customer scans (prohibited); Excel formula diff (no formulas exist);
  60-page success boundary (largest tested = 40).
