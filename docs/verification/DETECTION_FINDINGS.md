# Slice 2B detection findings (run on 1904 corpus PDFs, 43 folders)

- Confident predictions (VERY_HIGH): 915, 96.4% match the folder. All 33 disagreements sampled so far were genuine statements of the detected bank misfiled in the wrong folder (checked page-1 text).
- HIGH 181 (65% match) and MEDIUM 209 (68% match): disagreements sampled (ICICI/HDFC/Union/SBI/IndusInd/Karnataka/Canara/BoB/Paytm) were also misfiled files; not all 96 confident disagreements were read yet.
- Abstains (Unknown/Low): 296 of 1601 labelled files (18.5%). Causes seen: no issuer text on page 1 (UPI-style exports, Paytm/Axis-labelled), garbled font text (Karur Vysya, cid), payslips/invoices (correctly refused), scanned/locked.
- Table-header fix (Indian Bank, Federal Jupiter, Central Bank layouts) recovered ~25 files. Remaining LOW: Federal "Fi" statements (IFSC only, no table recognized).
- 19 of 64 files in Other_Unknown/Non_Bank/Password_Protected were detected as a bank (mostly HIGH): likely misfiled; not yet verified.
- Old detector agrees with folder on 25.6%, new on 71.4%. 49 files where only the old one agreed (mostly Paytm/Kotak/Axis/ICICI abstains) - to be reviewed.
Corpus folders are labels, not truth. Outputs: docs/slice2/out/ (outputs moved to external archive 2026-10-12).
