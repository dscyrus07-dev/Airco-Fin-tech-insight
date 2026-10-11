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
