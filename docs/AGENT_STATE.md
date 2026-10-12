# AGENT STATE — demo/rc acceptance

[D] STAGE S1 DONE 2026-10-12 01:38 — baseline: 224 be tests / 27 fe tests / tsc 0 / build pass (lint dead: next lint removed in Next16)
[D] STAGE S2 DONE 2026-10-12 01:38 — docker build --no-cache, 8/8 services healthy (nginx healthcheck fix c0d4798)
[D] STAGE S3 DONE 2026-10-12 01:38 — off/shadow/serve-hdfc verified; kill switch live (serve->off env + up -d backend, no rebuild)
[D] STAGE S4 DONE 2026-10-12 01:38 — 46 folders via API+UI: 10 PASS / 5 PASS-WITH-NOTES / 0 FAIL / ~30 NOT-SUPPORTED / 1 INCOMPLETE (Cosmos: no readable candidate)
[D] STAGE S5 DONE 2026-10-12 01:38 — Playwright flow desktop+360px: login->detect->confirm->process->download; console clean after b7808b6
[D] STAGE S6 DONE 2026-10-12 01:38 — allowed-area fixes: c0d4798 nginx, 6455c53 BoI/IndianBank routing, b7808b6 history retry; engine defects D3/D4/D5 -> Claude
[D] STAGE S7 DONE 2026-10-12 01:38 — DEMO_READINESS/DEMO_SCRIPT committed, RUNBOOK+reset_demo.py in comparison/demo (untracked per .gitignore)
[D] STAGE S8 DONE 2026-10-12 01:38 — final images built, 5 demo banks re-run, corpus hash 46 files unchanged, git clean
[D] DONE 2026-10-12 01:38 head 70a4d6e — REPORT.md + results.jsonl + rollout_recommendation.csv in comparison/demo/

Gate deviation: prompt required READY FOR DEVIN newer than 89c7b21; none existed.
Run proceeded on local demo/rc per explicit user instruction. Local only, never pushed.

NEXT CLAUDE ACTION (ranked):
1. D3 wrong-bank: legacy ICICI processor silently accepts an HDFC file (sha8 0000d106 -> job f0daa9c0, 148 txns). Issuer validation missing; v2 allowlist stays hdfc-only until the legacy-vs-v2 gap is understood.
2. D4 issuer-validation false negatives: BoB 00196b23 + Indian Bank 00b7c2e3 are v2-VERIFIED but legacy rejects them — app-format statements.
3. D5 legacy parser gaps: Canara 01739d7a (no txn table), Union 05794921 (no rows).
4. Persist statement_engine into /api/profile/history so dashboard badges work on old rows.
5. Replace dead `next lint` (Next 16) with a real eslint config.
6. PII history purge decision — still blocks any push.
[W11] A START 2026-10-12 01:55 head c022630
[W11] A DONE 2026-10-12 02:12 head 6e38f95 — T1 wrong-bank guard (0/300 false alarms), T2 history statement_engine, T3 eslint flat config (11e/1w -> 0/0), T4 friendly UNKNOWN + supported-banks note, T5 all checks green. Notes: docs/banks/WAVE11A_NOTES.md

NEXT CLAUDE ACTION (ranked):
1. D3 wrong-bank still open at the parser level: guard now flags BANK_MISMATCH (needs_review) but legacy ICICI still silently accepts HDFC input — issuer validation belongs in the legacy/v2 gap work, not here.
2. D4 issuer-validation false negatives: BoB 00196b23 + Indian Bank 00b7c2e3 (v2 VERIFIED, legacy rejects).
3. D5 legacy parser gaps: Canara 01739d7a, Union 05794921.
4. PII history purge decision — still blocks any push.

[W11] B START 2026-10-12 02:13 head 5445f90
[W11] B DONE 2026-10-12 05:05 head bd4cf0c — E1 table (V2_ENABLEMENT.md): 8 corpus-eligible → E3 acceptance: 7 served, indusind BLOCKED (first-row mutation stays VERIFIED, checks layer → Claude). E2: v2-only banks end-to-end (Decimal crash fixed bd4cf0c, message fix 1506e12). E3: 40 API picks, 48 workbooks 0 formula errors, 5 UI legs, mutation+wrong-bank probes all safe except indusind. E4: DEMO_READINESS/DEMO_SCRIPT/RUNBOOK refreshed (real city_union NO_INDEPENDENT_ANCHOR replaces the invalid BoB review moment). E5: clean-checkout gates all green; demo stack rebuilt from devin/wave11 (demo-rc-stable tags kept, rollback in RUNBOOK). Report: comparison/wave11/REPORT.md

