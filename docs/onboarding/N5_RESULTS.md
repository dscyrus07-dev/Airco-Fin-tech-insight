# N5 RESULTS — bank wave on N1–N3 engine capabilities

Branch `devin/n5-bank-wave`, base `devin/n3-engine-grouped` tip `f81095e`.
N4 audit verdicts: all ACCEPT — no revert branches merged.
Authorization: LayoutSpecs, detector entries, tests, docs, wiring only. No
engine/checks/registry-logic/verdict/guard/serve changes. `pnb` +
`bank_of_maharashtra` restricted to layout variants with zero-diff proof.

Verdict vocabulary: VERIFIED / REVIEW / FAILED; fallback = `no_layout` /
`foreign_bank` / `bank_unconfirmed`. Cause classes: A variant · B boundaries ·
C marker · D corpus/scanned/glyph · E no printed anchors · F engine.

## Per-bank results

| bank | files | before | after | Δ | audit | xbank | status | sha |
|---|---|---|---|---|---|---|---|---|
| federal | 291 | 228V/36R/13F/14fb | 232V/39R/6F/14fb | +4V +3R -7F | 4/4 clean | — | SHADOW_ONLY (det 95.2%) | 67968b6 |
| standard_chartered | 196 | 168V/23F/5fb | 171V/2R/18F/5fb | +3V +2R -5F | 3/3 clean | — | SHADOW_ONLY | d26d9e0 |
| indusind | 129 | 92V/6R/5F/26fb | 92V/28R/6F/3fb | +22R -23fb | 40/40 clean | 0/417 | SHADOW_ONLY (det 97.7%, V 71%) | 9f3a252 |
| dbs | 131 | 116V/9R/5fb | 116V/11R/3fb | +2R -2fb | — | 0/x | SHADOW_ONLY | 7e4b9a5 |
| idbi | 83 | — | 15V/22R/28F/18fb | 0 | — | — | SHADOW_ONLY | e81b00f |
| yes | 92 | — | 34V/34R/20F/4fb | 0 | — | — | SHADOW_ONLY | 7959842 |
| central_bank | 34 | — | 2V/25R/5F/2fb | +1R (`459f15b8` via N1 L4) | — | — | SHADOW_ONLY | 38ebc04 |
| equitas_sfb | 36 | — | 4V/23R/5F/4fb | 0 | — | — | SHADOW_ONLY | fa2bde6 |
| ujjivan_sfb | 32 | — | 20R/4F/8fb | 0 | — | — | SHADOW_ONLY (false-accept resolved at tip) | fa2bde6 |
| hsbc | 33 | — | 22R/9F/2fb | rows now read (was no_layout) | — | — | SHADOW_ONLY | cbf3f14 |
| kvb | 71 | — | 3V/1F/67fb | 0 | — | — | SHADOW_ONLY | cbf3f14 |
| dcb | 15 | — | 7V/8F | 0 | 7/15 clean (anchor-assoc) | — | SHADOW_ONLY | c351a80 |
| bandhan | 17 | 5V/5R/7fb | 8V/8R/1F/0fb | +3V +3R -7fb | 3/3 clean | 0/416 | SHADOW_ONLY | 906688b |
| uco | 9 | — | 3R/6F | 0 | — | — | SHADOW_ONLY | fc3c618 |
| dhanlaxmi | 11 | 9R/2fb | 11R | +2R | totals MATCH | 0/416 | SHADOW_ONLY | fc3c618 |
| csb | 16 | — | 1V/10R/3F/2fb | 0 | 1/1 clean | — | SHADOW_ONLY | fc3c618 |
| ippb | 5 | — | 4R/1fb | 0 | — | — | SHADOW_ONLY | fc3c618 |
| pnb | 82 | 81R/1fb | 81R/1fb | 0 (no change) | — | — | unchanged (served REVIEW-only) | 98fe2a5 |
| bank_of_maharashtra | 25 | 24V/1R | 25V | +1V | audited clean | — | improved (restricted, zero-diff) | 98fe2a5 |

## Changes shipped

- **federal** `67968b6`: `balance_optional` + `continuation_amounts` on L1/L3
  (charge-back rows print without balance cells; wrapped date-line/amount-line
  records). GRAND TOTAL clipped-decimal files stay FAILED (glued squash is
  genuinely ambiguous — class D). 12 unbranded exports stay fallback — correct
  refusal.
