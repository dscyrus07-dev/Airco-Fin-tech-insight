# ENGINE_GAPS — engine-level gaps found during prompt-29 unblocking

Each entry is a statement family that **cannot** be expressed by the current
`LayoutSpec` model (or is provably unreadable without OCR). All were verified on
corpus files before being parked — none are spec-tuning failures. Bank-owned specs
that *were* expressible were shipped in the same pass.

## 1. Balance-less transaction tables

`balance_column` is mandatory; without a running balance the chain model cannot
engage at all.

- `dbs` — `Date | Details of Transaction | Debit | Credit` variant (9 files)
- `equitas_sfb` — `baf15ad9` single `Withdrawal(INR)` column
- `idbi` — `Date | Description | Amount | Type` family (8 files)
- `federal` — balance-less app-statement family (part of the 113 no_layout)

## 2. Unreadable text layers (OCR required)

- **cid-garbage glyphs**: `kvb` ~70 bank_unconfirmed files extract as `(cid:NN)`
  tokens; `ippb` `5128847f` same class.
- **Space-glyph money cells**: digits absent from the text layer — `uco` FAILEDs,
  `equitas_sfb` variant-A (`Withdrawal`/`Deposit`/`ClosingBalance` titles never
  extract), `dhanlaxmi` fp-C balance cells, `csb` orphan `CR` fragments.
- **Scanned**: `hsbc` 57/103, `equitas_sfb` 3, plus scattered locked files.

These are honest FAILED/excluded outcomes — a spec would only re-label them.

## 3. Fully glued word tokens

`central_bank` `2e2f4e20`/`735d18a4` and `ujjivan_sfb` `91db325d` print every line
as one fused word. `find_header` runs on raw words before `_split_monospace`, so
`monospace_text` cannot rescue the header — positional extraction is impossible.

## 4. `Dr.`/`Cr.` side markers with trailing period

`idbi` `Srl | Txn Date | Value Date | Description | Cheque | CR/DR | CCY | Amount |
Balance` family (19 files): `normalize.py` marker regex `\(?(cr|dr)\)?$` rejects
the trailing `.` in `Dr.` — every row fails schema. Spec drafted (`IDBI_LAYOUT_3`)
and parked unregistered; fix is a one-character regex change in the engine.

## 5. Header shapes beyond `header_wraps`

- **3-line interleaved headers**: `yes` `008a966b`, `central_bank` `459f15b8`
  (15-col wrapped) — `header_wraps` merges pairs only.
- **Headerless tables** (`implicit_header`): works only when dated rows are
  positionally consistent; unusable where money cells are also absent (§2).

## 6. Date-grouped app statements

`federal` dominant family (~100 files, Jupiter/Fi-style): dates appear as section
headers; transaction rows beneath them are undated. LayoutSpec requires a dated
row per transaction — needs a row-grouping model the engine does not have.

## 7. Non-row balance prints

- `hsbc` UK variant: running balance prints only on `BALANCE CARRIED FORWARD`
  lines; data rows carry none → chain cannot engage.
- `dhanlaxmi` fp-A: amount on a prefix line, balance on an inline `Balance:` label
  line — needs balance-as-continuation-line semantics plus §5 header.
- `ippb` closing sits in a 5-column label:value summary (`No.ofTransactions`
  field) that `parse_summary` cannot express; values merge ambiguously when
  squashed → single-ended anchor, REVIEW ceiling.

## 8. Document-internal inconsistencies (honest FAILED)

Not repairable — the document contradicts itself:

- `yes` 20 FAILED: paired fee rows where the balance moves once per charge-pair
  while two debit lines print → printed per-pair balances cannot reconcile.
- `central_bank` `deb76171`: duplicate rows printed in the document.
- `indusind` L3 credit-card statements: balance column truncated to whole rupees
  while debits keep paise.
- `dbs` multi-account docs / `uco` multi-segment: second-segment sections break
  the single-chain model.
- `idbi` L5: 1409/2045 rows lack printed balances (sparse print).

## 9. Detector scope limits (engine constraints, not bugs)

- Detector scans page 1 + running edges — `idbi` deep-page `IBKL`/`IDBI BANK`
  evidence is unreachable by design.
- Head scan ends at the first date-like line: `standard_chartered` 4 files where
  an address fragment (`6-3-1090`) terminates the scan before `IFSC: SCBL…`.
- `ujjivan_sfb` `f3105a96` false-accept at tip verified resolved (now UNKNOWN).

## Misfiled documents (class D — correctly excluded, not gaps)

- `kvb` no_layout files: Canara e-pass sheets.
- `csb` federal-routed files: genuine Federal exports misfiled in the CSB folder.
- `yes` `e99c7c1d` Union Bank letterhead, `2aed793f` AU statement (`AUBL` IFSC),
  `apgv` `248fc20d` Canara e-Pass Sheet.
- `airtel_pb` 3 unrouted: postpaid/fiber billing statements (non-bank).
- `idbi` `2cde3656`: GL ledger report, not a statement.
- `apgb`: NOT_POSSIBLE — no running-balance column (see `banks/apgb.md`).

## N5 refresh (devin/n5-bank-wave)

Newly confirmed engine-level gaps (no spec fix possible):

- **Anchor association in multi-account docs** (`dcb`): printed summary
  opening/closing belongs to a different sub-account than the parsed section;
  needs per-segment anchor binding (class B).
- **Continuation swallow before date-inherit** (`scb`): an undated `9,608`
  withdrawal line is consumed as continuation narration before
  `undated_rows_inherit_date` can promote it (class F ordering).
- **Detector head-scan terminator** (`scb`): `_head_lines` stops at the first
  date-like line; a street address `6-3-1090,` cuts the scan before
  `IFSC: SCBL…`, leaving weak evidence vs narration-leak counterparty marks.
- **All-zero B/F ordering** (`idbi`): `opening_row_balance_only` rejects a dated
  `0.00 / 0.00` carry-forward row before `zero_amount_is_empty` can clear it.
- **5-value summary rows** (`ippb`): label:value summary includes a
  `No.ofTransactions` field; `parse_summary` expects exactly the configured
  numeric count — ambiguous squash, REVIEW ceiling stands.
- **Clipped GRAND TOTAL decimals** (`federal`): `6149602.0`/`6106586.94` print
  glued; the boundary is ambiguous at text level → honest FAILED (class D).
- **Shared/misplaced balance cells** (`yes`, `idbi`): B/F balance printed in
  the wrong money cell; charge pairs share one balance print (class D/F).
- **Jumbled print order** (`uco` `14ab1185`): rows print out of date order and
  cannot chain (class F).
- **Non-statement misfiles confirmed refused**: `pnb` `4eb17de5` (WhatsApp T&C).
