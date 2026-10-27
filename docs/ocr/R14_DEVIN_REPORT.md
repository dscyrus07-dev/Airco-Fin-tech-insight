# R14 — Real-scan cache fill, engine-fix measurement, and the 300 dpi/orientation experiment

**Documents cached: 197 of 558 distinct (2,018 pages). Evaluated: 197. New-engine tiers — A+: 20, A: 2, B: 11, C: 0, R: 164 (33/197 = 17% pass).**
Caches: `X:\Airco Projects\ocr_real_cache` (197 docs, ~17 MB), `X:\Airco Projects\ocr_real_cache_ab` (12-doc A/B subset). Reports: `X:\Airco Projects\ocr_real_report{,_old,_ab}`; snapshots committed under `docs/ocr/eval/real/`.
This is parser-side verdicts on real scans — **not** ground-truth accuracy (no answer keys). All output PII-safe (sha8/bank/codes/counts only).

## 1. Engine-fix before/after (Phase 2) — identical 19-doc cache, eval `--fresh`

| metric | OLD `e7be912` | NEW merged (`35ac176`+`ac871c4`+`41de05f`) |
|---|---|---|
| tiers | R 18, B 1 | **A+ 1, A 1, B 2, R 15** |
| served (blocks / lines) | 1 / 1 | 3 / 3 |
| rows served (blocks / lines) | 19 / 19 | **456 / 427** |
| `OCR_NO_USABLE_PAGES` refusals | 2 (blocks), 2 (lines) | **0 — eliminated** |
| docs read by both → fully agreeing | 3 → 2 | 5 → 2 |
| row agreement | 62/62 | 1,047 agree / **39 side_disagree / 17 amount_disagree** |

Break counts rose only because 24× more rows are now read (blocks `amount_other` 13→303) — exposure, not regression. Merge commit `896abf8` on `devin/r13-real`; 593 statement-engine + 4 harness tests pass.

## 2. Final-cache results (197 docs, new engine)

**Tiers:** A+ 20 · A 2 · B 11 · R 164.
**Served:** blocks 26 docs / 2,068 rows · lines 31 docs / 2,869 rows.
**Timing:** p50 10.5 s/page, p95 16.8 s/page.

Refusal codes (blocks): LOW_CONFIDENCE_COLUMNS 52 · NO_DATES 48 · CHECKS_FAILED 30 · TOO_FEW_ROWS 19 · NO_DATED_ROWS 8 · NO_TABLE_HEADER 8 · NO_MONEY_COLUMNS 4 · MULTI_STATEMENT 2.
(lines): NO_DATES 46 · LOW_CONFIDENCE_COLUMNS 40 · CHECKS_FAILED 38 · NO_MONEY_COLUMNS 16 · NO_DATED_ROWS 13 · TOO_FEW_ROWS 6 · NO_TABLE_HEADER 4 · others 3.
Largest single class: **`(no header)` — 87 blocks / 108 lines refusals** (pages where no table header shape was found at all: cover/notice/ATM-summary pages and non-tabular layouts).

Chain-break classes (blocks): amount_other 502 · **side_flip 272** · digit_misread 36 · balance_misread 13 · digit_dropped_or_extra 9 · amount_missing 1.
(lines): amount_other 332 · digit_misread 74 · digit_dropped_or_extra 26 · decimal_shift 26 · balance_misread 6 · side_flip 2.

**Cross-validation (LOUD):** 48 docs read by both readers; **25 fully agree**; of 4,944 matched rows: 4,740 agree, **176 side disagreements** (one reader put money on the wrong side), 28 amount disagreements. Unmatched tails: 831 only-in-blocks, 1,460 only-in-lines.

**Per-bank** (A+/A/B/C/R): HSBC 17/0/0/0/0 — clean sweep; HDFC 1/0/6/0/6; ICICI 1/1/1/0/14; Karur Vysya 1/0/0/0/5; Karnataka 0/1/0/0/5; DCB 0/0/1/0/0; Indian Bank, Other_Unknown, DBS 1 B each; all remaining banks (Kotak 16, SBI 16, Union 12, Axis 9, BoB 9, Yes 9, Canara 8, IDBI 6, IDFC 5, IOB 3, IndusInd 3, BoI 4, Citibank 3, Central 2, single-digit others) all R. HSBC's win is format-specific (its columnar scans OCR cleanly); there is no evidence yet that other banks' scans can't pass — the refusal classes dominate instead.

