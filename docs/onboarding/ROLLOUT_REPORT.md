# Rollout report — 14-bank served list on `onb` (`devin/rollout-1`)

Base: `411f6ca` (tip of `integration/v2-waves`; contains `411f6ca` by
definition — the integrity-guard float fix). Product code untouched; this
branch carries tooling + docs only. Nothing pushed.

Compose default verified live (resolved env inside `onb_backend`):

```
STATEMENT_ENGINE_V2_SERVE_BANKS=hdfc,sbi,axis,idfc,paytm,citibank,city_union,au_sfb,bank_of_maharashtra,airtel_pb,iob,apgv,south_indian,pnb
```

`ONB_EXTRA_SERVE_BANKS` was **not** set.

## 1. Rebuild and image proof — PASS

| Check | Result |
|---|---|
| `restore_statement_order` in image | present (`base_processor.py`) |
| `apply_row_count_guard` in image | present (`checks.py`/serve path) |
| `_num` float coercion in image | present (`base_processor.py`, 4 call sites) |
| `SOUTHINDIANBANK` marker | present (`extractors/south_indian/layout_spec.py:14`; collision guard comment `extraction/registry.py:187`) |
| PNB `amountinr` variant | present (`extractors/pnb/layout_spec.py:21`) |
| Registered spec count | **97 = 97** (image == repository) |
| `bank_status.json` in image | present |

`GET /api/statements/banks`:

- `all_banks`: **44 ids**
- `v2_served: true` on **exactly** the 14 rollout banks
- 10 `verified` (hdfc, sbi, axis, idfc, paytm, citibank, city_union,
  au_sfb, bank_of_maharashtra, airtel_pb)
- 4 `review_required` (iob, apgv, south_indian, pnb)
- legacy-only banks remain `legacy`; nothing else changed state

## 2. Integrity flag — PASS

`validation.integrity_passed` now reflects the real guard result: **true on
all 42 v2-served files** (was permanently `false` on v2 serves before
`411f6ca`). All 42 jobs completed; every workbook's `Transactions` rows equal
the engine's transaction count (exact match on all downloadable workbooks —
3 downloads timed out but job `validation` + `statement_engine` verdict were
still captured from the API).

| Bank | sha8s | Verdict | integrity_passed | rows (workbook = engine) |
|---|---|---|---|---|
| hdfc | 03c74e6a, 0476c63a, 1d6d4f65 | VERIFIED ×3 | true ×3 | 129, 279, 3661 |
| sbi | 0a88acf3, 348bff4b, 4ab48c24 | VERIFIED ×3 | true ×3 | 149, 279, 299 |
| axis | 12d3dc13, 23ba50c0, 26eb145c | VERIFIED ×3 | true ×3 | 340, 318, 651 |
| idfc | 28356692, 4650c87e, 4c2f4223 | VERIFIED ×3 | true ×3 | 121, 59, 667 |
| paytm | 2895898c, 33562b42, 3eecc767 | VERIFIED ×3 | true ×3 | 807, 367, 696 |
| citibank | 0b1fc4a5, 1e7f432f, 31339bfb | VERIFIED ×3 | true ×3 | 123, 328, 1191 |
| city_union | 223e53b9, 5757d35c, a376215c | VERIFIED ×3 | true ×3 | 478, 150, 451 |
| au_sfb | 4fe31321, 743c9292, 74ee653f | VERIFIED ×3 | true ×3 | 1, 310, 225 |
| bank_of_maharashtra | 2128fa93, 332c3b53, 69a64efd | VERIFIED ×3 | true ×3 | 58, 245†, 189 |
| airtel_pb | 544c29ce, bb24712d, d9ed04ad | VERIFIED ×3 | true ×3 | 807, 700, 70 |
| iob | 04bb86d3, 09028dcb, 0b216176 | REVIEW ×3 | true ×3 | 337, 426†, 87 |
| apgv | 0e44d2c3, 212797f3, 2d71643c | REVIEW ×3 | true ×3 | 62, 455, 965 |
| south_indian | 1590d10c, 1b913365, 215a6b2a | REVIEW ×3 | true ×3 | 378†, 705, 409 |
| pnb | 03f4f087, 05e5296f, 0c4d91ef | REVIEW ×3 | true ×3 | 279, 415, 1171 |

