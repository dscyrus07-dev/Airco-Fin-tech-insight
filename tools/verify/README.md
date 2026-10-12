# tools/verify — independent verification tooling (prompt 26)

Written for the verification pass; does not reuse `tools/onboarding/` logic.
Reuses only the corpus sha8 manifest (`tools/onboarding/.local/manifest_*.jsonl`,
`folders.json`) to locate files — all measurement is re-run by these scripts.

- `measure.py` — resumable per-file runner. Routes each PDF with
  `route_pdf` (V2 shadow semantics: `use_detector=True`) and records status,
  fallback reason, routed layout + spec bank, detector bank/confidence, verdict,
  verdict reasons, row count, runtime. Output: JSONL, one record per file;
  re-running skips sha8s already present.
- `summarize.py` — aggregates a measure JSONL into per-bank stats
  (detection rate, tier mix, rows, verdict mix, review-code counts, runtime).
- `audit_verify.py` — spec-independent audit of VERIFIED files: re-extracts
  text with pdfplumber directly, counts dated amount-bearing lines vs rows,
  rebuilds the running-balance chain from extracted rows, and compares first/
  last running balances with printed opening/closing anchors found by regex.
- `confuse.py` — cross-bank matrix runner (same measure core, folder × detected
  bank counts).
- `pii_scan.py` — diff-only PII/secret scanner used for the boundary check.

State and outputs live in `tools/verify/.local/` (gitignored).
