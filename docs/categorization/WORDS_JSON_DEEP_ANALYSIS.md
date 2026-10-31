# words.json — Deep Analysis & Improvement Plan

**Audience**: Claude (implementation handoff)
**Author**: Devin — corpus-mined analysis, 2026-10-31
**Scope**: `backend/words.json` (v5.0, 290 KB) + every consumer that actually reads it.

> **STATUS UPDATE (same day, post-handoff)**: v5.1 received from Claude and
> **implemented + verified**. words.json → v5.1 (40 entity groups, +4 new,
> +6 regex families); engine wiring done in `generic_bank.py`
> (`_build_pattern_sets` compiles 6 new regex families; `_classify_single`
> evaluates them after token checks, before entity lookup — except
> `payment_rail_patterns` which runs after entities so merchants still win);
> `PAYMENT_AGGREGATORS` added to `_rails` tier; `upi.*id.*`/`txn id.*`
> strip patterns bounded (were erasing whole narrations);
> `CRD DUES`/`card dues`/`cc dues` + `:self`/`self` + `chq:`/`chq dt` +
> `mb ft*`/`rdp|rde|nda` rails added in pass-2.
> Measured: **APGV 99.9, AU 100, BoM 98.9, CSB 99.2, Canara 84.0→100** (5-bank
> sample, 18.7k→9.7k txns subset). Remaining residuals are honest Others
> (person names, masked refs, `DEBIT`/`BY TRANS` fragments).

---

## 0. TL;DR

`words.json` is **alive but half-wired**. Only **3.5 of its 12 sections** are read by the
runtime classifier. The other 8.5 — including the 74-entity `entity_registry`, all of
`fuzzy_matching`, `direction_rules`, `behavior_context`, `confidence_scoring`,
`collision_resolution`, `feedback_learning`, and **7 of 15 `pattern_detection` keys**
(161 patterns, incl. the entire bounce-detection family) — are **dead config**: editing
them changes nothing. Meanwhile several token lists the classifier *does* check are
**hardcoded inside `generic_bank.py`**, bypassing words.json entirely.

Current corpus coverage after the v2 extraction fixes: **94–99.5% categorized** per
served bank. The residual 1–5% is a mix of (a) missing alias variants, (b) missing
pattern families, (c) dead config that was written but never wired, and (d) a small
honest floor of genuinely unclassifiable rows.

**The improvement goal is not "0% Others"** — it is *higher precision AND recall*:
add the right aliases/patterns with correct direction semantics, wire or delete dead
config, and keep the residual "Others" honest.

---

## 1. Which file is canonical

| Path | Version | Role |
|---|---|---|
| `X:/Airco Projects/wt-r5/backend/words.json` | **5.0** | **Live dev repo** → `main` → Railway. Edit this. |
| `X:/Airco Projects/Airco Insights fintech/backend/words.json` | 4.0 | Older clone (last commit `e8ab437`). **Do not edit.** |

Both repos share the same remote (`github.com/dscyrus07-dev/Airco-Fin-tech-insight.git`);
wt-r5 is ahead. The Docker image resolves words.json via `_find_words_json()`
(`backend/app/services/banks/_shared/generic_bank.py:269-274`):
`/app/words.json`, `/app/keywords.json`, `backend/words.json`, `words.json`,
then `samples/{bank}/output/words.json` fallbacks.

---

## 2. Runtime consumption map (the ground truth)

### Classifier chain

```
transaction → JsonRuleEngine(bank_key).classify()
  ├─ layer: bank-specific rules.json  (exists for 12 legacy banks only)
  │          unknown/rules.json used for v2-only banks
  │            ├─ debit_rules: 15 categories (keyword dicts)
  │            ├─ credit_rules: 4 categories
  │            ├─ upi_merchants: 23 entries
  │            └─ generic_fallback: True ───────────────┐
  └─ GenericRuleEngine(words.json).classify() ◄─────────┘
       → writes {category, confidence, source, matched_rule, matched_keyword}
```

`coverage_percent` = share of rows whose category does NOT start with `"Others"`
(computed frontend `ResultStep.tsx`, backend pipeline report). `Others Debit` /
`Others Credit` both count as unclassified.

