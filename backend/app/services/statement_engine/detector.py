"""Bank detection from the text layer, with evidence and a confidence category.

Principles (see the Slice 2 plan):
  * Document text decides. Filename, MyPaisaa metadata and the user's choice are supporting evidence only:
    they are recorded, and a disagreement is flagged, but they never raise confidence.
  * Position matters. A statement's transaction rows are full of other banks' names, UPI handles and
    IFSC codes (NEFT/IMPS counterparties). Only the page-1 header block, running
    headers/footers, and *labelled* IFSC codes count strongly; lines that look like transaction rows are ignored. Names found deep in the body count for nothing.
  * Longer names are consumed first, so "State Bank of India" is never also read as "Bank of India",
    and phrases such as "Reserve Bank of India" are masked.
  * Unknown is a valid answer. Weak or ambiguous evidence returns UNKNOWN or LOW and never auto-routes.

Pure function over page texts: no file I/O, deterministic.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Sequence, Tuple

from .contracts import (
    DOCUMENT_EVIDENCE,
    Confidence,
    DetectionResult,
    Evidence,
    EvidenceKind,
)
from .registry import BankRegistry, default_registry

HEAD_LINES = 20      # page-1 header block
EDGE_LINES = 3       # running header/footer lines checked on every page (top 3 and bottom 3)

WEIGHTS: Dict[EvidenceKind, int] = {
    EvidenceKind.IFSC_LABELLED: 40,
    EvidenceKind.HEADER_NAME: 30,
    EvidenceKind.IFSC_HEADER: 25,
    EvidenceKind.RUNNING_HEADER: 20,
    EvidenceKind.DOMAIN: 25,
    EvidenceKind.PAGE1_NAME: 8,
    EvidenceKind.STATEMENT_PHRASE: 8,
}
SHORT_NAME_WEIGHT = 12   # bare token ("hdfc"), header block only
SUPPORT_WEIGHT = 6

# (min score, min margin over runner-up, min distinct evidence kinds) -> confidence, checked in this order
_THRESHOLDS: Tuple[Tuple[int, int, int, Confidence], ...] = (
    (60, 30, 2, Confidence.VERY_HIGH),
    (40, 25, 1, Confidence.HIGH),
    (25, 15, 1, Confidence.MEDIUM),
    (12, 8, 1, Confidence.LOW),
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_LABELLED_IFSC = re.compile(
    r"(?i)\b(?:ifsc(?:\s*code)?|ifs\s*code)\s*[:\-.]?\s*([A-Za-z]{4}0[A-Za-z0-9]{6})\b"
)
_BARE_IFSC = re.compile(r"\b([A-Z]{4}0[A-Z0-9]{6})\b")


def _norm_words(text: str) -> str:
    return " " + _NON_ALNUM.sub(" ", (text or "").lower()).strip() + " "


_D = r"(?:0?[1-9]|[12]\d|3[01])"
_M = r"(?:0?[1-9]|1[0-2])"
_MON = r"[A-Za-z]{3,9}"
# any plausible date (day 1-31, month 1-12): "01/04/21", "1-Apr-2021", "2021-04-01". "2-91/81" (an address) is not one.
_DATE_CORE = (
    rf"(?:{_D}[-/.]{_M}[-/.](?:\d{{4}}|\d{{2}})"
    rf"|{_D}[-/. ]{_MON}[-/. ,]*(?:\d{{4}}|\d{{2}})"
    r"|\d{4}-\d{2}-\d{2})"
)
# a date that cannot be a house number: 4-digit year, or a month name, or ISO ("1-4-15, Gandhi Nagar" is an address)
_STRONG_DATE_CORE = (
    rf"(?:{_D}[-/.]{_M}[-/.]\d{{4}}"
    rf"|{_D}[-/. ]{_MON}[-/. ,]*(?:\d{{4}}|\d{{2}})"
    r"|\d{4}-\d{2}-\d{2})"
)
_DATE = re.compile(r"(?<![\d.,])" + _DATE_CORE + r"(?!\d)")
_STRONG_DATE_AT_START = re.compile(r"^\s*" + _STRONG_DATE_CORE + r"(?!\d)")
_PERIOD_LINE = re.compile(r"^\s*" + _DATE_CORE + r"\s*(?:-|\u2013|to|TO|To)\s*" + _DATE_CORE + r"\s*$")
_TIMESTAMP_START = re.compile(r"^\s*" + _DATE_CORE + r"\s+\d{1,2}:\d{2}(?::\d{2})?\b")
_AMOUNT = re.compile(r"\d[\d,]*\.\d{2}\b")
_PERIOD_WORDS = re.compile(r"\b(?:to|from|between|period|as on|as of|generated|generation)\b", re.I)
_DATE_WORD = re.compile(r"\bdate\b", re.I)
_MONEY_WORDS = re.compile(r"balance|withdraw\w*|debit|credit|deposit\w*|amount|\bdr\b|\bcr\b", re.I)
_TEXT_WORDS = re.compile(r"narration|particulars|description|details|remarks|cheque|chq|ref(?:erence)?\b|type|value", re.I)


def _is_txn_row(line: str) -> bool:
    """A transaction row: a date and an amount on one line, or a line that starts with an unambiguous date.

    Not transaction rows: period lines ("01 Aug 2025 - 31 Aug 2025", "From 01/04/2023 To 30/06/2023") and page
    timestamps ("29-11-2022 14:41:48 BANK OF INDIA Page 1"). Names inside transaction rows are counterparties,
    never the issuer."""
    if _PERIOD_LINE.match(line):
        return False
    has_amount = bool(_AMOUNT.search(line))
    if _PERIOD_WORDS.search(line) and not has_amount:
        return False
    if _TIMESTAMP_START.match(line) and not has_amount:
        return False
    if _DATE.search(line) and has_amount:
        return True
    return bool(_STRONG_DATE_AT_START.match(line))


def _is_table_header(line: str) -> bool:
    """'Date  Narration  Withdrawal  Deposit  Balance' and its variants: the transaction table starts here."""
    if not _DATE_WORD.search(line):
        return False
    money = {m.lower() for m in _MONEY_WORDS.findall(line)}
    other = {m.lower() for m in _TEXT_WORDS.findall(line)}
    return bool(money and (len(money) + len(other)) >= 2)


def _raw_lines(text: str) -> List[str]:
    return [ln.strip() for ln in (text or "").splitlines() if ln.strip()]


def _lines(text: str) -> List[str]:
    """Lines that can carry an issuer name: transaction rows and table headers removed."""
    return [ln for ln in _raw_lines(text) if not _is_txn_row(ln) and not _is_table_header(ln)]


def _head_lines(raw: List[str]) -> List[str]:
    """The issuer block: lines above the transaction table, at most HEAD_LINES. Stops at the first table header or
    transaction row, so nothing from the table can be mistaken for the issuer."""
    head: List[str] = []
    for ln in raw[:HEAD_LINES]:
        if _is_txn_row(ln) or _is_table_header(ln):
            break
        head.append(ln)
    return head


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[0-9]+", "#", line.lower())).strip()


_COLUMN_WORDS = {"description", "details", "particulars", "narration", "debit", "credit", "dr", "cr", "amount",
                 "withdrawal", "withdrawals", "deposit", "deposits", "transaction", "remarks", "cheque"}


def _is_column_header(line: str) -> bool:
    """A transaction-table column line that does not need a 'Date' word (Value/Post Date, 'Reference ID ...')."""
    words = set(re.findall(r"[a-z]+", line.lower()))
    return "balance" in words and len(words & _COLUMN_WORDS) >= 2


STRONG_PHRASE_WEIGHT = 25


def _compact(text: str) -> str:
    return _NON_ALNUM.sub("", (text or "").lower())


class _NameIndex:
    """All names, longest first, so a long name consumes its text before a shorter one can match inside it."""

    def __init__(self, registry: BankRegistry):
        items: List[Tuple[str, str, bool]] = []  # (normalized phrase, bank_id, is_short)
        for b in registry.banks.values():
            for n in b.names:
                items.append((_norm_words(n).strip(), b.id, False))
            for n in b.short_names:
                items.append((_norm_words(n).strip(), b.id, True))
        items.sort(key=lambda t: (-len(t[0].split()), -len(t[0])))
        self.items = [
            (re.compile(r"(?<![a-z0-9])" + re.escape(p) + r"(?![a-z0-9])"), p, bid, short) for p, bid, short in items
        ]
        mask_phrases = sorted((_norm_words(m).strip() for m in registry.masks), key=lambda s: -len(s))
        self.masks = [re.compile(r"(?<![a-z0-9])" + re.escape(m) + r"(?![a-z0-9])") for m in mask_phrases]

    def scan(self, text: str) -> Dict[str, Tuple[bool, str]]:
        """bank_id -> (matched_only_as_short_name, matched text). Strongest match per bank wins."""
        s = _norm_words(text)
        for rx in self.masks:
            s = rx.sub(lambda m: "_" * len(m.group(0)), s)
        found: Dict[str, Tuple[bool, str]] = {}
        for rx, phrase, bank_id, short in self.items:
            hit = False
            def eat(m: "re.Match[str]") -> str:
                nonlocal hit
                hit = True
                return "_" * len(m.group(0))
            s = rx.sub(eat, s)
            if hit:
                prev = found.get(bank_id)
                if prev is None or (prev[0] and not short):  # a full name beats a short token
                    found[bank_id] = (short, phrase)
        return found


_INDEX_CACHE: Dict[int, _NameIndex] = {}


def _index(registry: BankRegistry) -> _NameIndex:
    key = id(registry)
    if key not in _INDEX_CACHE:
        _INDEX_CACHE[key] = _NameIndex(registry)
    return _INDEX_CACHE[key]


def _resolve_bank(registry: BankRegistry, text: Optional[str]) -> Optional[str]:
    """Map a free-text bank name (hint / metadata) to a registry id, or None."""
    if not text:
        return None
    c = _compact(text)
    if not c:
        return None
    for b in registry.banks.values():
        names = [b.id, b.display_name, *b.names, *b.short_names]
        if c in {_compact(n) for n in names}:
            return b.id
    hit = _index(registry).scan(text)
    if len(hit) == 1:
        return next(iter(hit))
    return None


def _domain_present(domain: str, text_lower: str) -> bool:
    return re.search(r"(?<![a-z0-9-])" + re.escape(domain) + r"(?![a-z0-9-])", text_lower) is not None


def detect_bank(
    page_texts: Sequence[str],
    *,
    filename: Optional[str] = None,
    metadata_bank: Optional[str] = None,
    user_hint: Optional[str] = None,
    registry: Optional[BankRegistry] = None,
) -> DetectionResult:
    reg = registry or default_registry()
    idx = _index(reg)
    pages = [t or "" for t in page_texts]
    ev: Dict[str, Dict[EvidenceKind, Evidence]] = {}  # bank_id -> kind -> evidence (one per kind)

    def add(bank_id: str, kind: EvidenceKind, weight: int, matched: str, page: Optional[int]) -> None:
        slot = ev.setdefault(bank_id, {})
        cur = slot.get(kind)
        if cur is None or weight > cur.weight:
            slot[kind] = Evidence(kind, bank_id, weight, matched[:60], page)

    looks_like_statement = False
    if pages:
        raw_pages = [_raw_lines(t) for t in pages]
        head = _head_lines(raw_pages[0])
        body = [ln for ln in raw_pages[0][len(head):] if not _is_txn_row(ln)]
        head_text = "\n".join(head)

        # a real statement has a transaction table (a date+columns header, or several dated rows) somewhere
        txn_rows = sum(1 for rp in raw_pages for ln in rp if _is_txn_row(ln))
        looks_like_statement = txn_rows >= 3 or any(_is_table_header(ln) or _is_column_header(ln) for rp in raw_pages for ln in rp)

        # names in the issuer block above the table
        for bank_id, (short, phrase) in idx.scan(head_text).items():
            add(bank_id, EvidenceKind.HEADER_NAME, SHORT_NAME_WEIGHT if short else WEIGHTS[EvidenceKind.HEADER_NAME], phrase, 1)
        # PDFs whose text layer has no spaces ("KotakMahindraBank"): match long names on the compacted head
        compact_head = _compact(head_text)
        phrases: List[Tuple[str, Optional[str], str]] = []  # (compact, bank_id or None for masks, original)
        for b in reg.banks.values():
            for n in b.names:
                c = _compact(n)
                if len(c) >= 10:
                    phrases.append((c, b.id, n))
        for m in getattr(reg, "masks", []) or []:
            c = _compact(m)
            if len(c) >= 10:
                phrases.append((c, None, m))
        phrases.sort(key=lambda x: -len(x[0]))
        for c, bank_id, n in phrases:  # longest first, each match is consumed so shorter names cannot match inside it
            if c in compact_head:
                compact_head = compact_head.replace(c, "|")
                if bank_id and not (bank_id in ev and EvidenceKind.HEADER_NAME in ev[bank_id]):
                    add(bank_id, EvidenceKind.HEADER_NAME, WEIGHTS[EvidenceKind.HEADER_NAME], n, 1)
        # names elsewhere on page 1 (weak; bare tokens ignored there)
        for bank_id, (short, phrase) in idx.scan("\n".join(body)).items():
            if not short:
                add(bank_id, EvidenceKind.PAGE1_NAME, WEIGHTS[EvidenceKind.PAGE1_NAME], phrase, 1)

        # running header/footer: the SAME line (digits ignored) at the top or bottom of 2+ pages, naming a bank.
        # Wrapped narration text differs from page to page, a real running header does not.
        edge_lines: Dict[str, List[int]] = {}
        for i, rp in enumerate(raw_pages, start=1):
            edge = [ln for ln in (rp[:EDGE_LINES] + rp[-EDGE_LINES:]) if not _is_txn_row(ln) and not _is_table_header(ln)]
            for key in {_normalize_line(ln) for ln in edge}:
                edge_lines.setdefault(key, []).append(i)
        running_text_parts: List[str] = []
        running_pages: Dict[str, List[int]] = {}
        for key, plist in edge_lines.items():
            if len(plist) >= 2:
                running_text_parts.append(key)
                for bank_id, (short, phrase) in idx.scan(key).items():
                    if not short:
                        running_pages.setdefault(bank_id, []).extend(plist)
        for bank_id, plist in running_pages.items():
            add(bank_id, EvidenceKind.RUNNING_HEADER, WEIGHTS[EvidenceKind.RUNNING_HEADER], f"pages {sorted(set(plist))[:4]}", min(plist))

        # IFSC inside the issuer block only (counterparty IFSCs appear in narrations and transaction detail)
        for line in head:
            for m in _LABELLED_IFSC.finditer(line):
                owner = reg.ifsc_owner(m.group(1)[:4])
                if owner:
                    add(owner, EvidenceKind.IFSC_LABELLED, WEIGHTS[EvidenceKind.IFSC_LABELLED], m.group(1).upper(), 1)
        for m in _BARE_IFSC.finditer(head_text):
            owner = reg.ifsc_owner(m.group(1)[:4])
            if owner:
                add(owner, EvidenceKind.IFSC_HEADER, WEIGHTS[EvidenceKind.IFSC_HEADER], m.group(1), 1)

        # domains and bank-specific wording: issuer block and running lines only
        zone_lower = (head_text + "\n" + "\n".join(running_text_parts)).lower()
        body_lower = "\n".join(body).lower()
        page1_compact = _compact(head_text + "\n" + "\n".join(body))
        for b in reg.banks.values():
            for d in b.domains:
                if _domain_present(d, zone_lower):
                    add(b.id, EvidenceKind.DOMAIN, WEIGHTS[EvidenceKind.DOMAIN], d, 1)
                    break
            else:
                for d in b.domains:  # not in the issuer block: page-1 body text that is not a transaction row (weaker)
                    if _domain_present(d, body_lower):
                        add(b.id, EvidenceKind.DOMAIN, 15, d, 1)
                        break
            for ph in b.strong_phrases:
                if _compact(ph) in page1_compact:
                    add(b.id, EvidenceKind.STATEMENT_PHRASE, STRONG_PHRASE_WEIGHT, ph, 1)
                    break
            for ph in b.statement_phrases:
                if ph in head_text.lower():
                    add(b.id, EvidenceKind.STATEMENT_PHRASE, WEIGHTS[EvidenceKind.STATEMENT_PHRASE], ph, 1)
                    break

    # ---- score
    scores: Dict[str, int] = {}
    for bank_id, slot in ev.items():
        scores[bank_id] = sum(e.weight for k, e in slot.items() if k in DOCUMENT_EVIDENCE)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    top_id, top_score = (ranked[0] if ranked else (None, 0))
    second_id, second_score = (ranked[1] if len(ranked) > 1 else (None, 0))
    margin = top_score - second_score
    kinds = len(ev.get(top_id, {})) if top_id else 0

    confidence = Confidence.UNKNOWN
    for min_score, min_margin, min_kinds, level in _THRESHOLDS:
        if top_id and top_score >= min_score and margin >= min_margin and kinds >= min_kinds:
            confidence = level
            break

    not_a_statement = False
    if pages and not looks_like_statement and confidence in (Confidence.VERY_HIGH, Confidence.HIGH, Confidence.MEDIUM):
        not_a_statement = True
        confidence = Confidence.LOW   # a bank name on a document with no transaction table (payslip, letter) is not a statement

    # ---- supporting evidence: recorded, never counted
    supporting: List[Evidence] = []
    fname = _compact(filename or "")
    if fname:
        for b in reg.banks.values():
            tokens = {_compact(n) for n in list(b.names) + list(b.short_names) + [b.id]}
            tokens |= {p.lower() for p in b.ifsc_prefixes}
            if any(len(t) >= 4 and t in fname for t in tokens):
                supporting.append(Evidence(EvidenceKind.FILENAME, b.id, SUPPORT_WEIGHT, filename or "", None))
    hint_ids: List[str] = []
    for kind, text in ((EvidenceKind.METADATA, metadata_bank), (EvidenceKind.USER_HINT, user_hint)):
        rid = _resolve_bank(reg, text)
        if rid:
            supporting.append(Evidence(kind, rid, SUPPORT_WEIGHT, str(text), None))
            hint_ids.append(rid)

    winner = reg.get(top_id) if confidence != Confidence.UNKNOWN else None
    hint_conflict = bool(
        winner and confidence in (Confidence.MEDIUM, Confidence.HIGH, Confidence.VERY_HIGH)
        and any(h != winner.id for h in hint_ids)
    )

    chosen = ev.get(top_id, {}) if winner else {}
    document_ev = sorted(chosen.values(), key=lambda e: -e.weight)
    return DetectionResult(
        bank_id=winner.id if winner else None,
        bank_name=winner.display_name if winner else None,
        confidence=confidence,
        score=top_score if winner else 0,
        runner_up_id=second_id,
        runner_up_score=second_score,
        supported=bool(winner and winner.supported),
        processor_key=winner.processor_key if winner else None,
        evidence=document_ev,
        supporting=supporting,
        hint_conflict=hint_conflict,
        looks_like_statement=looks_like_statement if pages else False,
        reason=(
            "A bank name was found, but the document has no transaction table, so it does not look like a bank statement."
            if not_a_statement
            else _reason(reg, winner.id if winner else None, confidence, document_ev, top_id, top_score, second_id, second_score)
        ),
    )


def _reason(reg, bank_id, confidence, evidence, top_id, top_score, second_id, second_score) -> str:
    if bank_id and evidence:
        parts = {
            EvidenceKind.IFSC_LABELLED: "a labelled IFSC code",
            EvidenceKind.IFSC_HEADER: "an IFSC code in the header",
            EvidenceKind.HEADER_NAME: "the bank name in the page header",
            EvidenceKind.RUNNING_HEADER: "the bank name repeated on several pages",
            EvidenceKind.DOMAIN: "the bank's website",
            EvidenceKind.PAGE1_NAME: "the bank name on page 1",
            EvidenceKind.STATEMENT_PHRASE: "bank-specific wording",
        }
        return "Found " + ", ".join(parts[e.kind] for e in evidence if e.kind in parts) + "."
    if top_id and second_id and second_score and top_score - second_score < 8:
        a, b = reg.get(top_id), reg.get(second_id)
        return f"The statement points to both {a.display_name} and {b.display_name}."
    if top_id:
        return "Only weak signs of a bank were found in the statement."
    return "No bank name or IFSC code was found in the statement header."