- **scb** `d26d9e0`: `balance_optional` on L1/L2. Remaining FAILEDs are
  duplicated-page PDFs and the undated-NACH continuation swallow (class F);
  4 `no_layout` files need detector head-scan past `6-3-1090`-style street
  addresses (engine, class F).
- **indusind** `9f3a252`: new `INDUSIND_LAYOUT_4` (`Date|Type|Description|
  Debit|Credit|Balance` app-export variant, 2-line header, `Aug 1, 2022`
  comma dates, newest-first) + `ifsc_re=INDB` own-evidence on all 4 specs
  (IFSCCODE sits in the page-1 account block; foreign hits were narration
  counterparties only).
- **dbs** `7e4b9a5`: L4 for yearless `02 Jul` + `From..To` period balance-less
  variant (`year_from_period`); N2 `merge_statements` absorbed multi-account
  docs.
- **bandhan** `906688b`: L3/L4 for `INR`-prefixed label:value export family
  (`Statement Summary` + bare-value line, `Dr / Cr` squashed title) +
  `ifsc_re=BDBL` on all specs (rescues files whose customer address contains
  `BEHIND AXIS BANK`).
- **dhanlaxmi** `fc3c618`: L3 (`Date|Cheque/RefNo|Description|Debit|Credit|
  Balance`, B/F row counted in printed totals — totals line is the independent
  verifier; REVIEW ceiling: no opening/closing labels).
- **bom** `98fe2a5`: L3 `dates_monotonic_expected=False` — the bank prints
  value-dated rows out of order in posting order while the balance chain flows
  in print order. Zero-diff proof: 25 files, 1 named diff (`6f062db1`
  REVIEW→VERIFIED), audited clean (281/281 lines, anchors match exactly).

## Unchanged banks (all residuals classified)

- **idbi**: FAILEDs = real print gaps (unread=0, class D) + all-zero B/F rows
  that hit `opening_row_balance_only` before `zero_amount_is_empty` (class F);
  `bank_unconfirmed` files carry no IDBI evidence (class C).
- **yes**: 20 FAILED = shared-balance charge pairs + B/F balance printed in the
  wrong money cell (class D/F). `008a966b` already VERIFIED via N1 3-line spec.
- **central_bank**: glued-token files NOT_POSSIBLE (class D); wrapped family
  routed by N1 L4.
- **equitas_sfb**: `baf15ad9` single-money-column no-side-marker NOT_POSSIBLE
  (class D/F).
- **ujjivan_sfb**: prior detector false-accept verified resolved at tip.
- **hsbc**: rows now extract (was `no_layout`) but boundary rows carry
  discontinuous balances + a both-sides schema row → honest FAILED (class D/F).
- **kvb**: 67 files cid-garbage `(cid:NN)` — class D.
- **dcb**: summary opening/closing belongs to a different sub-account than the
  parsed section — needs per-segment anchor association (class B, engine).
- **uco**: clipped summary decimals disagreeing with rows, missing deposit
  cells, jumbled date order — class D/F.
- **csb**: interleaved-line defects and stray truncated dates — class F; two
  files carry zero CSB evidence → honest `bank_unconfirmed` (class C).
- **ippb**: 5-value summary row has an unmodeled txn-count field → REVIEW
  ceiling (class F); `5128847f` cid-garbage (class D).
- **pnb**: sole fallback `4eb17de5` is a WhatsApp T&C document — correct
  refusal; 81 REVIEW is the honest ceiling (no printed anchors on these
  variants). No spec/marker change.

## Gates

- Regression (1,099-file corpus): mid-wave checkpoint 1,099/1,099 identical;
  final at HEAD pending → see DONE line.
- Cross-bank: 0 foreign accepts (416 + 417 + pooled probes).
- Suites: 500 green at bandhan commit; re-run at end.
- No served-bank state changes made; `bank_status.json` untouched.

## bank_status.json candidates (proposed only — not shipped)

- `federal` — shadow; promote only after brand-marker coverage for the 12
  unbranded exports (det currently 95.2%).
- `indusind` — shadow; VERIFIED share 71% < 80% gate.
- `standard_chartered`, `bandhan`, `dhanlaxmi`, `csb`, `dbs` — shadow;
  REVIEW-heavy yield is honest but below serve threshold.
- All others — remain shadow/legacy per existing states.