### Section-by-section usage

| words.json section | Size | Consumer | Status |
|---|---|---|---|
| `metadata` | 11 keys | `get_statistics()` (version only) | informational |
| `category_normalization` | canonical_map + all_categories | `category_registry.py` — maps internal codes (`FOOD_EXPENSE`) → display names (`Food`) | **LIVE** |
| `text_normalization` | 7 keys | `GenericRuleEngine._build_normalization()` — strip_patterns + replace_rules | **LIVE** |
| `entity_interpretation` | **36 groups, ~950 aliases** | `_build_entity_lookup()` — the core dictionary | **LIVE** |
| `pattern_detection` | 15 keys | `_build_pattern_sets()` reads only 8 keys | **HALF LIVE** — see §4 |
| `entity_registry` | 74 entities, ~512 aliases | **nothing** | **DEAD** |
| `fuzzy_matching` | 6 keys | **nothing** | **DEAD** (declares `enabled: true`!) |
| `direction_rules` | 6 keys | **nothing** | **DEAD** |
| `confidence_scoring` | 5 keys | **nothing** — engine emits fixed 0.82 | **DEAD** |
| `collision_resolution` | 5 keys | **nothing** — engine uses insertion order | **DEAD** |
| `behavior_context` | 10 keys | **nothing** (`enabled: false` anyway) | **DEAD** |
| `feedback_learning` | 7 keys | **nothing** (`enabled: false`) | **DEAD** |

### Dead code inside generic_bank.py (mirroring dead config)

Built in `_build_pattern_sets()` but **never referenced** by `_classify_single()`:

- `self._interest_tokens` — interest credits only classify via hardcoded `_credit_rules` ("interest" keyword) or entities
- `self._atm_tokens` — ATM detection relies on `_debit_rules` hardcoded keywords
- `self._gst_tokens` — `["cgst","sgst","igst"," gst"]` — GST components never fire
- `self._ach_tokens` — `["ach d","ach debit","nach","ecs ","auto debit","standing instruction"]` — **the entire ACH/NACH/ECS family is dead code**, and corpus data shows it's the biggest residual family (§5)

Used: `_salary_tokens`, `_refund_tokens`, `_charge_tokens` (lines 480-485) — but
`_charge_tokens` list is too narrow (§5.2).

### Actual match order in `_classify_single()` (generic_bank.py ~440-540)

1. hardcoded `_debit_rules`/`_credit_rules` exact+pattern dicts
2. `_upi_merchant_map` (9 hardcoded entries, only when 'upi' in text)
3. `_salary_tokens` → Salary; `_refund_tokens` → Refund; `_charge_tokens` → Bank Charges
4. `_entity_hit(generic_tokens=False)` — **all ~950 words.json aliases**, sorted
   tiered: specific entities → rails → longest-first within tier
5. pattern sets: loan / refund / bill_payment / insurance / transfer / settlement / fuel_travel
6. `_entity_hit(generic_tokens=True)` — generic business-suffix tokens only
7. `upi_handle` substring / VPA regex → Transfer
8. → `Others Debit` / `Others Credit`

### Alias matching semantics (`_kw_in`, `_entity_hit`)

- aliases **> 4 chars**: plain substring match (`alias in description`)
- aliases **≤ 4 chars**: regex word-boundary `(?<![a-z0-9])alias(?![a-z0-9])`
- description is normalized first: lowercased, `text_normalization.strip_patterns`
  removed, `replace_rules` applied (e.g. `@` → `at`)
- direction: each entity has `credit.category` + `debit.category`; wrong-side hits
  produce the side's mapped category (e.g. `swiggy` credit → `MERCHANT_PAYOUT`)

---

## 3. entity_interpretation structure (the live dictionary)

36 groups, ~950 aliases. Each alias → `{credit: {category, group, priority, confidence}, debit: {...}}`.