† download timed out; engine row count + validation + verdict recorded from
the job API (workbook rows not read for these three).

Review-required banks all carry `needs_review: true` +
`NO_INDEPENDENT_ANCHOR` in the `statement_engine` block — nothing is
presented as verified anywhere.

### False-flag classification

Only 2 `integrity_passed: false` outcomes — **both on legacy-served banks,
both real defects** (pre-existing legacy parse problems the flag now
honestly reports; not rollout regressions):

| sha8 | Bank | Failed checks | Class |
|---|---|---|---|
| 174a8bc3 | icici (legacy) | schema_check, balance_check, opening_closing_check, duplicate_check (`ROWS_SUSPECT`, 6 delta repairs, declared closing ≠ last-row balance) | **real defect** — pre-existing icici legacy integrity problems (audit-WRONG class); flag correctly false |
| 07283f50 | karnataka (legacy) | balance_check, opening_closing_check (`ROWS_SUSPECT`, 345/377 rows delta-repaired, declared anchors ≠ chain) | **real defect** — pre-existing; flag correctly false |

**Guard false alarms: 0. Real defects: 2 (both legacy, pre-existing).
Unknown: 0.**

### Legacy-bank payload vs `bc2cc17` — PASS

The only backend product diff `bc2cc17..411f6ca` is `_num` (integrity-guard
expectation coercion) — so `validation.integrity_passed` is the only field
that can legitimately move, and only from false to its true value. Observed:

- `statement_engine` block: byte-identical structure on all completed legacy
  jobs — `{"advisory":null,"anchored":false,"detected_bank":null,
  "engine":"legacy","layout_id":null,"mode":"serve","needs_review":false,
  "review_codes":[],"verdict":null}` (v2 untouched → no Statement Check
  sheet on legacy-only banks).
- Workbook sheet names: identical 9-sheet set on all legacy workbooks
  (Summary … Transactions) — same as the bc2cc17-era legacy shape.
- Status/verdict: completed jobs complete; honest fails fail honestly
  (canara ×2, bank_of_baroda ×2, indian_bank ×2, kotak ×1, union ×1,
  bank_of_india ×1) — matching the known bc2cc17 legacy-failure posture.
- `integrity_passed`: 5/6 legacy workbooks now `true` (was always `false`
  before — the allowed change); 2 stay `false` because real checks fail.

Per bank: icici ✓✓, karnataka ✓✓, union ✓+fail, kotak ✓+fail, canara
fail×2, bank_of_baroda fail×2, bank_of_india fail + parked-REVIEW,
indian_bank fail×2.

### Regression (bc2cc17 → 411f6ca)

**734 files, 0 differences** in status / bank / layout / rows / verdict
(650-file main set + 84-file extras; baseline measured at `bc2cc17` product
code, re-measured on the tip).

## 3. Whole-system UI smoke — PASS

Playwright on `:3400` (preinstalled Chromium):

- **14 flows** (one neutral-named real file per served bank): all detected
  the right bank, confirmed, processed, and reached a completed report.
  API-side final states: 10 `VERIFIED` + 4 `REVIEW` (iob, apgv,
  south_indian, pnb — all `NO_INDEPENDENT_ANCHOR`), **`integrity_passed:
  true` on all 14**.
- **Bank picker**: rolled-out banks show "· verified engine" / "· always
  needs review" tags — **zero rolled-out banks shown as coming soon** (two
  regex hits in the raw probe were picker-option proximity, disproven by the
  screenshots: `ro-review-sbi-1280`, `ro-review-citi-1280` show "verified
  engine").
