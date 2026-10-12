# Universal reader — tiers and claims (U1)

Goal: **every text-layer bank statement yields useful, honestly labelled output; nothing the
product calls verified is ever wrong.** Tiers decide what a file may claim; the claim ceiling
is a property of the tier, not of the parser's confidence.

## Tier order

| Tier | When it runs | What it may claim |
|---|---|---|
| **T0 unreadable** | No extractable text layer: locked/encrypted (no password), image-only, or glyph-dump text (`(cid:NN)`, zero real words) | Plain message only. This is the **only** tier that may mention "scanned / image-based". Nothing is run. |
| **T1 registered layout + bank evidence** | The detector/spec registry resolves a registered `LayoutSpec` for this bank **and** the bank evidence passes (as today) | Full v2 verdicts exactly as today: VERIFIED / REVIEW / FAILED. T1 is the only tier that may claim VERIFIED. |
| **T2 legacy parser** | One of the 13 legacy processors, when T1 does not serve | As today: a completed workbook, **never** a "Verified" badge (no Statement Check sheet, no verification claim). |
| **T3 universal reader** | Any text-layer statement no higher tier handled: unknown bank, unknown layout, detector-unconfirmed bank, or `bank_unconfirmed` | **Capped at REVIEW** this wave — never VERIFIED. New review code `GENERAL_READER`. FAILED when the engine's own checks fail. Bank identity = the detector's bank when confident, else "Unknown bank". T3 never asserts a bank from the inferred layout. |

A file always takes the **highest** tier that produces a result. T3 output is a proposal to the
user ("read with our general reader — check the figures"), not a verification.

## How T3 works (U2)

T3 does not parse anything itself. It **infers a runtime `LayoutSpec`** and runs the ordinary
engine (`extract_pages`) plus `run_checks`, so every result passes through the same verdict code
as registered layouts:

1. **Probe** — `read_pages` (pdfplumber). Words-per-page threshold and `(cid:NN)` share decide the
   text layer. Locked/empty → T0, nothing else runs.
2. **Furniture removal** — lines repeated on most pages (headers, footers, page numbers) are
   dropped before structure inference.
3. **Header discovery** — a synonym lexicon (Date/Txn Date/Value Date…; Narration/Particulars/
   Description…; Debit/Withdrawal/Dr…; Credit/Deposit/Cr…; Amount(+Dr/Cr or Type);
   Balance/Closing Balance…; Ref/Chq No…) scored by token coverage and column geometry,
   multi-line headers allowed. The matched tokens become the spec's `columns` entries verbatim —
   the engine still anchors on what the document actually prints, never on assumed words.
4. **Headerless fallback** — when no header line exists, repeated dated-line geometry yields an
   `implicit_header` spec (the wave-10 mechanism).
5. **Column-role inference** — money columns are not guessed from their names: candidate role
   assignments are scored by how well the running-balance chain holds (`bal_i = bal_{i-1} ± amt_i`
   across sampled dated rows). The best assignment wins **only** when its margin over the
   runner-up is clear; a low margin is `FAILED` (`LOW_CONFIDENCE_COLUMNS`), never a guess.
6. **Date-shape inference** — from the date column's tokens against a fixed candidate set
   (numeric, `dd-Mon-yyyy`, `dd Mon yyyy`, yearless + `date_tail_re`, wrapped year). The year is
   inferred only when unambiguous (`year_from_period` only when a parseable period exists).
7. **Amount forms** — Indian grouping, `Dr`/`Cr` suffixes (→ `single_amount_column`), signed
   amounts (→ `merge_sign_prefix`), single amount + type column (→ `side_marker_column`),
   `Rs.`/`₹` prefixes, parenthesised negatives.
8. **Summary capture** — labelled opening/closing/period/totals lines are found generically and
   emitted as `opening_balance_re` / `closing_balance_re` / `totals_line_re` / `period_re`, so
   `reference`/`totals`/`period` checks anchor to printed figures where the statement prints them.
   Balance-only first rows map to `opening_row_balance_only`.
9. **Multi-statement** — ≥2 distinct account numbers or repeated full statements → `FAILED` with
   `MULTI_STATEMENT`, never merged silently.
10. **Budgets** — hard page cap (default 60) and wall-clock budget (default 20 s). Any exception,
    overrun or internal inconsistency returns `FAILED` with a reason code — T3 never raises.

## What T3 may say in the UI

`GENERAL_READER`: *"This statement's layout was read with our general reader, so please check the
figures against your statement."* — amber "Read by general reader" badge, never "Verified".

## Deciding if T3 may ever go above REVIEW

U3 measures the **false-clean rate**: files where T3's checks all pass but rows differ from rows
verified by a registered layout on the same file. The recommendation (delivered in
`UNIVERSAL_RESULTS.md`): T3 stays capped at REVIEW while any false-clean exists; a documented
per-bank/per-layout promotion path needs false-clean ≈ 0 over the trusted set plus the
onboarding gates in U4.
