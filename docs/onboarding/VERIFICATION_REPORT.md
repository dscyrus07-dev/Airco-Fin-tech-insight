# Independent Verification Report — all-banks onboarding (prompt 26)

Verifier branch: `devin/onboard-verify` · verified tip: `5d8026a` (`devin/onboard-wire`)
Pre-onboarding base: `integration/v2-waves` @ `8b57e0d6c1dbd67555a90cc5311d434226273a17`
Gate: `[OW] DONE` found in `docs/AGENT_STATE.md`. All numbers below were re-measured with my
own tooling (`tools/verify/`), not the previous agents' scripts. Identifiers: bank ids,
counts, sha8 only. No statement content anywhere. Corpus read-only. Nothing pushed.

---

## Executive summary — **NO-GO** for merging onboarding into the integration branch

The wiring work is largely honest and well-gated: the shipped allowlist is unchanged,
non-allowlisted banks are correctly refused end to end, the UNSUPPORTED-row UI bug is
fixed, Docker stack is healthy and reproducible, and 712/738 backend tests pass with the
8 failures pre-existing on base. Per-bank statuses are all *confirmed* (none meet the
READY gates — consistent with the report).

But verification found real defects the reports did not disclose:

1. **Served-bank regression (major):** 1 of 619 existing-bank regression files changed
   base→tip. Paytm file `d4de1ead` was `v2 / VERIFIED / 103 rows` at base and is refused
   `foreign_bank` at tip. Caused by commit `c43e8f1` (`onboard(indusind)`): registering
   `INDUSINDBANK` as a spec `bank_markers` entry adds it to the registry's `known` set;
   this Paytm statement names IndusInd in non-row furniture, so the (correct) foreign-marker
   guard now rejects it. A real, currently *served* bank can lose a file it previously
   processed. This is exactly the class of silent interaction the no-regression gate is for.
2. **Silent row drop in report (major):** HDFC `0a05a1f7` — engine extracted 49 rows
   (verdict FAILED); the completed job's downloaded workbook contains only **38**
   transaction rows. An incomplete workbook was served for a non-empty statement.
