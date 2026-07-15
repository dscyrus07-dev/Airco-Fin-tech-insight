"""Airco Insights - Indian Bank Parser"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .._shared.generic_bank import GenericBankConfig, GenericParseError, GenericParser, GenericTransaction

from .structure_validator import INDIAN_BANK_CONFIG

logger = logging.getLogger(__name__)


@dataclass
class IndianBankParseResult:
    transactions: List[GenericTransaction]
    total_count: int
    parse_method: str
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_credits: float = 0.0
    total_debits: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_count": self.total_count,
            "parse_method": self.parse_method,
            "opening_balance": self.opening_balance,
            "closing_balance": self.closing_balance,
            "total_credits": self.total_credits,
            "total_debits": self.total_debits,
            "warnings": self.warnings,
        }


class IndianBankParser:
    BANK_NAME = "Indian Bank"

    # Matches a transaction date at the start: "02 Feb 2026"
    _DATE_RE = re.compile(r"^(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})\b")

    # Matches an INR amount: "INR 40,000.00"  or  "INR 40000.00"
    _INR_AMT_RE = re.compile(r"INR\s+([\d,]+\.\d{2})")

    # Matches the tail of a transaction date-line:
    # <debit_col> <credit_col> INR <balance>
    # Each of debit/credit col is either "INR 12,345.67" or "-"
    _TXN_TAIL_RE = re.compile(
        r"(?P<debit>INR\s+[\d,]+\.\d{2}|-)\s+(?P<credit>INR\s+[\d,]+\.\d{2}|-)\s+INR\s+(?P<balance>[\d,]+\.\d{2})\s*$"
    )

    _SKIP_TOKENS = frozenset([
        "account statement", "account details", "account summary",
        "account activity", "date transaction details debits credits",
        "generated on", "page ", "opening balance", "ending balance",
        "closing balance", "total credits", "total debits",
    ])

    def __init__(self, audit_service=None, job_id=None):
        self.bank_name = self.BANK_NAME
        self.audit_service = audit_service
        self.job_id = job_id
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._parser = GenericParser(INDIAN_BANK_CONFIG)
        self._hygiene_result = None
        self._collected_parser_metrics = []

    def parse(self, file_path: str, text_content: str = "") -> IndianBankParseResult:
        try:
            text = text_content or self._extract_text(file_path)
        except Exception as exc:
            raise GenericParseError(str(exc), error_code="EXTRACTION_ERROR") from exc

        transactions = self._parse_inr_column_format(text)

        if not transactions:
            try:
                result = self._parser.parse(file_path, text)
                transactions = list(result.transactions or [])
                parse_method = "generic"
            except GenericParseError:
                raise
        else:
            parse_method = "inr_column"

        metadata = self._extract_metadata(text)
        opening_balance = self._as_float(metadata.get("opening_balance"))
        closing_balance = self._as_float(metadata.get("closing_balance"))

        if opening_balance is None and transactions:
            first = transactions[0]
            if first.balance is not None:
                opening_balance = round(float(first.balance) + float(first.debit or 0) - float(first.credit or 0), 2)

        if closing_balance is None and transactions:
            closing_balance = self._as_float(getattr(transactions[-1], "balance", None))

        total_credits = sum(float(getattr(t, "credit", 0) or 0) for t in transactions)
        total_debits = sum(float(getattr(t, "debit", 0) or 0) for t in transactions)

        return IndianBankParseResult(
            transactions=transactions,
            total_count=len(transactions),
            parse_method=parse_method,
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits,
        )

    # ── dedicated INR-column parser ────────────────────────────────────────────

    def _parse_inr_column_format(self, text: str) -> List[GenericTransaction]:
        """Parse Indian Bank's 'Date | Details | Debits | Credits | Balance' layout.

        Each transaction starts with a date line of the form:
            DD Mon YYYY  <partial description>  [INR debit|-]  [INR credit|-]  INR balance
        Continuation lines follow with no date.
        """
        lines = [l.strip() for l in text.splitlines()]
        transactions: List[GenericTransaction] = []

        current_date: Optional[str] = None
        current_desc_parts: List[str] = []
        current_debit: float = 0.0
        current_credit: float = 0.0
        current_balance: Optional[float] = None

        def flush() -> None:
            if current_date is None:
                return
            desc = " ".join(current_desc_parts).strip()
            transactions.append(GenericTransaction(
                date=current_date,
                description=desc,
                debit=current_debit,
                credit=current_credit,
                balance=current_balance,
            ))

        for line in lines:
            if not line:
                continue

            low = line.lower()
            if any(tok in low for tok in self._SKIP_TOKENS):
                continue

            dm = self._DATE_RE.match(line)
            if dm:
                tail_m = self._TXN_TAIL_RE.search(line)
                if tail_m:
                    # This line is a complete transaction start with amounts
                    flush()
                    current_date = self._normalize_date(dm.group(1))
                    desc_text = line[dm.end():tail_m.start()].strip()
                    current_desc_parts = [desc_text] if desc_text else []
                    current_debit = self._inr_to_float(tail_m.group("debit"))
                    current_credit = self._inr_to_float(tail_m.group("credit"))
                    current_balance = self._clean_amount(tail_m.group("balance"))
                    continue
                else:
                    # Date line but no tail amounts yet — rare, treat as new txn start
                    flush()
                    current_date = self._normalize_date(dm.group(1))
                    current_desc_parts = [line[dm.end():].strip()]
                    current_debit = 0.0
                    current_credit = 0.0
                    current_balance = None
                    continue

            # Continuation line — if we have an open transaction, append description
            if current_date is not None:
                # Check if this continuation line has a tail (amounts on a wrapped line)
                tail_m = self._TXN_TAIL_RE.search(line)
                if tail_m and current_balance is None:
                    desc_text = line[:tail_m.start()].strip()
                    if desc_text:
                        current_desc_parts.append(desc_text)
                    current_debit = self._inr_to_float(tail_m.group("debit"))
                    current_credit = self._inr_to_float(tail_m.group("credit"))
                    current_balance = self._clean_amount(tail_m.group("balance"))
                else:
                    current_desc_parts.append(line)

        flush()
        return transactions

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _inr_to_float(col_text: str) -> float:
        """Convert 'INR 40,000.00' → 40000.0, '-' → 0.0."""
        if not col_text or col_text.strip() == "-":
            return 0.0
        m = re.search(r"([\d,]+\.\d{2})", col_text)
        if m:
            return float(m.group(1).replace(",", ""))
        return 0.0

    @staticmethod
    def _clean_amount(value: str) -> Optional[float]:
        if not value:
            return None
        try:
            return float(value.replace(",", ""))
        except Exception:
            return None

    @staticmethod
    def _normalize_date(date_text: str) -> str:
        for fmt in ("%d %b %Y", "%d %b %y"):
            try:
                return datetime.strptime(date_text.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return date_text

    def _extract_text(self, file_path: str) -> str:
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    pages.append(page.extract_text() or "")
            return "\n".join(pages)
        except Exception:
            pass
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except Exception:
            return ""

    def _extract_metadata(self, text: str) -> dict:
        meta: dict = {}
        m = re.search(r"Opening Balance\s+INR\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if m:
            meta["opening_balance"] = self._clean_amount(m.group(1))
        m = re.search(r"(?:Ending|Closing) Balance\s+INR\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if m:
            meta["closing_balance"] = self._clean_amount(m.group(1))
        return meta

    @staticmethod
    def _as_float(value) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except Exception:
            try:
                return float(str(value).replace(",", ""))
            except Exception:
                return None


IndianBankParseError = GenericParseError
