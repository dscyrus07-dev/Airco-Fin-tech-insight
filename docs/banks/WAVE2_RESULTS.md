# Wave 2 — the long tail

Scope: every remaining bank folder not covered by Wave 1, excluding Bank of India
(legacy parser), Human Verification, Non_Bank_Documents, Other_Unknown, Others and
Unknown. Folder census: `comparison/wave2/BANK_LIST.md` (base `devin/wave1` tip
`0229019`, 14,445-file corpus). Every folder ends in exactly one disposition:
**ONBOARDED**, **REFUSED-CORRECTLY** or **INSUFFICIENT-DATA**.

## Onboarded banks

| # | Bank | Commit | Layout(s) | In-scope verified | G2 | G3 forced | G6 route |
|---|------|--------|-----------|-------------------|----|-----------|----------|
| 1 | Central Bank of India | `76af602` | `cbi_postdate_*` + `cbi_postdate_*_transaction_*` | L1 partial (8/10 hold-out; isolated damaged rows stay FAILED), L2 3/3 | 15/15 MATCH | 0 foreign | 24 VERIFIED `region`, residuals `no_layout`/`locked`/`scanned` |
| 2 | Equitas SFB | `6c6ed43` | `equitas_date_referencenochequeno_narration_*` | 9/12 hold-out (isolated chain breaks = damaged rows) | 15/15 MATCH | 0 foreign | 23 VERIFIED, residuals refused |
| 3 | City Union Bank | `fb411fa` | `cub_date_description_*` + `cub_date_particulars_*` | 31/31 + 6/6 | 15/15 + 6/6 MATCH | 0 foreign | detector-blocked (see below) |
| 4 | Ujjivan SFB | `264314b` | `ujjivan_date_particular_chqrefno_*` | 8/10 hold-out (page-edge clipped dates = source damage) | 15/15 MATCH | 0 foreign | 20 VERIFIED `document`, 9 `no_layout` |
| 5 | Bank of Maharashtra | `b9fd756` | `bom_*_channel` + `bom_date_type_*_channel` | 11/11 + 6/6 | 17/17 MATCH | 0 foreign | 17 VERIFIED `document` |
| 6 | Bandhan Bank | `1fb7ee7` | `bandhan_date_effective_*` + `bandhan_date_description_debitcredit_*` | 7/8 + 5/5 (one honest isolated inconsistency stays FAILED) | 7/7 + 5/5 MATCH | 0 foreign | 10 VERIFIED, residuals refused |
| 7 | AU Small Finance Bank | `0a0fdbe` | `au_date_descriptionnarration_*_balance` | 14/14 | 14/14 MATCH | 0 foreign | 14 VERIFIED `region`, 3 residuals `no_layout` |
| 8 | DCB Bank | `c461c0b` | `dcb_date_transactiondetails_*` | 14/15 (1 printed-incomplete row FAILED, 1 scanned) | 14/14 MATCH | 0 foreign | 14 VERIFIED |
| 9 | APGV Bank | `fcd0523` | `apgv_postdate_valuedate_narration_chequedetails_*` | 13/13 | 10/13 MATCH + 3 explained diffs* | 2 foreign VERIFIED** | 13 VERIFIED `region` |

\* APGV files `52bf7ca8`, `433593b7`, `0e44d2c3` are Dr-balance loan accounts: probe
signs `Dr` balances negative and derives a signed opening, the engine reports the
printed magnitude. Row sets, Σdebits, Σcredits and closing magnitudes are identical
and the per-row chain VERIFIES — a probe sign-convention artifact, not data loss.

\*\* The only foreign VERIFIEDs are the 2 `APGB Bank` files: Andhra Pragathi
Grameena Bank shares APGV's exact core-banking format. Production routing refuses
them (`foreign_bank`) via the `ANDHRAPRAGATHIGRAMEENABANK` marker — a forced-spec
sweep bypasses the marker gate by design, so this is the documented sweep-only
exception (same pattern as Wave 1 SIB→BoB).

## Refused correctly / insufficient data