- **Supported-banks panel** (both widths): "22 banks supported · 17 coming
  soon · 5 not supported", groups Verified(10)/Review required(4)/Legacy
  parser(8)/Coming soon(17)/Not supported(5) — matches the API exactly
  (`ro-panel-open-{360,1280}.png`).
- **Mixed batch** (5 files: iob review-only, yes not-enabled, federal
  non-enabled, hdfc verified, kotak legacy): iob row carried the
  needs-review/confirm tag; yes and federal rows showed "not enabled" with
  reasons and were **not selectable** (3 of 5 rows confirmable — exactly the
  servable three).
- **Unsupported leg**: `ro_unsupported.pdf` (non-statement invoice) →
  analyze `UNKNOWN`; `ro_yes.pdf` → `UNSUPPORTED`; `ro_federal.pdf` →
  `REVIEW` (detected but not selectable). All honest refusals.
- Widths 360 and 1280: **no horizontal scroll at 360**; **0 console errors**
  across the whole run.

Screenshots (no statement content — bank-selection and status areas only):
`e2e/shots_ro/ro-{panel,review,result,mixed}*.png`.

## 4. Docs and status — DONE (docs only)

- `docs/PRODUCT_STATUS.md`: added the rolled-out serve table (10
  VERIFIED-capable + 4 review-only), Airtel thin-corpus caveat, Axis
  truncated-statement caveat with current guard status; updated the stale
  rows for Axis / PNB / Bank of Maharashtra / South Indian and added rows for
  the rolled-out banks.
- `docs/operations/V2_ENABLEMENT.md`: annotated the axis E1 row; added the
  14-bank served list + per-group caveats under "Eligible for serving".
- `docs/operations/DEMO_READINESS.md` + `DEMO_SCRIPT.md`: rollout update
  blocks incl. the Axis caveat phrasing for demos.
- `docs/operations/RUNBOOK.md`: one-line rollback to the 7-bank list, add-a-
  bank procedure, per-stack served-list table.
- `bank_status.json` consistency check: **0 conflicts** — all 15 explicit
  entries match the live API exactly; the other 29 ids derive their state
  per the documented rules (`verified`/`legacy` come from serve config +
  `PIPELINE_BANK_NAME`, never from the JSON). No data fix needed; README
  already documents the derivation.

### Axis completeness-guard check (the `000df35f` blocker)

Direct extraction on the corpus file: **1,141 rows, verdict REVIEW**,
warnings include `unread_transaction_lines:6` + extraction warnings. The
previous silent-VERIFIED condition (1,141 of 1,147 rows) is caught by the
completeness guard on the current tip — honest current state recorded in all
three demo docs.

## 5. Hygiene inventory — DONE (report only, nothing deleted)

**Local worktrees** (34 total): those whose branches are merged into
`integration/v2-waves` and could be removed once artifacts are archived:
`wt-ca` (devin/cleanup-audit), `wt-final` (devin/final-rc),
`wt-ob` (devin/onboard-all), `wt-ow` (devin/onboard-verify),
`wt-pii` (devin/pii-fixtures), `wt-pr1` (devin/promote-1),
`wt-sc` (devin/test-typing), `wt-ub` (devin/unblock-1),
`wt-ue` (devin/unified-entry), `wt-ui` (devin/ui-banks),
`wt-v2` (devin/verify-2), `wt-v3` (devin/verify-3),
`wt-trackA` (devin/wave6), `wt-trackB` (devin/wave8),
`wt-wave10` (devin/wave10), `wt-w11` (devin/wave11), plus detached
`wt-base`, `wt-p8b`, `wt-p8c`, `wt-pr1base`, `wt-v26base`, `wt-v3base`,
`wt-w11clean`, `wt-audit`, `wt-guard`, `wt-old`, `wt-ot`, `wt-univ`,
`wt-gv`, `wt-wave9b`. Keep: `wt-ro` (this branch), `wt-demo` (demo stack),
the main checkout, and the locked `/sessions/*` worktrees.