| Group | Aliases | Notes |
|---|---|---|
| BANKS | 84 | rail entities — generic `Transfer` categories |
| PAYMENT_PLATFORMS | 59 | |
| UPI_HANDLES | 59 | VPA suffixes |
| ECOMMERCE_PLATFORMS | 63 | |
| OTA_MERCHANTS | 56 | |
| NBFC_LENDERS | 48 | `bajaj finserv`, `bajaj finance`, `bajaj housing` — **not `bajajfin`** |
| PAYMENT_GATEWAYS | 22 | |
| BUSINESS_ENTITIES | 19 | generic suffixes (GENERIC tier) |
| CREDIT_CARD_PAYMENTS | 17 | |
| GENERIC_LENDER_TOKENS | 10 | GENERIC tier |
| DELIVERY_PLATFORMS | 13 | |
| TERMINAL_SETTLEMENTS | 6 | |
| INSURANCE_TRANSACTIONS | 5 | |
| SALARY_PAYMENTS / ATW_TRANSACTIONS / NEFT_TRANSACTIONS | 1 each | |
| CURATED_* (18 groups) | ~450 | v5.0 additions — merchants/utilities/tax/insurance/charges. Credit side mostly maps to `Refund`/`Insurance Claim`/`Investment Returns` (income-ish); debit side maps to spend categories |

Category codes are internal (`FOOD_EXPENSE`, `BANK_TRANSFER`) → normalized to display
names via `category_normalization.canonical_map` (145 declared categories).

---

## 4. pattern_detection — half dead

| Key | n | Used by `_build_pattern_sets`? |
|---|---|---|
| `upi_handle` | 64 | ✔ |
| `loan_patterns` | 10 | ✔ |
| `refund_patterns` | 4 | ✔ |
| `bill_payment_patterns` | 8 | ✔ |
| `insurance_patterns` | 31 | ✔ |
| `transfer_patterns` | 8 | ✔ |
| `settlement_patterns` | 7 | ✔ |
| `fuel_travel_patterns` | 10 | ✔ |
| **`card_patterns`** | 6 | ✖ dead |
| **`business_vendor_patterns`** | 23 | ⚠ live in `finbit_analytics` (vendor-name extraction), not the classifier |
| **`outward_bounce_patterns`** | 50 | ⚠ live in `finbit_analytics` (bounce metrics), not the classifier |
| **`inward_bounce_patterns`** | 30 | ⚠ live in `finbit_analytics`, not the classifier |
| **`bounce_penalty_patterns`** | 21 | ⚠ live in `finbit_analytics`, not the classifier |
| **`credit_card_patterns`** | 26 | ✖ dead |
| **`salary_patterns`** | 11 | ✖ dead |

> **Correction (v5.1 review)**: the bounce family + business_vendor patterns ARE
> consumed — by `finbit_analytics.py` for bounce/vendor metrics (`α1.py:150-152`,
> `:305`), not by the transaction classifier. They were wrong to call fully dead:
> they're dead *for categorization* but live for analytics. `card_patterns`,
> `credit_card_patterns`, `salary_patterns` remain read by nothing.
>
> Bounce classification for txn categories exists ONLY via `unknown/rules.json`
> (`Bounce` debit_rule, `Inward Bounce` credit_rule) for banks routed through
> the unknown rule layer.

---

## 5. Corpus-mined residuals — what actually lands in "Others"

Probe: per-bank v2 extraction + classification on real corpus (12 files/bank cap,
`probe_others_all.py`). Numbers are row counts on the sampled subset.

### 5.1 Per-bank baseline (sampled)

| Bank | rows | cls% | others | empty | rej |
|---|---|---|---|---|---|
| APGV | 5431 | 99.4 | 31 | 0 | 0 |
| AU SFB | 4256 | 99.3 | 31 | 0 | 0 |
| Axis | 4621 | 98.4 | 74 | 2 | 6 |
| Bandhan | 5142 | 96.6 | 175 | 117 | 0 |
| BoB | 207 | 99.5 | 1 | 0 | 11 |
| BoI | 1091 | 97.6 | 26 | 0 | 7 |
| BoM | 3592 | 96.3 | 133 | 4 | 0 |
| CSB | 4318 | 94.3 | 246 | 0 | 2 |
| Canara | 1134 | 83.7 | 185 | 0 | 9 |
| Airtel/APGB | 0 | — | 0 | 0 | all | (bank_unconfirmed — by design, manual confirm path) |