3. **Markerless layout accepts (major, unresolved):** 8 files in the `csb` folder were
   *accepted under the federal spec* (`v2`, federal layout) while containing **zero**
   bank-identifying text markers (no `federal`/`fdrl`/`csb` anywhere in extracted text).
   `bank_markers` are not required for acceptance by design ("a page that names no bank is
   not refused"), so whether these are genuine Federal exports with image-only letterheads
   or true wrong-bank accepts is unresolvable without OCR (not permitted). The overnight
   report's claim that these files "print Federal" is **FALSE** per my text extraction.
4. **kvb unchecked closing anchor (minor):** kvb VERIFIED files reconcile opening+chain but
   never check the printed summary closing, which disagrees on 3/3 sampled (`5d823031
   032f3977 d7c4ad2a`). Either format semantics or under-supported VERIFIED; kvb remains
   SHADOW_ONLY either way.
5. **Protected-area non-additive change (minor):** `pipeline_orchestrator.py` changed an
   *existing* alias `"south indian bank": "south_indian_bank"` → `"south_indian"`. The old
   target was a nonexistent spec key, so the change is a fix — but it is not the additive-only
   change the boundaries allowed, and it was not disclosed.

Per-gate verdicts: every bank keeps its reported status; nothing upgrades. The blockers are
the regression + workbook drop above, not the bank classifications.

**Recommendation (labelled as such):** fix the Paytm marker-collision (scope foreign-marker
refusal to regions that distinguish banks, or add an own-marker precedence), reproduce the
HDFC row-drop, and re-run the 619-file regression to zero before merge. Onboarding itself is
safe to keep *behind the unchanged allowlist* — the defects are in interactions, not specs.

---

## Confirmed `SERVE_BANKS` (unchanged — must not expand)

```
hdfc,sbi,axis,idfc,paytm,citibank,city_union
```

0 of the 24 onboarded banks qualify for serving. Verified inside `onb_backend` env and via
`/api/statements/banks` (15 banks listed; `v2_served: true` for exactly the 7 above).

---

## 1. Boundaries and diff audit — `8b57e0d..5d8026a`

107 files changed: **92 added, 15 modified, 0 deleted.**

Modified files (all audited):

| file | verdict |
|---|---|
| `pipeline_orchestrator.py` | **non-additive**: existing `south indian bank` alias re-pointed `south_indian_bank`→`south_indian` (old key nonexistent; a fix, but not additive) |
| `statement_engine/v2_router.py` | additive `DETECTOR_TO_SPEC_BANK` entries only (csb, uco, airtel_pb, ippb, dhanlaxmi) |
| `extractors/registry.py` | additive imports + registrations only |
| `banks/{airtel_pb,csb,ippb,uco}.json` | additive marker/name/domain fields for new banks |
| `docs/*` ×4 | docs only |
| `frontend/Dockerfile` | additive `ARG/ENV NEXT_PUBLIC_UNIFIED_ENTRY`, no default value |
| `AnalyzeFlow.tsx`, `ReviewTable.tsx` | the mandated UNSUPPORTED-row fix (existing-logic edit, UI — not a protected area) |
| `frontend/types/index.ts` | additive `BankName` union widening |

Protected areas **unchanged** (verified absent from diff): `checks.py`, `extraction/*`
(incl. `registry.py` resolve logic), `detector.py`, all existing `layout_spec.py` files,
all legacy parsers, `process_statement`, verdict policy, completeness/mismatch guards,
`STATEMENT_ENGINE_*` defaults.

**Indirect effect not disclosed:** new spec `bank_markers` expand the registry `known` set
used by foreign-marker refusal → caused the Paytm regression above. The *letter* of
"additive only" holds; the *spirit* (no observable behavior change on existing banks) does not.

## 2. PII / secret scan

Scan of the full base→tip diff, all new docs, and all commit-intended `tools/verify`
outputs: patterns for account numbers, phone, email, PAN/Aadhaar-like strings, IFSC tied to
persons, ≥9-digit runs, corpus filenames, high-entropy tokens, API keys, JWTs.
**Result: CLEAN** — 0 matches outside `tools/verify/.local/` (gitignored measurement data,
which itself contains only sha8/counts — scanned clean). No `passwords.txt` opened.

## 3. Per-bank re-measurement (my runner, `mode=shadow`, 1,738 unique files / 30 folders)

See `VERIFICATION_BANKS.csv` for the full table. Detection% is over text-usable files.
Deltas vs report >1pp: `ujjivan_sfb` 75.8 (−1.1), `central_bank` 86.8 (−3.0),
`apgv` 86.7 (+2.5), `yes` 88.7 (+2.9), `airtel_pb` 85.7 (+28.6 — their denominator
counted routed-only; mine counts correct attribution on text files), `csb` 37.5
(8 of 17 routed to federal spec — the markerless accepts).

Gate check (READY requires det 100% + 0 false accepts + ≥90% V/R hold-out + ≥80% VERIFIED
where anchors + clean audit): **no bank changes status** — all reported statuses confirmed.

`kvb` detection remains 5.4% (pre-existing detector weakness, not onboarding-caused —
bank was already registered at base).

### Independent audit (spec-independent: dated-amount line count, chain recompute,
opening/closing anchors via generic regex, page continuity)

187 VERIFIED files audited across all 10 banks that produced any VERIFIED:

| bank | sampled | flags | note |
|---|---|---|---|
| indusind | 40 | 0 | clean |
| federal | 40 | 0 | clean |
| standard_chartered | 40 | 0 | clean |
| au_sfb | 14 | 0 | clean |
| yes | 15 | 0 | clean |
| idbi | 15 | 0 | clean |
| bank_of_maharashtra | 8 | 0 | clean |
| dcb | 7 | 0 | clean |
| kvb | 3/3 | **closing_mismatch ×3** | real finding, see below |
| bandhan | 5/5 | closing_mismatch ×5 | **audit artifact** — the engine's own spec closing anchor reconciles exactly (`printed closing == last balance`); my generic regex matched a different summary cell. Not a product defect. |

**kvb finding (minor):** on all 3 sampled kvb VERIFIED files, extraction is complete
(`dated-amount-lines == rows`, chain clean, printed opening matches exactly) — but the
statement's summary block prints a "Closing Balance" figure that does **not** equal the
extracted last balance (diffs observed: 28.35 / 1,896.54 / 39,307.51). The kvb spec has no
closing anchor, so the engine VERIFIED on opening+chain only and never compared it. Either
the printed figure denotes a different quantity (e.g., balance incl. unposted items) or the
VERIFIED is under-supported. sha8s: `5d823031 032f3977 d7c4ad2a`. Downgrade pressure:
kvb stays SHADOW_ONLY (its 5.4% detection already disqualifies it) — no status change.