**Merged branches** (removable after worktree cleanup):
`demo/rc`, `devin/cleanup-audit`, `devin/final-rc`, `devin/onboard-all`,
`devin/onboard-verify`, `devin/pii-fixtures`, `devin/promote-1`,
`devin/test-typing`, `devin/ui-banks`, `devin/unblock-1`,
`devin/universal`, `devin/verify-2`, `devin/verify-3`, `devin/wave5`,
`devin/wave6`, `devin/wave8`, `devin/wave9`, `devin/wave10`, `devin/wave11`,
`claude/onboard-fix` (+ the `+`-marked lines of `git branch --merged
integration/v2-waves`).

**Docker**: no stray containers — everything running belongs to `airco_*`,
`keycloak*`, or `onb_*` (`ue_*`/`demo_*` are down post-reboot). Stale images:
`onb-backend:pr1`, `onb-frontend:pr1` (~1.7 GB, superseded by `:latest`);
`docker-auth-service:latest` + `:demo-rc-stable` (demo stack — protected,
leave). `docker system df`: images 6.87 GB (758 MB reclaimable), build
cache **39.1 GB (35.7 GB reclaimable)**, volumes 416 MB (195 MB reclaimable).
Disk: `X:` 137 GB used / 87 GB free.

**Proposed (NOT executed):**

```bash
git worktree remove X:/Airco\ Projects/wt-{ca,final,ob,ow,pii,pr1,sc,ub,ue,ui,v2,v3}   # then detached ones
git branch -d devin/cleanup-audit devin/final-rc devin/onboard-all devin/onboard-verify \
  devin/pii-fixtures devin/promote-1 devin/test-typing devin/ui-banks devin/unblock-1 \
  devin/universal devin/verify-2 devin/verify-3 devin/wave{5,6,8,9,10,11} claude/onboard-fix
docker rmi onb-backend:pr1 onb-frontend:pr1
docker builder prune -f            # ~35.7 GB reclaimable build cache
docker image prune -f              # ~758 MB dangling images
```

## Defects

No new defects introduced by the rollout. Two pre-existing legacy-parse
integrity problems are now *visible* because `integrity_passed` works:
icici (`174a8bc3`: schema/balance/opening-closing/duplicate failures,
`ROWS_SUSPECT`) and karnataka (`07283f50`: broken balance chain + anchor
mismatches, 345 repairs). Classified as real defects, not false alarms.

## NOT RUN

- Byte-level `statement_engine` diff on a live bc2cc17 stack (no second
  stack exists; bounded instead by the product diff — `_num` only — plus
  identical serialized blocks observed on all legacy jobs).
- 3 workbook downloads timed out (`332c3b53`, `09028dcb`, `1590d10c`);
  verdict + `integrity_passed` + engine rows captured via the API, workbook
  `Transactions` row count not re-read from the xlsx for those three.
- Locked-PDF password flow (unchanged, out of rollout scope).
- `4c67872a` (bank_of_india) parked at `REVIEW` doc without a job —
  counted as an honest non-completion for the payload comparison.

## Containers (protected, recorded)

Machine was rebooted before this run; `ue_*`/`demo_*` stacks were down
before and remain down. `airco_*`/`keycloak*` came back via restart policy
and were not touched.

| Container | After state |
|---|---|
| airco-agent-db-1 `4579bf0eeef3` | Up (healthy) |
| airco_auth_service `8e2e980a8292` | Up (healthy) |
| aircoopsagentv2-db-1 `5055ff0ef8f8` | Up (healthy) |
| aircoopsagentv2-web-1 `f96d3ae63b09` | Up (healthy) |
| aircoopsagentv2-worker-1 `5250e39f6347` | Up |
| keycloak `fb9949a38cac` | Up (healthy) |
| keycloak-postgres `9b188150407d` | Up (healthy) |
| onb_backend `f7eaf7ebd751` | Up (healthy) — only stack rebuilt/restarted |
| onb_frontend `c7c5d1baaf8e` | Up |
| onb_rabbitmq `1ebdd3205c82` | Up (healthy) |
| onb_redis `18d6a0858d38` | Up (healthy) |