(Full-corpus scan `banks.txt` continues in background; numbers above are the
mining-probe sample, sufficient for pattern ranking.)

> **Extraction-gap alert**: `DBS Bank` scored **0.6% with 1482/1492 empty
> narrations** — its layout drops description text entirely, same disease class
> as the narration-pad fixes already shipped (`9fb0d1c`). That is an
> **extraction** defect, NOT a words.json gap — words.json cannot categorize
> text it never receives. DBS needs a `band_left_pad`/layout fix before any
> dictionary work shows up in its coverage. Same rule for Canara (83.7%): its
> Others are dominated by `CHQ:` cheque fragments + UPI-hash narrations —
> verify narration completeness before dictionary changes.

### 5.2 Residual families, ranked by impact

| Family | Examples (real narrations) | Rows | Root cause | Fix class |
|---|---|---|---|---|
| **Cash deposit/self** | `CASH:SELF` (44), `DEPOSIT,CASH/N/SELF` (13), `TO CASH` , `CD SELF`, `CD-SELF`, `CASHDEPOSIT-XXX-MIYAPUR` | ~80+ | no cash-deposit pattern/entity at all | new pattern set + entity group `CASH_OPERATIONS` → `Cash Deposit`/`Cash Withdrawal` |
| **ACH/NACH/ECS mandates** | `ACH DR 10TP…`, `ACH IBGE CHITS`, `ACH BD-WHITEOAK`, `ACH C-POWERGRID`, `ACH D-IDFCFIRSTBANK`, `ECS MANDATE`, `APYN..INSTALLM` | ~60+ | `_ach_tokens` built but never used (dead code) | **wire dead code** + extend tokens |
| **Bank/SMS/fee charges** | `MAINTENANCE CHG` (16), `SMS_ALERT_CHARGE_*` (9), `LF CHG CA AC` (6), `MANDATE REG CHG: BKIDN` (5), `CHQ BK ISSUE CH`, `INSTAALERTCHG`, `CMS/N/SMSOTP` | ~50+ | `_charge_tokens` too narrow — lacks `chg`, `charge`, `fee`, `insta alert`, `sms alert`, `mandate reg`, `cheque book` | extend `_charge_tokens` (better: move to words.json, §6.3) |
| **Payment-aggregator prefixes** | `FN/SHP/N/ UNIQUESHOES_BHARTIPAY SERV` (39+), `IFN/EPAY/400CDDN/ BAJAJFIN`, `BAN/PAYMENT/ IFT/PBN/ONE97` (Paytm rail), `FBA/PAYMENT/` | ~80+ | rail prefix `FN/SHP`, `IFN/EPAY`, `BAN/PAYMENT` unknown; merchant embedded mid-string | new `payment_rail_patterns` family + aggregator entities (bharatpay, bhartipay, epay, payu, rzp) |
| **Fused lender forms** | `BAJAJFIN_BFN_662-1145_N` (109 in earlier probe), `BAJAJFIN` in IFN/EPAY | ~110+ | alias `bajaj finserv`/`bajaj finance` needs space; text is `bajajfin` | add fused aliases: `bajajfin`, `bajajfinser`, `bfl`, `bfsl` |
| **UPI reversal/npa** | `UPI NPAID VIA CRED` (22), `UPIR NUPIDEBITREV` (8) | ~30 | reversal markers `NP`, `UPIDEBITREV` unmatched | pattern: `upi.*(np|rev|revers)` → Refund/Reversal |
| **Cheque operations** | `DR THRU CHQ`, `CNRBN CHQ:`, `WTHDRL,DD ISSUED`, `CHQ:` | ~15 | no cheque/DD family | new group `CHEQUE_OPERATIONS` → `Cheque Payment`/`DD Issuance` |
| **Interest credit/debit** | `SAV INCREASE INT PAID`, `CR INT DB`, `INT.COLL:` | ~8 | `_interest_tokens` dead | wire dead code + `int coll`, `int paid` tokens |
| **Card dues recovery** | `CRD DUES RECOVERY / NXXX` | 3 | `credit_card_patterns` dead | wire or port to entity |
| **Medical/hospital** | `ANKURA HOSP` | 2 | CURATED_MEDICAL lacks `hosp`, `hospital`, `clinic` aliases | alias additions |
| **Gaming** | `RUMMYCU` | 2 | no gaming group | CURATED_GAMING entity group |
| **Employer/govt credits** | `ACH C- POWERGRIDCORPORATI` | 7 | ACH credits unhandled | wire `_ach_tokens` credit side |
| **Blank narrations** | Bandhan 117 rows `D|`/`C|` empty | 117 | extraction or genuinely blank rows | separate metric — do NOT force-categorize |
| **Reference-only/VPA** | bare `xyz@ybl`, `Q0JBYS1-NVAT-LPQ2AW7` | ~30 | irreducible | legitimate Others — leave |