REVIEW justification (all 384 REVIEWs' reason codes + independent anchor spot-check ×8):
overwhelming majority = "no independent opening/closing anchor: balance chain is
self-derived" → **justified**. My independent check confirms: files that do contain
"opening/closing balance" phrases have **no amount on the anchor line** (text layer splits
label/amount) → REVIEW is honest, not avoidable. Residuals: extraction-warning and
date-monotonic REVIEWs = real extraction issues, also justified.

## 4. Cross-bank confusion matrix (45 folders, runA_all + reg_tip, ~2,350 files)

Off-diagonal spec **accepts**:

| folder → spec | n | classification |
|---|---|---|
| csb → federal | 8 | **unresolved** — markerless docs; ground truth not confirmable without OCR |
| idbi → icici | 1 | **correct** — `7dd67f11` contains `icici` marker, no `idbi` → corpus mislabel |
| sbi → rbl | 1 | **correct refusal** — `b2c42bdf` `other_bank:rbl`, identical at base (pre-existing) |
| deutsche/fino_pb/tmb → self | 5 | **correct refusals** — `other_bank:*` (NOT_POSSIBLE, no spec) |
| bank_of_india → bank_of_india(legacy) | 3 | same bank via legacy tier — not a cross-route |

Confirmed wrong-bank accepts: **0**. Unresolved accepts: 8 (csb→federal). False refusals:
1 regression (`d4de1ead` paytm) + 1 pre-existing (`b2c42bdf` sbi→rbl, identical at base).

Look-alike pairs all clean: union vs city_union, kotak variants, BOB/BOI/BOM/CBI/
indian_bank/iob, karnataka vs kvb, paytm splits, sbi vs sbm, pnb vs punjab&sind,
apgb vs apgv, SFB/payments banks — zero cross-accepts observed.

## 5. Regression on existing banks — 619 unique files, 15 banks, base vs tip, same config

| metric | result |
|---|---|
| identical records | 618/619 |
| diffs | **1** — `d4de1ead` (paytm): base `v2/paytm/VERIFIED/103r` → tip `fallback/foreign_bank` |
| causing commit | `c43e8f1` (`onboard(indusind)`) — INDUSINDBANK entered the known-marker set |

Synthetic probes (own generator; identical base vs tip):
clean→VERIFIED · wrong-bank-narration→VERIFIED (narration markers correctly out of scope) ·
truncated→REVIEW (completeness guard) · summary-after-transactions→VERIFIED (summary not
ingested) · locked→unsupported/locked · scanned→unsupported/scanned_no_text ·
unknown→fallback/bank_unconfirmed.

## 6. End-to-end on `onb` stack (authenticated HTTP)

**Allowlisted banks — 14 records, 7 banks ×2 files:**
analyze 200 → DETECTED/REVIEW → confirm ok → process 200 → job `completed` → download 200
for all 14. Detected bank/layout/verdict match my shadow output on all records.

**Workbooks (openpyxl, independent):** all 14 open, all 10 expected sheets present, 0
formula-error cells, no empty reports. Transaction rows == engine rows on **13/14**.
**Defect:** `0a05a1f7` (hdfc) workbook has 38 rows vs engine's 49.

**Wired-but-not-allowlisted banks — 46 records, 23 banks ×2 files:** analyze 200 → doc
`UNSUPPORTED` (or `UNKNOWN` where detection genuinely missed: kvb ×2, idbi ×1 — consistent
with shadow) → confirm refused `ok:false BANK_REQUIRED` on all 46 → no process job
possible. **Correct**: not listed, not processable under shipped config.

**Negative cases (all pass):**
- Locked PDF: `REVIEW` + `PASSWORD_REQUIRED`; unlock path → `DETECTED`/AWAITING_CONFIRMATION
- Scanned PDF: `UNSUPPORTED` + `UNSUPPORTED_SCANNED_PDF`; confirm → `NOT_CONFIRMABLE`
- Override bank A→B: confirm → HTTP 400 (mismatch guard refuses)
- Unknown bank: `UNKNOWN` + AWAITING_CONFIRMATION
- Non-allowlisted bank: `UNSUPPORTED`, confirm 400

**Browser (Playwright, preinstalled Chromium):** sign-in OK (Keycloak round-trip to
/dashboard), multi-file batch (5 files) uploaded, review rows rendered, bank dropdown
populated with servable banks + "verified engine" tags, **UNSUPPORTED row: no bank select,
no default bank, no row Confirm**. Viewports 360/768/1280: `scrollWidth==width`, no
horizontal scroll. 0 console errors.

## 7. Docker / environment truth

- Protected containers identical IDs/uptime to the `[OW]` baseline: `airco_auth_service`
  8e2e980a8292 (26h), `keycloak` fb9949a38cac (26h), `keycloak-postgres` 9b188150407d (26h),
  `ue_backend` bafad1db0191, `ue_frontend` 8370c7f6fe09, `ue_rabbitmq` 6aa001419890,
  `ue_redis` b48f553aa2b6 (all 9h). **Untouched.**
- `onb_*`: backend healthy :8401, frontend :3400 200, redis+rabbitmq healthy. Image holds
  **81 registered specs** — matches local tree exactly (new specs present).
- Rebuild from `docker-compose.onboard.yml`: reproduces both images (cache-validated).
- Port inventory: no collisions (8401/3400 unique to onb).
- onb image disk: backend 1.44 GB + frontend 270 MB + `onb-auth-service` 551 MB
  (**unused image** — compose built the inherited auth_service target; no container uses it).
- Note: onb_* uptime ~1h vs protected stacks' 9–26h — an uptime reset occurred during the
  window; I did not restart them. Recorded for transparency.

## 8. Claims audit (sample of material claims)

| claim | evidence | verdict |
|---|---|---|
| 712 passed / 18 skipped / 8 failed; 8 pre-existing | my run: identical 712/18/8; same 8 fail at base | TRUE |
| 400-file compare 0 diffs | their 400 had 0; my 619 found 1 (`d4de1ead`) | TRUE-as-measured; **substance FALSE** (a real regression exists) |
| "0 genuine false accepts (415 probes)" | 8 markerless csb→federal accepts can't be confirmed; 1 idbi→icici is a true mislabel | **UNSUPPORTED** |
| "no existing spec/detector/engine/flag/allowlist touched" | south_indian alias edited; INDUSINDBANK marker changed observable routing | **FALSE** |
| SERVE_BANKS unchanged | verified onb env + banks endpoint | TRUE |
| "csb folder ~6 files are Federal docs" | 8 federal-routed; **none contain 'federal' text** | **FALSE** (the count) / unresolvable ground truth |
| apgv wiring-blocked (detector absent) | no banks/apgv.json; APGV not in served list | TRUE |
| banks endpoint: 15 listed, 7 v2_served | re-verified authed | TRUE |
| Keycloak additive 3400 redirects | admin-API read: exactly the 4 URIs + 2 origins claimed | TRUE |
| 81 specs in image / sign-in OK / 0-diff compare | verified | TRUE |
| frontend vitest 43, tsc, eslint | re-ran: all pass | TRUE |
| "corpus mislabel" explanations generally | verified for idbi→icici + the 5 prompt-24 csb probes; not for the 8 markerless ones | mixed |
| per-bank det%s | mine within ±3pp except airtel_pb (denominator) | substantially TRUE |
| review/UNSPEC rows-behaviour claims | browser + API re-verified | TRUE |

## 9. NOT RUN / gaps

- **OCR resolution of the 8 csb→federal files** — prohibited; ground truth stays unresolved.
- Full-folder runs for `apgb/cosmos/deutsche/fincare_sfb/fino_pb/tmb` (NOT_POSSIBLE set) —
  only 1–3 files each; measured (all unsupported) but too small to characterize.
- onb stack restart-cycle test (the "~1h uptime" note) — not performed; only observed.
- Legacy-tier verdicts for fallback files — out of scope of my runner.
- Live mobile-device check — viewport emulation only.

## Reproduce

- Paytm regression: route sha8 `d4de1ead` (paytm folder) at base vs tip → base v2/VERIFIED,
  tip foreign_bank. Cause: `git show c43e8f1` (indusind spec registration).
- HDFC row-drop: e2e sha8 `0a05a1f7` via onb → download workbook → Transactions=38 vs
  engine rows=49 (verdict FAILED).
- csb→federal: sha8s `105adbdd 18f47088 22f26126 46ebec0b 528ee39a 930efd6d d24882cc
  d8eeb603` — accepted under federal spec with no bank markers in text.
