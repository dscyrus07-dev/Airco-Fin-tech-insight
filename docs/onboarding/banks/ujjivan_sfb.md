# ujjivan_sfb — onboarding notes

Status: **SHADOW_ONLY** — detection 76.9%; all REVIEW (self-derived anchor) — spec frozen; FAILED x5 chain/side

Folders: Ujjivan Small Finance Bank
Files: 39 pdf | 39 text | 0 scanned | 0 locked

## Fingerprints

distinct fingerprints: 4 | top share: 74.4%
- `date/debit/credit/balance/amount` x29
- `date/narration/amount/dr_cr` x8
- `date/narration/debit/credit/balance` x1
- `date/narration/ref/srno/debit/credit/balance` x1

## Current behaviour (V2_MODE=shadow)

- probed: 39 | detected-correct: 76.9% (wrong: 1, none: 8)
- tier: {'fallback': 10, 'v2': 29} | rows read: 13323
- verdicts: {'REVIEW': 24, 'FAILED': 5}
- fallback reasons: {'no_layout': 10}
- cross-bank false accepts on pooled other-bank files: 1
  - f3105a96 from Human Verification via detector

## Independent audit (hold-out VERIFIED sample)

- sampled: 0 of 0 VERIFIED | ok: 0 | disagreements: 0

## Unblock pass (devin/unblock-1)

Re-measure (33 files): 24 v2 (20 REVIEW + 4 FAILED), 9 no_layout.
- All REVIEWs are self-derived chains: L1 statements print no opening/closing
  anchors (a per-account-type "Summary of Accounts" is unrelated). Honest (E);
  Vshare 0% -> stays SHADOW_ONLY.
- no_layout causes: 6 files use a `Sr | Date | Description | Amount | Type`
  (Dr/Cr) loan/passbook layout with NO balance column - engine gap (F);
  `91db325d` is a fully monospace-glued export (each line one word): a
  `monospace_text` spec extracts it after prep, but registry header detection
  runs pre-split so it can never route - engine gap (F);
  `0e8ceb69` is a misfiled IDBI statement (header IFSC `IBKL..`; `UJVN` only in
  body) - excluded (D). The Human-Verification detector hit (`f3105a96`) no
  longer reproduces at tip (UNKNOWN/no_layout).
- FAILED `a08627e2`,`c7f7cb38`,`793b0633`,`0197b955`: real printed chain
  discontinuities (balance jumps across page boundaries) - honest.

## N5 pass (branch devin/n5-bank-wave)

- Re-measure (32 files): REVIEW 20, FAILED 4, fallback 8 (7 `bank_unconfirmed` + 1 `no_layout`).
- The Human-Verification detector false-accept (`f3105a96`) does not reproduce at tip.
- 7 `bank_unconfirmed` files carry zero Ujjivan tokens in header/footer (unbranded exports;
  UJVN appears nowhere) -> correct refusal, class C.
- `91db325d` fully monospace-glued (one word per line): registry header detection runs pre-split,
  so `monospace_text` can never route it — class F engine gap.
- FAILEDs `0197b955`/`793b0633`/`a08627e2`/`c7f7cb38`: real printed balance discontinuities (class D).
- No spec/detector change. **SHADOW_ONLY** (VERIFIED share ~0% — statements print no anchors, class E).