### 5.3 Collision/false-positive risks to respect

- `bajaj` alone must NOT match "Bajaj Nagar" (place) — keep fused forms `bajajfin*`, don't add bare `bajaj`
- `finance`/`finserv` alone too broad — only inside lender group with boundary checks
- `hospital`/`medical` fine; `medic` too short (matches "medicine", "paramedic")
- `chg`/`charge`/`fee` — must remain debit-side Bank Charges; a *credit* "charge reversal" is a Refund → direction handling required
- `cash` alone is dangerous ("cashback") — use `cash deposit`, `cd self`, `cash:self`, `deposit,cash`, `to cash:` forms
- `self`/`n/self` — part of cash-deposit phrases only, never standalone
- `int`/`inst`/`rev`/`np` — all ≤4 chars → word-boundary regex already protects, but add them only inside longer patterns
- adding `bank`/`payment`/`transfer` aliases is pointless (already covered) and dangerous

---

## 6. Improvement plan for Claude (ordered)

### P0 — Wire the dead code (no schema change, pure engine)

1. **`generic_bank.py`: use `_ach_tokens`, `_interest_tokens`, `_atm_tokens`, `_gst_tokens`**
   in `_classify_single()` — they're built at lines 372-379 and never called.
   Suggested order: ach → mandate/auto-debit family; interest → Interest Income (credit)
   / Interest Charges (debit); atm → ATM Withdrawal; gst components → append or
   standalone `GST Charges`. Each needs a direction rule.
   File: `backend/app/services/banks/_shared/generic_bank.py`, `_classify_single()` ~440-540.

2. **Move `_charge_tokens`/`_salary_tokens`/`_refund_tokens`/`_ach_tokens`/`_interest_tokens`/
   `_atm_tokens`/`_gst_tokens`/`_upi_merchant_map`/`_debit_rules`/`_credit_rules` out of
   hardcoded dicts into words.json** — new `pattern_detection` keys (e.g.
   `charge_patterns`, `salary_keyword_patterns`, `atm_patterns`, `ach_patterns`,
   `gst_patterns`, `interest_patterns`) so maintainers edit config, not code. Keep
   hardcoded lists as fallback defaults during migration.

3. **Wire `pattern_detection.salary_patterns` + `credit_card_patterns`** — they exist
   in the file (37 patterns) and duplicate partial intent of dead token lists.

### P1 — High-impact dictionary additions (words.json only)

