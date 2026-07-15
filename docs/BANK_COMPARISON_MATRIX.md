# Bank Parser Comparison Matrix
*Airco Insights — All 14 Supported Banks Side-by-Side*

---

## 1. Parser Architecture Tier

Every bank parser sits in one of **3 capability tiers** based on how deeply it has been implemented:

| Tier | Description | Banks |
|------|-------------|-------|
| **Tier 1 — Full Custom Engine** | Dedicated coordinate parsing + hardcoded layout + dynamic fallback. Most complete. | HDFC, ICICI, Axis, Kotak, SBI |
| **Tier 2 — Shared-Base Line Parser** | Line-by-line text extraction using shared `base_parser`. Direction inference by balance delta. | Canara, IDFC, Bank of Baroda, Union, Karnataka, Paytm |
| **Tier 3 — Generic Delegate** | Thin wrapper delegating directly to `_shared/generic_bank` engine. | Bank of India, Indian Bank, Unknown |

---

## 2. Full Bank-by-Bank Comparison Table

| Feature | HDFC | ICICI | Axis | Kotak | SBI | Canara | IDFC | Karnataka | Paytm | Union | Bank of Baroda | Bank of India | Indian Bank | Unknown |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Tier** | 1 | 1 | 1 | 1 | 1 | 2 | 2 | 2 | 2 | 2 | 2 | 3 | 3 | 3 |
| **Parser Lines (Complexity)** | 924 | 1412 | 787 | 785 | 1068 | 536 | 557 | 455 | 475 | 544 | 535 | 309 | 98 | 483 |
| **Coordinate / Bounding-Box Parsing** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Hardcoded Layout (Primary)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| **Dynamic Column Detector** | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Multi-Layout Branching** | ❌ | ✅ (3 layouts) | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Direction Inference (Balance Delta)** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Explicit Dr/Cr Column Parsing** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Image-Only / Scanned PDF Detection** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| **Unsupported Format Queue Logging** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Parser Metrics Recording** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| **Scaled Boundary per Page Width** | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Multi-line Description Stitching** | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| **Date Normalizer (Bank-Specific)** | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ |
| **Opening/Closing Balance Extraction** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **AI Fallback (Groq → Claude)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Data Quality Score** | ✅ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Reconciliation Engine** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Structure Validator (PDF fingerprint)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Recurring Engine** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Finbit Analytics (31 Metrics)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **14-Sheet Excel Output** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Verified Live Sample Result** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ (27 txn) | ⚠️ (0 txn) | ✅ (213 txn) | ✅ (397 txn) | ⚠️ (0 on some) | ⚠️ (0 txn) | ✅ | ✅ (102 txn) | ✅ |

---

## 3. Parsing Strategy — How Each Bank's PDF is Read

| Bank | Primary Strategy | Secondary (Fallback) | Unique Challenge Handled |
|---|---|---|---|
| **HDFC** | pdfplumber table extraction + coordinate bounding boxes | Dynamic column detector | Complex overlapping columns in newer statements |
| **ICICI** | Layout branching: detects one of 3 distinct statement formats | Dynamic column detector | 3 completely different PDF layouts across statement generations |
| **Axis** | Coordinate parsing with scaled dynamic page-width boundaries | Hardcoded text fallback | Column positions shift based on page physical width |
| **Kotak** | Coordinate parsing with `DD Mon YYYY` date normalization | Dynamic column detector | Date format is `01 Oct 2025`, not `DD/MM/YYYY` |
| **SBI** | Coordinate parsing with multi-fragment transaction reconstruction | Hardcoded text extraction | Transactions split across 4–5 lines; requires fragment reassembly |
| **Canara** | Line-regex matching + balance-delta direction inference | Generic bank fallback | No explicit `Dr/Cr` column; direction inferred by balance change |
| **IDFC** | Line-regex + multi-line description stitching | Generic bank fallback | Multi-line descriptions bleed into adjacent rows |
| **Karnataka** | Line-regex with generic bank fallback | — | Sparse metadata; relies heavily on balance-delta direction |
| **Paytm** | Header-group matching: each transaction has a title header + detail lines | Generic bank fallback | UPI/wallet micro-transactions with non-standard row groupings |
| **Union** | Line-regex with direction inference + transaction order normalization | Generic bank fallback | Order of transactions may be reversed; direction from balance delta |
| **Bank of Baroda** | Line-regex with prefix + suffix multi-line description stitching | Generic bank fallback | Multi-column amounts with complex bracket-style debit/credit markers |
| **Bank of India** | Pure generic bank delegate | — | Handled 100% by shared generic engine; IFSC `BKID` detection |
| **Indian Bank** | Pure generic bank delegate | — | IFSC `IDIB` detection; delegates to shared generic engine entirely |
| **Unknown** | Dynamic column detector + generic bank delegate | — | No bank markers at all; full dynamism on any tabular ledger |

---

## 4. Date Format Handled Per Bank

