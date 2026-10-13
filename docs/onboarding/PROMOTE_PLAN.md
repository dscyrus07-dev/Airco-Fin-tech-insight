# PROMOTE_PLAN — banks nearest to READY_TO_SERVE (prompt 27, Part B)

Measured on `devin/promote-1 @ c550bac` (runA shadow data re-derived; 1,738 files / 30
folders). Gates: det 100% on readable files · 0 cross-bank accepts · ≥90% of hold-out
text files VERIFIED-or-REVIEW-with-rows · ≥80% VERIFIED where printed balances exist ·
clean spec-independent audit. Fixes must live inside the bank's own spec/detector entries.

## Excluded up front (gap not fixable in a bank's own spec/detector)

| bank | why excluded |
|---|---|
| iob, south_indian | REVIEW_ONLY by design — no printed balance anchors |
| csb | corpus problem: 8 markerless docs accepted under federal spec; ground truth unresolvable without OCR |
| apgv | detector intentionally absent; APGB↔APGV collision unchecked — high-risk, not a "nearest" gap |
| kvb | det 5.4% — pre-existing detector weakness, massive gap, not onboarding-introduced |
| dhanlaxmi | needs engine capability (balance-on-continuation) — engine gap, park |
| hsbc | corpus problem: 66/103 files image-only |
| ippb | corpus too thin (5 files) to evidence a promotion |
| federal, indusind, standard_chartered, idbi, ujjivan_sfb, yes, central_bank, equitas_sfb | gap too large for the timebox (22–113 missing layout variants and/or deep detector/FAILED gaps) |
| pnb (borderline) | 30 no_layout files = large variant gap; statements genuinely anchorless (1/25 anchor phrases) → REVIEW ceiling; kept as 5th pick only if variant yield math works |

## Ranked shortlist (smallest fixable gap first)

### 1. au_sfb — smallest gap
- Now: det 94.1% (16/17), v2 14 (all VERIFIED), yield 82.4%, audit clean.
- Gap: 3 `no_layout` files (`4e1287dd` no det, `7b2023ab` `f50a0f50` det=au_sfb) —
  almost certainly 1–2 missing layout variants.
- Plan: fingerprint the 3 files; if a distinct header shape exists, add `AU_LAYOUT_2`
  (and a marker tweak only if the undetected file lacks it). Target: det 100%, yield ≥90%.

### 2. dbs — largest corpus among near-ready, single-variant fixes
- Now: det 98.5%, yield 84.8% (118/132), 6 FAILED `chain+side`, 14 non-v2 (13 `no_layout`, 1 `NO_ROWS`).
- Gap: missing variants for ~13 files + 6 chain/side failures; VERIFIED=0 (self-derived
  chain). Anchor phrases exist in 25/25 sampled REVIEWs but amounts print on a *different
  line* — needs bounded next-line-tolerant anchor regexes inside the DBS spec (allowed:
  spec change) or is an engine gap if even that cannot express it.
- Plan: fingerprint the no_layout cluster (likely 1 dominant uncovered shape), diagnose the
  6 chain/side failures (column side-detection), then attempt spec-level anchors. If anchors
  are not expressible at spec level → park as engine gap, keep whatever yield improvement lands.

### 3. bank_of_maharashtra — det already 100%, variant + anchor gaps
- Now: det 100%, yield 63.0% (17/27), Vshare 47% (8V/9R).
- Gap: 10 `no_layout` files (all det=correct bank) → missing variants; REVIEWs all carry
  anchor phrases (9/9) — spec has `opening/closing_balance_re` but amounts print on adjacent
  lines → anchor regexes may need next-line tolerance.
- Plan: add variant(s) for the 10 files + try spec-level anchor fix. Yield 63→90 needs ~8 more routed.

### 4. bandhan — small unrouted set, anchors present
- Now: det 94.4%, yield 55.6% (10/18), 5V/5R.
- Gap: 5 `no_layout` + 3 `foreign_bank` refusals. The 3 refused files contain 8–16 other-bank
  markers each → multi-bank/mislabeled documents, correctly refused — real gap is the 5 no_layout.
- Plan: variants for the 5; anchor phrases present in 5/5 REVIEWs (next-line amounts again).
  Hard: yield 55.6→90 on 18 files means ~7 more V|R out of 8 unrouted.

### 5. pnb — conditional (see exclusion note above)
- Now: det 98.8%, yield 65.1% (56/86), all REVIEW (anchorless content).
- Plan only if fingerprints of the 30 no_layout files collapse to ≤2 shapes and routing them
  yields ≥90% V|R with rows. Anchorless ceiling means the 80% VERIFIED clause is vacuous.

### 6. airtel_pb — thin corpus, schema errors may be spec-fixable
- Now: det 85.7%, yield 0 (4/4 routed files FAILED `schema errors: 1–2`), 3 no_layout.
- Plan: diagnose the 1–2 edge rows per file that fail schema; if it's a column-boundary
  issue → spec fix converts FAILED→V|R. Corpus (7 files) is thin but > the NOT_POSSIBLE floor.

### 7. uco — chain/side failures, small corpus
- Now: det 100%, yield 44.4% (4/9 REVIEW, 3 FAILED `chain+side`, 2 unrouted).
- Plan: inspect whether chain/side failures are a column misclassification (spec-fixable)
  or genuine balance anomalies (park). Small corpus limits confidence.

### 8. dcb — investigate then likely park
- Now: det 100%, yield 46.7% (7V, 8 FAILED — 7 `reference failed` + 1 schema).
- The `reference failed` = printed reconciliation mismatch on a multi-account fingerprint —
  likely a real statement-structure issue needing engine support. Plan: confirm quickly; if
  engine gap → park with generic description, use the slot for pnb/bandhan depth instead.

## Execution order

`au_sfb → dbs → bank_of_maharashtra → bandhan → pnb(conditional) → airtel_pb → uco → dcb`,
one commit per bank, time-boxed; cross-bank run + audit + fast checks before every commit.
Any fix harming another bank → revert, park. A bank that clears every gate is reported as
`READY_TO_SERVE_CANDIDATE` only — the final word belongs to an independent check.
