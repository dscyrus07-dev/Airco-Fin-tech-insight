# Demo Readiness — Demo Release Candidate

Pin: `demo/rc` (local only). Stack: Docker Compose, all 8 services healthy.
Flags for the demo: `STATEMENT_ENGINE_V2_MODE=serve`, `STATEMENT_ENGINE_V2_SERVE_BANKS=hdfc`.

This build is honest: every bank shows exactly what is true today — v2 VERIFIED,
legacy processed, needs review, or not supported. Nothing unverified is presented
as verified.

## Per-bank table (one tested file each; A=off, C=serve-hdfc)

| Bank | Engine used | Expected verdict | What the demo shows | Known limitation | Result |
|---|---|---|---|---|---|
| HDFC Bank | v2 (serve) | VERIFIED | Upload → DETECTED → verified badge + Statement Check sheet | — | **PASS** |
| SBI | legacy | — | 299-txn statement processes end-to-end | not v2-served yet | **PASS** |
| ICICI Bank | legacy | — | 378-txn statement processes end-to-end | not v2-served; see probe note | **PASS** |
| Axis Bank | legacy | — | 1,147-txn statement (largest) | not v2-served | **PASS** |
| Kotak Mahindra | legacy | — | 506-txn statement | not v2-served | **PASS** |
| Kotak Bank | legacy | — | 453-txn statement | not v2-served | **PASS** |
| IDFC First | legacy | — | 798-txn statement | not v2-served | **PASS** |
| Karnataka | legacy | — | 231-txn statement | not v2-served | **PASS** |
| Paytm / Paytm Payments | legacy | — | 396 / 414-txn statements | not v2-served | **PASS** |
| Bank of India | legacy | — | completes after routing fix (150 txn) | fix landed this run | **PASS-WITH-NOTES** |
| Bank of Baroda | legacy | — | REVIEW → issuer validation rejects this app-format file | legacy check false-negative; v2 VERIFIED in shadow | **PASS-WITH-NOTES** |
| Indian Bank | legacy | — | routes now; issuer validation rejects app-format file | same class as BoB | **PASS-WITH-NOTES** |
| Canara Bank | legacy | — | DETECTED then honest failure message | legacy parser can't find txn table (e-passbook) | **PASS-WITH-NOTES** |
| Union Bank | legacy | — | DETECTED then honest failure message | legacy parser can't extract rows | **PASS-WITH-NOTES** |
| Other ~30 folders | — | — | detector UNKNOWN or document UNSUPPORTED | not in the 13-bank product set | **NOT-SUPPORTED** |

## What is verified vs claimed

- **Verified live**: analyze→confirm→process→Excel download for every completed
  bank through the HTTP API; the same flow through a real browser for HDFC
  (desktop + 360 px), console clean.
- **Serve safety**: HDFC-only allowlist verified — all non-HDFC banks produce
  byte-path-identical legacy results in serve mode; a mutated HDFC statement is
  caught (verdict FAILED, falls back) instead of staying VERIFIED.
- **Kill switch**: mode flipped serve→off at runtime (env + `up -d backend`),
  next upload immediately legacy. Verified live.
- **Excel**: 17 workbooks recalculated headless in LibreOffice — 0 real formula
  errors (one false positive: an address literal starting with `#`).
- **Numbers**: engine txn counts match the independent parser within layout
  tolerance (exact on Axis/SBI/Karnataka/Kotak/Citibank-class rows; HDFC counts
  date+value-date lines so it reads ~2× — a counter artifact, not data loss).

## Public-URL options (user decision — NOT enabled)

- Keep it local (recommended): `http://localhost:3000` on the demo machine.
- Tunneling (ngrok/cloudflared): quick but sends real statement data through a
  third-party endpoint — risk flagged, not done.
- Opening firewall/ports on this machine: not done.