| Bank | Date Format(s) | Bank-Specific Normalizer |
|---|---|---|
| **HDFC** | `DD/MM/YY`, `DD/MM/YYYY` | ✅ Shared date normalizer |
| **ICICI** | `DD/MM/YYYY`, `DD-MM-YYYY`, `DD MMM YYYY` | ✅ `_normalize_date()` |
| **Axis** | `DD-MM-YYYY`, `DD/MM/YYYY` | Shared normalizer |
| **Kotak** | `DD Mon YYYY` (e.g., `01 Oct 2025`) | ✅ `_normalize_kotak_date()` |
| **SBI** | `DD MMM YYYY`, `DD/MM/YYYY`, year inference from header | ✅ `_normalize_sbi_date()` with year inference |
| **Canara** | `DD/MM/YYYY`, `DD-MM-YYYY` | Shared normalizer |
| **IDFC** | `DD/MM/YYYY` | Shared normalizer |
| **Karnataka** | `DD/MM/YYYY` | Shared normalizer |
| **Paytm** | `DD MMM YYYY`, `DD/MM/YYYY` | Shared normalizer |
| **Union** | `DD/MM/YYYY`, `DD-MM-YYYY` | ✅ `_normalize_date()` |
| **Bank of Baroda** | `DD/MM/YYYY`, `DD-MM-YYYY` | ✅ `_normalize_date()` |
| **Bank of India** | `DD/MM/YYYY`, `DD-MM-YYYY` | ✅ `_normalize_date()` (generic) |
| **Indian Bank** | `DD/MM/YYYY` | Shared normalizer (generic) |
| **Unknown** | Any detectable date | Shared normalizer (generic) |

---

## 5. Special Capabilities & Unique Features Per Bank

| Bank | Unique / Notable Capability |
|---|---|
| **HDFC** | Dual-pass strategy: tries hardcoded first, falls back to dynamic. Separate parser metric telemetry. Highest transaction yield reliability. |
| **ICICI** | Only bank with **3-layout detection** (`_detect_statement_layout`). Handles legacy "Detailed Statement" format, amount/type format, and newer balance format. |
| **Axis** | **Page-width-scaled** dynamic column boundaries. Handles A4 vs Letter paper size statement variations gracefully. |
| **Kotak** | Custom date normalizer for `DD Mon YYYY`. Header line detection to avoid row bleeding from `#` serial number column. |
| **SBI** | Most complex parser (1412 lines). Handles **transaction fragments** spanning 4–5 lines. Infers statement year from header when year is absent in rows. |
| **Canara** | Reference number extraction strips noise from descriptions. Direction fully inferred from running balance delta (no explicit Dr/Cr columns). |
| **IDFC** | Multi-line description stitching (`_clean_multiline_text`). Reference extraction (`_extract_reference`) for UPI IDs. |
| **Karnataka** | Highest real-world transaction yield (213 txn on sample). Lightweight but effective line-regex parser. |
| **Paytm** | UPI/wallet-centric transactions. Each entry is a `header + detail_lines` group, not a flat row. Handles 397 transactions per sample — highest volume bank. |
| **Union** | Transaction **order normalization** (`_normalize_order`). Handles statements where transactions appear in reverse chronological order. |
| **Bank of Baroda** | Prefix + suffix multi-line description combining (`_combine_description`). Detects new description start mid-page. |
| **Bank of India** | Detects IFSC pattern `BKID\d{7}`. Broad UPI/IMPS token isolation to prevent alias preemption. |
| **Indian Bank** | IFSC `IDIB` detection, thin 98-line wrapper. Fastest to maintain. Delegates to `generic_bank` engine entirely. |
| **Unknown** | Zero bank markers needed. Dynamic column detection runs on any tabular PDF. Automatic fallback for all unrecognized uploads. |

---

## 6. Summary Score Card (out of 10)

| Bank | Parser Robustness | Multi-Format Support | Direction Accuracy | Verified Txn Yield | Overall |
|---|:---:|:---:|:---:|:---:|:---:|
| **HDFC** | 10 | 8 | 10 | 10 | **9.5** |
| **ICICI** | 10 | 10 | 10 | 10 | **10.0** |
| **Axis** | 9 | 8 | 10 | 9 | **9.0** |
| **Kotak** | 9 | 7 | 10 | 9 | **8.8** |
| **SBI** | 10 | 8 | 9 | 9 | **9.0** |
| **Canara** | 7 | 6 | 8 | 8 | **7.3** |
| **IDFC** | 7 | 6 | 7 | 6 | **6.5** |
| **Karnataka** | 7 | 6 | 8 | 9 | **7.5** |
| **Paytm** | 8 | 6 | 8 | 10 | **8.0** |
| **Union** | 7 | 6 | 7 | 6 | **6.5** |
| **Bank of Baroda** | 7 | 6 | 7 | 6 | **6.5** |
| **Bank of India** | 6 | 5 | 7 | 7 | **6.3** |
| **Indian Bank** | 5 | 5 | 7 | 8 | **6.3** |
| **Unknown** | 8 | 10 | 7 | 7 | **8.0** |

---

## 7. What "Improvement Needed" Means Per Tier-2 Bank

Banks in Tier 2 and 3 that showed `0 transactions` on live samples need specific attention:

| Bank | Known Issue | Fix Approach |
|---|---|---|
| **IDFC** | Returns 0 transactions on tested sample | `structure_validator` markers too strict; new IDFC First layouts may not match IFSC or header patterns |
| **Bank of Baroda** | Returns 0 transactions on tested sample | Bracket-style Cr/Dr amount columns not parsed correctly; `_parse_amount_columns` regex needs tuning |
| **Union Bank** | Fails on some samples (empty text extraction) | Some Union PDFs have embedded images per page; needs image-layer fallback or OCR pre-check |

---

*Last updated: June 2026 | Airco Insights FinTech SaaS*