| Folder | Readable | Route outcome | Disposition |
|--------|----------|---------------|-------------|
| Dhanlaxmi Bank | 11 | `no_layout` ×11 | REFUSED-CORRECTLY (below cluster threshold) |
| UCO Bank | 9 | `other_bank:uco` ×9 | REFUSED-CORRECTLY; latent hazard below |
| Airtel Payments Bank | 7 | `other_bank:airtel_pb` ×5, `no_layout` ×2 | REFUSED-CORRECTLY |
| India Post Payments Bank | 5 | `other_bank:ippb` ×4, `no_layout` ×1 | REFUSED-CORRECTLY |
| Fincare SFB Bank | 3 | `no_layout` ×3 | INSUFFICIENT-DATA (3 files, single fingerprint) |
| APGB Bank | 2 | `foreign_bank` ×2 (APGV sibling) | REFUSED-CORRECTLY; needs own samples to onboard |
| Cosmos Bank | 2 | `no_layout` ×2 | INSUFFICIENT-DATA |
| Deutsche Bank | 2 | `other_bank:deutsche` ×2 | INSUFFICIENT-DATA |
| Tamilnad Mercantile Bank | 2 | `other_bank:tmb` ×2 | INSUFFICIENT-DATA |
| Fino Payments Bank | 1 | `other_bank:fino_pb` ×1 | INSUFFICIENT-DATA |
| RBL Bank | 0 | — | INSUFFICIENT-DATA (no PDFs, folder holds only CSVs) |
| SBM Bank | 0 | — | INSUFFICIENT-DATA (no PDFs, folder holds only CSVs) |
| CSB Bank | ~8 true | `other_bank:csb` / `no_layout` | REFUSED-CORRECTLY — contaminated folder (most files are Federal Bank misfiles, `fdrl` IFSC); the genuine CSB files split across incompatible sub-shapes, none reaching cluster threshold |

## Engine capabilities added this wave

| Commit | Capability |
|--------|-----------|
| `c1c4c96` | `left_aligned_amounts` — classify money words by the column's left edge (CSB probe, DCB). |
| `a090ca6` | `amount_sign_gap` — accept a space between sign and digits inside one money cell (DCB `- 17,000.00`). |
| `e0cf06f` | fix: restored Wave-2 registrations dropped by a cumulative staging bug (no capability change). |

## Known hazards recorded

- **UCO→Karnataka**: 7 UCO files resolve under `karnataka_date_particulars_instrumentno_*`
  and would VERIFY if extraction ran (4 confirmed VERIFIED under force). Production
  routing refuses them only because the `uco` detector supplies `bank_key` →
  `other_bank:uco`. If the detector ever misses a UCO file, the Karnataka header can
  accept it — flag for the detector-coverage task.
- **TMB→Canara**: 2 TMB files hit `canara_date_particulars_*` header; refused via
  `other_bank:tmb` plus the `TAMILNADMERCANTILEBANK` foreign marker.
- **APGB→APGV**: same-fingerprint sibling, verifies under forced spec; refused at
  routing via `ANDHRAPRAGATHIGRAMEENABANK`. Any future APGB onboarding must keep
  this marker.
- **City Union detector block** *(resolved in Wave 5)*: the `union` detector
  false-positived on "Union" in CUB files → `other_bank:union` → legacy fallback.
  Wave 5 added a `city_union` detector entry (`banks/city_union.json`) with
  DOMAIN/HEADER_NAME/IFSC evidence; CUB now detects `city_union` at
  VERY_HIGH/HIGH and the layouts route — re-measure: **37/37 VERIFIED**.
- **Wave-5 routed re-measurement** (full folder, current code): DCB 14/15
  VERIFIED + 1 FAILED; APGV 13/15 VERIFIED + 2 unrouted; AU 14/17 VERIFIED + 3
  unrouted; Bandhan **10/18 VERIFIED + 8 unrouted** — Bandhan coverage is
  materially weaker than the hold-out numbers implied; the 8 unrouted files are
  sub-threshold clusters not yet onboarded. See `WAVE5_RESULTS.md`.

## Tests

- `tests/statement_engine`: 169 passed (codec round-trips every Wave-2 layout;
  synthetic tests for `left_aligned_amounts` and `amount_sign_gap`).
- G2 probe re-derives opening/closing/Σdebits/Σcredits per file; all banks MATCH
  except the three APGV Dr-balance convention diffs documented above.
- G3 = each spec forced over a 773-file corpus sample; zero foreign VERIFIEDs
  outside the documented APGV→APGB sibling exception.