4. **`entity_interpretation` additions** (validated against §5.2):

   - New group `CASH_OPERATIONS`: `cash deposit`, `cash:self`, `cd self`, `cd-self`,
     `cashdeposit`, `deposit cash`, `self deposit`, `to cash:paid`, `cash wdl`,
     `cash withdrawal` → debit `Cash Withdrawal`, credit `Cash Deposit`
   - `NBFC_LENDERS` aliases: `bajajfin`, `bajajfinser`, `bfl`, `bfsl`, `tatafin`, `tatacap` (fused forms)
   - New group `PAYMENT_AGGREGATORS`: `bhartipay`, `bharatpay`, `epay`, `payout to customer`,
     `fba/payment`, `ban/payment` rail prefixes as patterns (see #5)
   - `CURATED_MEDICAL`: `hospital`, `hosp`, `clinic`, `diagnostics`, `pathlab`, `pharmacy`, `apollo`, `medplus`
   - New group `CURATED_GAMING`: `rummycircle`, `rummycu`, `dream11`, `winzo`, `rummy`,
     `pokerbaazi`, `fantasy` → debit `Gaming`/`Entertainment`
   - `CHEQUE_OPERATIONS` (or pattern set): `thru chq`, `chq paid`, `dd issued`,
     `dd issue`, `cheque book`, `chq:` → `Cheque Payment` (debit) / `Cheque Deposit` (credit)

5. **`pattern_detection` additions**:
   - `ach_mandate_patterns`: `ach\s+[cd]`, `ach\s+dr`, `nach`, `ecs\s+mandate`,
     `auto.?debit`, `standing\s+instruction`, `apyn.*install`, `installm` —
     debit → `Loan EMI`/`Mandate Debit`, credit → `Transfer`
   - `charge_patterns` (extend existing charge handling): `\bchg\b`, `charge`,
     `sms.?alert`, `insta.?alert`, `mandate reg`, `cheque book`, `lf chg`,
     `maintenance chg`, `amt chg`, `fee` (≥5 chars or boundary-safe) → `Bank Charges` (debit only)
   - `reversal_patterns` (extend refund): `upi.*(np|rev|reversal)`, `debitrev`,
     `npaid.*cred`, `reversal` → `Refund`
   - `payment_rail_patterns`: `fn/shp`, `ifn/epay`, `ban/payment`, `pbn/one97`,
     `ybs ift` — credit → `Transfer`/`Payout`, debit → `Transfer`
   - `cheque_patterns`: `dr thru chq`, `chq dep`, `dd issued`, `dd issue`
   - `interest_patterns`: `int.?coll`, `int paid`, `cr int`, `int db` —
     credit → `Interest Income`, debit → `Interest Charges`

6. **Extend `_charge_tokens` immediately** (if #2 deferred): add `charge`, `chg`,
   `sms alert`, `insta alert`, `mandate reg`, `fee`, `maintenance`.

### P2 — Structural fixes

7. **Decide the dead sections' fate** — either:
   - (a) **Implement**: `entity_registry` as alias-validation layer (all
     `entity_interpretation` aliases must resolve to a registered entity +
     canonical category); `collision_resolution` to break ties by priority instead
     of insertion order; `confidence_scoring` weights actually applied to the
     emitted `confidence` field; `direction_rules.interpretation_order` made real;
     `fuzzy_matching` for OCR-grade noisy text (local OCR only — see §7).
   - (b) **Or delete/mark**: prefix each with `_deprecated_` or add
     `"implemented": false` markers so maintainers stop editing dead config.
   Recommend (a) for `collision_resolution` + `confidence_scoring` (small wins,
   already declared), (b) for `behavior_context` + `feedback_learning` (explicitly
   disabled, need infra that doesn't exist).

8. **Direction-aware charge reversal**: a credit-side `charge`/`chg` hit should map
   to `Refund`/`Fee Reversal`, not `Bank Charges`. Add per-pattern direction
   overrides in words.json (pattern entries already support
   `{credit: {...}, debit: {...}}` shape in entity_interpretation — extend the same
   shape to pattern_detection entries or add `direction: debit_only` flag).

9. **`entity_registry` ↔ `entity_interpretation` consistency check**: 74 registered
   entities vs 36 groups — write a validator that flags (a) aliases in
   entity_interpretation with no entity_registry entry, (b) registry entities with
   zero live aliases, (c) canonical categories in entity_registry not present in
   `category_normalization.canonical_map` (metadata claims 145 categories — verify).

### P3 — Guardrails & measurement

10. **Split metrics**: report `extraction_empty` (blank narration — Bandhan 117)
    separately from `others` (narration present but unmatched). Never let extraction
    fixes masquerade as categorization fixes.

11. **Precision regression set**: before adding any alias/pattern, build a small
    corpus of narrations that MUST stay in their current category (collision tests —
    §5.3 list + `cashback`, `bajaj nagar`, `medicine`, `paramedic`, `interest free`,
    `charge reversal` credit rows). Re-run after each batch.

12. **Coverage re-measure loop**: after each batch, re-run `probe_others_all.py`
    (12 files/bank) and the full `banks.txt` corpus scan; rank remaining Others
    by frequency; iterate. Target: move residual Others from ~1-5% to ~0.5-2%,
    treating coverage and precision as separate gates.

---

## 7. Cross-cutting constraints

- **Do not** add aliases that would let OCR/noisy text false-positive — the
  Universal OCR service stays local-only; production OCR variables must remain
  unset. If `fuzzy_matching` is ever wired, gate it behind the OCR path only.
- **Bank-specific `rules.json` (12 banks) fires BEFORE words.json.** A bank can
  already have a `Bounce`/`Charge` rule — changes to words.json won't alter those
  banks' behavior for overlapping patterns. Verify layer order per bank before
  blaming the dictionary.
- **`unknown/rules.json` has its own `debit_rules`/`credit_rules`/`upi_merchants`
  (23 entries)** that fire before the generic fallback for v2-only banks — a
  narrower second dictionary. Consider syncing its merchant list with words.json
  `entity_interpretation` (or removing duplication) — currently `swiggy` exists in
  both places with potentially different categories.
- **Categories must exist in `category_normalization.canonical_map`** — new
  internal codes (e.g. `CASH_DEPOSIT`, `GAMING`) need canonical display names or
  they surface raw in the UI.
- **Keep `Others` honest**: bare VPA handles, pure reference strings, and genuinely
  blank narrations should remain unclassified — a wrong category is worse than
  `Others`.
- **Rejection ≠ categorization failure**: `bank_unconfirmed`/`foreign_bank`/
  `no_layout` files (Airtel, APGB, Paytm mPassBook) never reach classification —
  they follow the manual-confirm path by design.

---

## 8. Quick reference — files

| File | Role |
|---|---|
| `backend/words.json` (wt-r5, v5.0) | THE dictionary — edit this |
| `backend/app/services/banks/_shared/generic_bank.py` | GenericRuleEngine — consumption logic, `_classify_single()` ~440-540, dead token lists 370-379, hardcoded dicts 547-578 |
| `backend/app/services/banks/_shared/category_registry.py` | `canonical_map` consumer — category code → display name |
| `backend/app/services/banks/unknown/rules.json` | v2-bank rule layer: 15 debit + 4 credit categories + 23 upi_merchants + `generic_fallback: true` |
| `backend/app/services/banks/{bank}/rules.json` | 12 legacy banks' own rule layers (fire first) |
| `backend/app/services/pipeline/classification/rule_engine.py` | layer orchestration + generic_fallback dispatch |
| `C:/Users/admin/AppData/Local/Temp/probe_others_all.py` | mining probe — per-bank coverage + Others pattern ranking (12 files/bank) |
| `C:/Users/admin/AppData/Local/Temp/out/others_all.txt` | live mining output |
| `C:/Users/admin/AppData/Local/Temp/out/banks.txt` | full-corpus scan (background, ~5000 PDFs) |

## 9. Acceptance criteria for the Claude work

- [ ] `_ach_tokens`/`_interest_tokens`/`_atm_tokens`/`_gst_tokens` evaluated in `_classify_single` (or lists moved to words.json and evaluated there)
- [ ] ≥5 new pattern_detection keys wired: `ach_mandate_patterns`, `charge_patterns`, `reversal_patterns`, `payment_rail_patterns`, `cheque_patterns`
- [ ] `CASH_OPERATIONS`, `PAYMENT_AGGREGATORS`, `CURATED_GAMING`, `CHEQUE_OPERATIONS` entity groups added with direction-correct categories
- [ ] `bajajfin`/`bfl` fused aliases added; **no bare `bajaj`/`finance`/`cash`/`self` aliases**
- [ ] `_charge_tokens` covers `chg`/`charge`/`fee`/`sms alert`/`insta alert`/`mandate reg`/`maintenance`/`cheque book`
- [ ] New categories registered in `category_normalization.canonical_map`
- [ ] Precision regression set passes: `cashback`, `bajaj nagar`, `medicine`, `paramedic`, `charge reversal` (credit), `interest free` all keep correct categories
- [ ] Re-run `probe_others_all.py`: residual Others ↓ from ~5% to ≤2% on sampled corpus with zero precision regressions
- [ ] Dead sections marked `implemented: false` OR wired — no silently dead config remains
