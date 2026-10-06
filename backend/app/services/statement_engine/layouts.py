"""Layout registry (Slice 2C).

BANK and LAYOUT are separate concepts: a bank can print several layouts, and one layout can be shared by banks.
A layout here is recognised from the transaction table's column header (what the text layer actually contains),
never from the bank name. If no registered rule matches, the layout is UNKNOWN: no confidence is invented.

Today every layout is still processed by the existing bank-specific processor ("legacy:<processor_key>"); the
`parser_family` field is where a shared parser will plug in later (strangler pattern) without changing the API.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

from .contracts import Confidence
from .registry import BankRegistry, default_registry

UNKNOWN_LAYOUT_ID = "UNKNOWN"

# words that make up transaction-table column headers
_COLUMN_VOCAB = frozenset({
    "date", "value", "post", "narration", "description", "particulars", "details", "remitter", "chq", "cheque",
    "ref", "withdrawal", "withdrawals", "debit", "credit", "deposit", "deposits", "balance", "amount", "type",
    "dr", "cr", "transaction", "txn", "remarks",
})
# Some statements print column titles glued together ("WithdrawalAmt.", "ClosingBalance", "ValueDt"). These
# fillers let such a token be split into vocabulary words; a token that cannot be split fully is ignored as before.
_GLUE_FILLERS = frozenset({"amt", "dt", "closing", "no"})
_SPLITTABLE = _COLUMN_VOCAB | _GLUE_FILLERS


def _split_glued(token: str) -> Tuple[str, ...]:
    """Segment `token` into known header words, or return () when it is not made only of them."""
    if token in _COLUMN_VOCAB:
        return (token,)
    best: Dict[int, Optional[Tuple[str, ...]]] = {0: ()}
    for end in range(1, len(token) + 1):
        best[end] = None
        for start in range(max(0, end - 11), end):
            part = token[start:end]
            if best.get(start) is not None and part in _SPLITTABLE:
                best[end] = best[start] + (part,)
                break
    parts = best[len(token)]
    return tuple(w for w in parts if w in _COLUMN_VOCAB) if parts else ()


def _header_words(text: str) -> FrozenSet[str]:
    words = set()
    for tok in re.findall(r"[a-z]+", text.lower()):
        words.update(_split_glued(tok))
    return frozenset(words)


_MONEY_WORDS = frozenset({"balance", "amount", "debit", "credit", "withdrawal", "withdrawals", "deposit", "deposits", "dr", "cr"})


@dataclass(frozen=True)
class LayoutDefinition:
    layout_id: str
    description: str
    required_words: FrozenSet[str]            # all must be present in the column header
    forbidden_words: FrozenSet[str] = frozenset()
    supported_banks: Tuple[str, ...] = ()     # empty = any bank
    date_formats: Tuple[str, ...] = ()
    multiline_rows: bool = False              # narration commonly wraps onto the next line
    running_balance: bool = True              # a balance column is present on every row

    def matches(self, words: FrozenSet[str], bank_id: Optional[str]) -> bool:
        if not self.required_words <= words:
            return False
        if self.forbidden_words & words:
            return False
        if self.supported_banks and bank_id and bank_id not in self.supported_banks:
            return False
        return True


# Most specific first. Built only from column layouts present in the benchmark corpus.
DEFAULT_LAYOUTS: Tuple[LayoutDefinition, ...] = (
    # HDFC account statement: "Date Narration Chq./Ref.No. ValueDt WithdrawalAmt. DepositAmt. ClosingBalance"
    # (also printed with spaced words). 99% of the HDFC benchmark corpus; value-date and reference columns present.
    LayoutDefinition("hdfc_date_narration_ref_valuedt_withdrawal_deposit_closing",
                     "HDFC: date, narration, chq/ref no, value date, withdrawal, deposit, closing balance",
                     frozenset({"date", "narration", "chq", "ref", "value", "withdrawal", "deposit", "balance"}),
                     supported_banks=("hdfc",), date_formats=("dd/mm/yy",), multiline_rows=True),
    LayoutDefinition("value_post_remitter_dr_cr_balance",
                     "Value date, post date, remitter branch, description, DR/CR, balance",
                     frozenset({"value", "post", "remitter", "balance"}), date_formats=("dd/mm/yyyy",), multiline_rows=True),
    LayoutDefinition("date_narration_withdrawal_deposit_balance",
                     "Date, narration, withdrawal, deposit, balance",
                     frozenset({"date", "narration", "withdrawal", "deposit", "balance"}), multiline_rows=True),
    LayoutDefinition("date_narration_withdrawal_deposit_balance",
                     "Date, narration, withdrawals, deposits, balance",
                     frozenset({"date", "narration", "withdrawals", "deposits", "balance"}), multiline_rows=True),
    LayoutDefinition("date_particulars_debit_credit_balance",
                     "Date, particulars, debit, credit, balance",
                     frozenset({"date", "particulars", "debit", "credit", "balance"}), multiline_rows=True),
    LayoutDefinition("date_description_debit_credit_balance",
                     "Date, description, debit, credit, balance",
                     frozenset({"date", "description", "debit", "credit", "balance"}), multiline_rows=True),
    LayoutDefinition("date_description_amount_type",
                     "Date, description, amount, DR/CR type (export style, no running balance)",
                     frozenset({"date", "description", "amount", "type"}), forbidden_words=frozenset({"balance"}),
                     multiline_rows=True, running_balance=False),
    LayoutDefinition("details_amount_balance",
                     "Transaction details, amount, balance (app export with day-grouped dates)",
                     frozenset({"details", "amount", "balance"}), multiline_rows=False),
)


@dataclass
class LayoutResult:
    layout_id: str = UNKNOWN_LAYOUT_ID
    confidence: Confidence = Confidence.UNKNOWN
    description: str = ""
    parser_family: Optional[str] = None
    column_header: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.layout_id,
            "confidence": self.confidence.value,
            "description": self.description,
            "parser_family": self.parser_family,
        }


class LayoutRegistry:
    def __init__(self, layouts: Sequence[LayoutDefinition] = DEFAULT_LAYOUTS, bank_registry: Optional[BankRegistry] = None):
        self.layouts = list(layouts)
        self._banks = bank_registry

    def _processor_key(self, bank_id: Optional[str]) -> Optional[str]:
        reg = self._banks or default_registry()
        cfg = reg.get(bank_id)
        return cfg.processor_key if cfg else None

    def ids(self) -> List[str]:
        return sorted({l.layout_id for l in self.layouts})

    def detect(self, page_texts: Sequence[str], bank_id: Optional[str] = None) -> LayoutResult:
        header_words, header_line = _find_column_header(page_texts)
        if not header_words:
            return LayoutResult()
        for layout in self.layouts:
            if layout.matches(header_words, bank_id):
                key = self._processor_key(bank_id)
                return LayoutResult(
                    layout_id=layout.layout_id,
                    confidence=Confidence.HIGH,
                    description=layout.description,
                    parser_family=f"legacy:{key}" if key else None,
                    column_header=header_line[:120],
                )
        return LayoutResult(column_header=header_line[:120])


def _find_column_header(page_texts: Sequence[str]) -> Tuple[FrozenSet[str], str]:
    """First line (pages 1-2) that looks like a transaction-table header. A header may wrap over two lines."""
    for text in list(page_texts)[:2]:
        lines = [ln.strip() for ln in (text or "").splitlines() if ln.strip()]
        for i, ln in enumerate(lines):
            words = _header_words(ln)
            if len(words) < 3 and i + 1 < len(lines):  # wrapped header: join with the next line
                words = _header_words(ln + " " + lines[i + 1])
            if len(words) >= 3 and words & _MONEY_WORDS and (words & {"date", "value", "post", "details", "transaction", "txn"}):
                return words, ln
    return frozenset(), ""


_default: Optional[LayoutRegistry] = None


def default_layout_registry() -> LayoutRegistry:
    global _default
    if _default is None:
        _default = LayoutRegistry()
    return _default


def detect_layout(page_texts: Sequence[str], bank_id: Optional[str] = None) -> LayoutResult:
    return default_layout_registry().detect(page_texts, bank_id)
