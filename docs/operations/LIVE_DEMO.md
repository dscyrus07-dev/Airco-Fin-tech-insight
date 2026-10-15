# LIVE_DEMO — 10-minute click path on the `rc` stack

Audience: product demo. Stack: `rc` (see `LIVE_STACK.md`). All files are in
`tools/final/demo_pdfs/` — fully synthetic ("Test Holder", fake numbers); no
real statement anywhere. Expected results per file: `demo_pdfs/README.md`.

## Before you start (1 min)

```bash
curl -s http://localhost:8601/health          # must say "status":"ok"
```
Open http://localhost:3600, Sign in with the shared test account
(`local.env` at repo root). You land on the unified statement workflow.

## Minute 0-2 — straight-through success

1. Drag **`demo_canara.pdf`** onto the upload area -> Analyze.
2. Say: "The engine reads the PDF's own evidence — IFSC, header text — and
   identifies the bank before any parsing."
3. The row shows **Canara Bank · DETECTED** with a confidence; expand "Why we
   think so" to show the evidence list.
4. Click **Confirm**, then **Process confirmed**.
5. On the report page: every sheet populated, **Statement Check** says
   `Verdict: VERIFIED · Independently verified: yes`. Download the Excel if
   asked — sheets: Summary, Monthly Analysis, Top 5 credits/debits, Bounce,
   Salary, Loan, CC payments, Transactions, Statement Check.

## Minute 2-4 — a bank that always needs review

6. New statement -> **`demo_iob.pdf`** -> Analyze.
7. Say: "Indian Overseas statements print no balance anchors, so the engine
   can never independently prove the numbers. We say that honestly."
8. Row shows IOB, selectable — Confirm -> Process. Verdict **REVIEW**;
   Statement Check prints `Needs review: yes` and the reasons
   (`NO_INDEPENDENT_ANCHOR`). Same full workbook; it just never claims
   machine-verified correctness.

## Minute 4-6 — refusals and safety

9. New statement -> **`demo_scanned.pdf`**. Row: **UNSUPPORTED** — "scanned or
   image-based … nothing will be run on it." No Confirm button, no bank
   picker. Say: "We refuse rather than guess."
10. **`demo_locked_hdfc.pdf`** -> shows a password prompt. Type a wrong
    password -> honest rejection. Type `demo1234` (in the kit README) ->
    unlocks and proceeds like a normal file.
11. **`demo_wrongbank.pdf`** (HDFC-shaped content, wrong holder header) ->
    detected as HDFC. If someone forced it through a different bank, the
    mismatch guard fails the job — a wrong-bank VERIFIED is impossible.

## Minute 6-8 — unknown bank + manual selection

12. **`demo_unknown.pdf`** -> **UNKNOWN** row: "We could not tell which bank
    issued this statement." Pick a bank in the dropdown — a yellow warning
    appears ("If the PDF is not actually from the selected bank, processing
    may fail validation") -> "Use selected bank". Process: the guard decides;
    a mismatched pick fails honestly.

## Minute 8-9 — supported-banks panel + batch

13. Open the bank dropdown or the supported-banks panel: **16 Verified ·
    4 Review required · 2 Legacy parser** selectable; coming-soon and
    unsupported banks are greyed with one-line reasons.
14. Batch: select `demo_hdfc.pdf`, `demo_kotak.pdf`, `demo_iob.pdf`,
    `demo_scanned.pdf` together -> Analyze -> Confirm all detected ->
    Process confirmed. HDFC/Kotak complete, IOB lands REVIEW, scanned stays
    refused — one batch, four honest outcomes.

## Minute 9-10 — history + wrap

15. Dashboard Files/history shows the batch entries with their verdicts.
16. Closing line: "Every answer the product gives — verified, review, or
    refused — is backed by the file's own evidence, and the review/refusal
    paths say exactly why."

## If something shows REVIEW or 'not enabled'

- **REVIEW** = "the file processed fully but the engine could not
  independently recompute the printed balances — a human should look." Not
  an error; it's the honest middle state.
- **Not enabled / coming soon** = "we detect this bank but have not passed
  the evidence gate to serve it — we refuse rather than produce an
  unverified report."
- **Failed job** = read the message; retry is offered. A failed job never
  produces a workbook that could be mistaken for a good one.