## 3. Phase 4 experiment — 300 dpi + line-reader orientation: **HURTS**

12-doc fixed subset (8 highest chain-break docs + 4 clean controls), re-OCR'd at `OCR_DPI=300` + `OCR_LINES_ORIENTATION=1` on a side service, evaluated on the same engine:

| doc | 200 dpi baseline | 300 dpi + orientation |
|---|---|---|
| 3 Axis docs | lines 51–73 breaks | **lines → LOW_CONFIDENCE_COLUMNS, 0 rows** |
| Citibank dd665311 | blocks 284 brk, lines 416 rows/55 brk | blocks 225 brk, **lines 0 rows** |
| ICICI 1fd686d6 (A control) | 13/13 rows served | **→ R, 4/0 rows** |
| KarurVysya 963144d4 (A+ control) | 61/61 rows served | **→ R, 58/0 rows** |
| HDFC + HSBC controls | clean | clean (unchanged) |
| Other_Unknown 4c7ce580 | 159/281 rows, 45/11 brk | 243/283 rows, 17/9 brk — best case |

- **Line reader lost all rows on 6 of 12 docs** (`LOW_CONFIDENCE_COLUMNS`) — orientation classification changes line-box geometry/reading order enough to break column inference.
- Blocks breaks shrank on several docs (284→225, 45→17, 46→40) but **no document flipped to served**; rows dropped (398→338 on Citibank) or held.
- Speed neutral (p50 ≈ 10 s/page either way; subset total within noise).
- **Verdict: hurts overall. Do not enable.** The decimal-drop hypothesis is not service-side fixable this way; errors live in row geometry, and 300 dpi rescues some digits while breaking inference elsewhere.
- Service **restored to exact R12 config** (`OCR_DPI=200`, orientation flags off — `OCR_LINES_ORIENTATION` defaults off and was never set on the live container): `/health` 200, and a synthetic scan read via the backend returned 2 blocks + 2 lines, 0 failed pages.
- `OCR_LINES_ORIENTATION` flag and harness `--sha` subset filter are committed (defaults preserve R12 behaviour).

## 4. Service health over the night

- **~05:30 Docker Desktop itself terminated** (host-side; all containers Exited 255). Everything was restarted; the OCR fill resumed from cache seamlessly — resume works, no data lost.
- **Frontend still DOWN**: Windows winnat reserved `2970–3069` while Docker was down; `airco_frontend` cannot bind :3000 and `airco_nginx` loops on the missing `frontend` upstream. Fix needs an admin shell: `net stop winnat && net start winnat` (or reboot), then `docker start airco_frontend airco_nginx`. Nothing else is affected; backend/ocr/auth all healthy.
- OCR service: **0 worker kills, 0 page timeouts, 0 repetition-loop kills** across ~2,200 real pages. Startup-window 503s only (model loading; the aborted first fill attempt saw them — its 157 `ocr_error` index rows were stripped and the docs re-queued cleanly).
- GPU steady at ~11.9/12.3 GB through the night; disk usage of cache trivial (17 MB).
- The fill ended on its `--budget-hours 4` bound: "budget reached after 142 documents". **361 of 558 distinct docs remain uncached** (resume: same `ocr` command, another budget). The 3 over-60-page corpus files were not reached in this pass (0 `skipped` records).

## 5. What remains unverified / notes for Claude

- Cache is ready for offline iteration: `X:\Airco Projects\ocr_real_cache` + `eval --fresh` re-scores on any new engine.
- Dominant refusal classes to attack, in order: headerless pages (87 blocks / 108 lines), NO_DATES (~47), LOW_CONFIDENCE_COLUMNS (~46), CHECKS_FAILED (~34) driven by amount_other/side_flip breaks.
- Cross-reader disagreement data (176 side / 28 amount) is the strongest evidence yet for an opt-in "reconciler chooses the consistent read" feature — still undecided; engine today never alters a read value.
- Live app: backend healthy on :8000; **:3000 unreachable until the winnat fix above runs** — flagged for the user.
