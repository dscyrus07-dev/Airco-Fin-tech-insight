# BANK STATUS — v2 statement engine coverage

Branch `devin/wave3`. One row per bank. States:

- **ONBOARDED** — registered `LayoutSpec`(s), verified on real files, routed.
- **LEGACY-HOLD** — explicitly pinned to the legacy parser; the v2 router returns
  `legacy_only:<bank>` before any layout resolution.
- **REFUSED-CORRECTLY** — known to the system (detector/marker); files refuse with
  `other_bank:*` / `foreign_bank` / `no_layout` rather than mis-accepting.
- **INSUFFICIENT-DATA** — too few readable samples to build/validate a layout.

## Onboarded (45 layouts / 33 bank keys)

| Bank | Layouts | Verified (in-scope) | Evidence |
|------|---------|---------------------|----------|
| HDFC | 1 | slice3 baseline | region |
| SBI | 1 | slice3 baseline | detector/region |
| ICICI | 2 | slice3 baseline | region |
| Axis | 1 | slice3 baseline | region |
| Canara | 1 | slice3 baseline | region |
| Kotak Mahindra | 3 | slice3 baseline | region |
| Bank of Baroda | 3 | slice3 baseline | document |
| Federal Bank | 1 | slice3 baseline | region |
| Indian Bank | 1 | slice3 baseline | region |
| Karnataka Bank | 1 | slice3 baseline | region |
| IDFC First | 1 | slice3 baseline | region |
| Paytm Payments Bank | 1 | slice3 baseline | region |
| Union Bank of India | 1 | slice3 baseline | region |
| Standard Chartered | 2 | slice3 baseline | region |
| DBS | 1 | 38/46 hold-out | region |
| Citibank | 1 | 23/24 hold-out | region/document |
| Karur Vysya | 1 | 1/29 hold-out (PARTIAL) | document |
| HSBC | 1 | 8/10 hold-out | region |
| IndusInd | 1 | 34/34 hold-out | region/document |
| Punjab National Bank | 1 | 23/23 hold-out | detector |
| IDBI | 2 | 8/14 + 8/8 hold-out | document/region |
| Yes Bank | 1 | 13/13 hold-out | detector |
| Indian Overseas Bank | 2 | 12/12 + 9/9 hold-out | detector |
| South Indian Bank | 1 | 11/12 hold-out | detector |
| Central Bank of India | 2 | L1 8/10, L2 3/3 | region |
| Equitas SFB | 1 | 9/12 hold-out | region |
| City Union Bank | 2 | 31/31 + 6/6 | marker only (no detector id) |
| Ujjivan SFB | 1 | 8/10 hold-out | document |
| Bank of Maharashtra | 2 | 11/11 + 6/6 | document |
| Bandhan Bank | 2 | 7/8 + 5/5 | region/document |
| AU Small Finance Bank | 1 | 14/14 | region |
| DCB Bank | 1 | 14/15 | region |
| APGV Bank | 1 | 13/13 | region (no detector id) |

## LEGACY-HOLD

| Bank | Reason | Exit criteria |
|------|--------|---------------|
| Bank of India | Stays on the old parser by decision. `LEGACY_ONLY_BANKS` in `v2_router.py` returns `fallback` + `legacy_only:bank_of_india` before layout resolution, even with `allow_header_only`. The bare marker `BANKOFINDIA` is intentionally NOT used (substring of STATEBANKOFINDIA / RESERVEBANKOFINDIA / CENTRALBANKOFINDIA). Corpus proof: 31 legacy_only + 21 no_layout + 18 locked + 3 scanned; zero v2 results. | Onboardable when the folder yields a readable cluster ≥5 files with a distinct header fingerprint that cannot collide with SBI/RBI/CBI, plus a detector-confident bank id. |

## Refused / insufficient data

| Folder | Readable | Route outcome | Disposition |
|--------|----------|---------------|-------------|
| Dhanlaxmi Bank | 11 | `no_layout` ×11 | REFUSED-CORRECTLY |
| UCO Bank | 9 | `other_bank:uco` ×9 | REFUSED-CORRECTLY (latent: would verify under Karnataka header if detector missed) |
| Airtel Payments Bank | 7 | `other_bank:airtel_pb` ×5, `no_layout` ×2 | REFUSED-CORRECTLY |
| India Post Payments Bank | 5 | `other_bank:ippb` ×4, `no_layout` ×1 | REFUSED-CORRECTLY |
| Fincare SFB | 3 | `no_layout` ×3 | INSUFFICIENT-DATA |
| APGB (Andhra Pragathi) | 2 | `foreign_bank` ×2 | REFUSED-CORRECTLY (shares APGV format; own marker) |
| Cosmos Bank | 2 | `no_layout` ×2 | INSUFFICIENT-DATA |
| Deutsche Bank | 2 | `other_bank:deutsche` ×2 | INSUFFICIENT-DATA |
| Tamilnad Mercantile | 2 | `other_bank:tmb` ×2 | INSUFFICIENT-DATA (latent: Canara header collision) |
| Fino Payments Bank | 1 | `other_bank:fino_pb` ×1 | INSUFFICIENT-DATA |
| RBL Bank | 0 | — | INSUFFICIENT-DATA (CSV only) |
| SBM Bank | 0 | — | INSUFFICIENT-DATA (CSV only) |
| CSB Bank | ~8 true | `other_bank:csb` / `no_layout` | REFUSED-CORRECTLY (folder contaminated with Federal misfiles; real CSB files split across sub-threshold shapes) |
