# N8 — Robustness & Limits (measured on `onb`, 1 uvicorn worker, 2-CPU host)

All tests used synthetic files (`tools/n8/.local`) or corpus PDFs referenced by
sha8 only. No statement content printed.

## (a) The two "persistent analyze-timeout" files — NOT REPRODUCED

| sha8 | pages | size | check_pdf | detect+analyze | S3 put (WAN) | HTTP total | result |
|---|---|---|---|---|---|---|---|
| `e775dd3a` | 19 | 45KB | 0.42s | 0.29s | ~2s | **2.9s** | 200, doc state REVIEW |
| `b7eb2e45` | 4 | 553KB | 0.26s | <0.01s | ~4.5s | **5.0s** | 200, doc state UNKNOWN |

- In-process profile (`check_pdf` → `analyze_text_pages` → `detect_layout`)
  shows sub-second engine cost; the WAN S3 put to Supabase (ap-southeast-2)
  dominates.
- Deployed code == worktree (`md5sum` match on analyzer/capability/analysis).
- Prior timeouts (`VERIFY3_REPORT`) were likely environmental: saturated host
  and/or stale build. Current build returns in ≤5s.
- **What the user sees on a genuinely slow call**: an unbounded spinner — the
  Next.js proxy route (`frontend/lib/statementsProxy.ts`) sets **no timeout**
  and the route has no `maxDuration`; the client never gives up.
  `analyze` also shares the `asyncio.to_thread` pool with publish — under an
  upload burst, analyze can starve for minutes (mechanism measured below).

## (b) Largest files (process path, async upload → job)

| sha8 | bank | pages | size | outcome | wall time | backend mem peak |
|---|---|---|---|---|---|---|
| `474ff6d2` | paytm | 160 | 4.27MB | completed | 88.1s | 1.33 GiB |
| `1203ecf7` | icici | 90 | 3.12MB | completed | 109.6s | 1.64 GiB |
| `a6aebcf5` | paytm | 110 | 2.81MB | completed | 87.3s | 1.53 GiB |
| `400b9d03` | kotak | 67 | 3.05MB | failed (extract) | 138.1s | 1.58 GiB |
| `b3724368` | citibank | 62 | 4.14MB | failed `[bank_routing]` unsupported | 24.3s | 1.63 GiB |

- ~1s/page processing throughput; memory peak ~1.6 GiB on a 4.3MB/160-page
  file — dominated by pdfminer/layout structures, grows with page count.
- **No page-count limit** — the 1,000-page synthetic was accepted and parsed
  before failing bank match (8.4s).
- The 62-page citi file dies fast because Citibank is unsupported on the
  process path (its analyze verdict is honest `UNKNOWN`).

## (c) Parallel uploads — saturation measured

25 identical small PDFs submitted in parallel (`ThreadPoolExecutor(25)`),
client timeout 30s:

- **0/25 client-side successes** — every request hit the 30s client timeout.
- **25/25 jobs landed server-side** — job created in Redis before the response
  (a retrying client would create duplicates; no dedup by file hash seen).
- Drain: serial local processor ≈ 1 job per ~25-60s (small file) — the burst
  took ~10min to drain; 13 completed, consistent 8-txn/hdfc output each
  (cross-contamination check: all outputs identical to the single-run twin —
  correct filename↔job mapping, no swap observed).
- **Mechanism**: `asyncio.to_thread` default pool ≈ 6 threads on this 2-CPU
  host. Each publish attempt to the broken RabbitMQ connection blocks a thread
  for seconds; WAN S3 puts (1-5s each) fill the rest — pool exhaustion serializes
  all requests (`/upload`, `/analyze`, `/jobs` share the loop's executor).
- RabbitMQ on `onb` is degraded: `file_upload_queue` consumer attached but
  publish fails → every job takes the local-fallback path; DLQ holds 36+ stale
  messages (retention finding).
- **Queue/job expiry**: job blobs carry 24h Redis TTL; index sets never
  expire; pending jobs DO survive a backend restart (re-scanned and resumed).

## (d) Malformed inputs

| input | result | notes |
|---|---|---|
| zero-byte `.pdf` | HTTP 400 `PDF_UNLOCK_FAILED` | detail leaks internal temp path `/tmp/tmp*.pdf` |
| `.txt` extension | HTTP 400 "Only PDF files are accepted" | clean |
| 1,000-page PDF | accepted → failed `bank_routing` in 8.4s | **no page cap; a hostile >1000p file burns worker time** |
| wrong PDF password | HTTP 400 `PDF_PASSWORD_INVALID` + `requires_password` | clean |
| corrupted xref | HTTP 400 `PDF_UNLOCK_FAILED` | temp-path leak again |

## (e) Restart safety — measured twice

- **Restart with 19 pending + 1 running**: after `docker restart`, pending
  jobs resumed and drained to completion. The in-flight job (`b9754725`) was
  observed `running` across the restart, then `completed` — in-flight work is
  re-run to completion (no checkpointing → the whole job restarts).
- **Dishonest-state window**: for ~minutes post-restart, the killed job reads
  `status: running` in both Redis **and** `user_file_records.status='running'`
  while nothing executes. If the rescan misses it, both stores keep `running`
  forever (DB row has no TTL).
- **No job-state reconciliation on startup** beyond re-queueing pending —
  a `running` job whose rescan is skipped would lie forever. Retry = resubmit
  the file (new job_id).

## Current vs recommended limits

| limit | current (code) | recommended |
|---|---|---|
| max file size | 20MB (`upload_async` reads whole file into memory) | keep ≤20MB but stream to temp; analyze path already 20MB cap |
| max pages | **none** | ~300 pages/process; ~100 for analyze |
| upload concurrency | unbounded; threadpool ~6 effective | rate-limit per IP/user (none measured: 25/25 accepted) |
| analyze files/request | `ANALYZE_MAX_FILES` (code constant) | keep; add per-request wall-time budget |
| client/proxy timeout | **none** (proxy fetch has no timeout) | 60s proxy timeout + client abort |
| job TTL | 24h redis blob; DB row forever | keep 24h blob; reconcile `running`→`failed` on startup |
| rate limiting | none observed on upload/analyze | token bucket per user/IP |

## Files/tools

`tools/n8/big_run.py` (large-file process timing + mem peak),
`tools/n8/retention_probe.py`, `tools/n8/.local/malformed/*`,
`tools/n8/.local/big_run.jsonl` (raw timings).