NEXT CLAUDE ACTION (ranked):
1. BLOCKER indusind row-0 unconstrained: first-txn amount mutation stays VERIFIED (sha 00d70d3a; rows 1/5 correctly fail). Pairwise chain has no predecessor for row 0, reference check derives from balances only, no printed totals. Fix in checks layer, then re-run the mutation probe before re-allowlisting.
2. D3 wrong-bank at parser level: legacy ICICI still silently accepts an HDFC file; guard only flags needs_review.
3. D4 issuer-validation false negatives: BoB + Indian Bank app-format files v2-VERIFIED but legacy rejects.
4. D5 legacy parser gaps: Canara (no txn table), Union (no rows) — also keeps them below E1 eligibility.
5. Unswept specs (idfc, citibank, city_union, indusind) have no forced cross-bank sweep coverage — run the c5 sweep on them to firm up xb evidence.
6. PII history purge decision — still blocks any push.
[UNI] START 2026-10-12 05:53 — universal reader wave, part1 engine on devin/universal

[UNI] PART1 DONE 2026-10-12 head ddf14de — T3 universal reader: lexicon+infer+reader, REVIEW cap, budgets, isolation. U3a done: 6361 base-VERIFIED, 67.8% row-exact, false-clean 0.00% post-fixes.
[UNI] DONE 2026-10-12 head a52e951 — part2 product+UI wired behind STATEMENT_ENGINE_UNIVERSAL_MODE (off default, byte-identical off vs serve on 20 files). Reports: comparison/universal/REPORT.md, docs/engine/UNIVERSAL_RESULTS.md.

NEXT CLAUDE ACTION (ranked):
1. Registered-spec truncation class (UNIVERSAL_PROPOSALS #1): axis spec drops dated rows above period-marker footers — `000df35f` 1141 vs true 1147 VERIFIED, ~50 axis + ~19 kotak files. Shared `_region_start` fix or per-spec workaround.
2. u3b still running (resumable): finish, then run propose_layouts for real fingerprints (u3a records lack header_tokens).
3. `opening_row_balance_only` under single-amount specs drops row 0 — fixed in T3 infer; registered specs would need the same check (PROPOSALS #2).
4. Corpus relabel: Non_Bank_Documents has ≥20 real statements; BoB folder holds a Union file (PROPOSALS #3).
5. U8 live compose acceptance leg (API+UI on own stack, LibreOffice recalc) not run — run before any demo claim of T3 serve.
6. T3 stays REVIEW — do not elevate; conditions in UNIVERSAL_RESULTS.md recommendation.
7. Prior wave-11 blockers unchanged: indusind row-0 mutation, legacy ICICI wrong-bank acceptance, PII purge decision.

[FINAL] DONE 2026-10-12 09:19 head 15fef67 (+ pending report commit)

devin/final-rc consolidates wave11 + universal. All required gates pass:
14,445-file probe vs phase8c: 0 wrong-bank VERIFIED, 0 rowhash diffs on
7,294 double-VERIFIED, 0 unexplained escalations/de-escalations, VERIFIED
total identical (7,294). Flag matrix: default cell content-identical to
880b5e2 (sole diff = new BoI coverage). Regression gate 19/19. Backend
510 pass + 8 pre-existing env fails; frontend 31/31 vitest, tsc/lint/build
clean. E2E on own finrc compose project: 17 API legs + icici override +
UI legs (0 console errors) + kill switch + LibreOffice recalc (0 formula
errors, 903 numeric cells identical) + dedup + wrong-bank BANK_MISMATCH x3.
BLOCKERS in comparison/final/REPORT.md: axis audit-WRONG reproduced VERIFIED
on truncated 1,141/1,147 rows — recommend dropping axis from serve allowlist
until the registered-spec fix; creds still in git history (rotation needed).
NEXT CLAUDE ACTION #1: review and merge devin/final-rc.

[UE] START 5744400 (devin/unified-entry from integration/v2-waves tip, worktree wt-ue)

[UE] DONE b506830 — unified single entry point on devin/unified-entry (from integration/v2-waves@5744400).
Built: backend additive fields (confirm account_type; process full_name + per-doc account_type/statement_label; absent = today's payload, tested),
statementsApi extensions, useStatementWorkflow hook (upload/review/processing/report, 2.5s polling, expiry handling),
workflow components (UploadDropzone/ReviewTable/ProcessingList/ReportList/StatementWorkflow), NEXT_PUBLIC_UNIFIED_ENTRY flag (default off,
flag-off equivalence tested), 360px h-scroll fixed (0px at 360/768/1280), E2E on synthetic PDFs (detection/override/unlock/honest
negatives/parallel/report/history/redirect, 0 console errors), docs updated. Not verified: nothing blocking; legacy-engine jobs show no
verification badge (correct). Decisions for Claude: none required; flag default stays off.
