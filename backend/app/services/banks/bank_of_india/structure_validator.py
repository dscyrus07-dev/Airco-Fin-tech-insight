"""Airco Insights - Bank of India Structure Validator"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .._shared.generic_bank import (
    GenericBankConfig,
    GenericStructureError,
    GenericStructureMetadata,
    GenericStructureResult,
    GenericStructureValidator,
)

logger = logging.getLogger(__name__)

BANK_OF_INDIA_CONFIG = GenericBankConfig(
    bank_key="bank_of_india",
    bank_name="Bank of India",
    file_prefix="bank_of_india",
    markers=[
        "detailed statement",
        "customer id",
        "account holder name",
        "account number",
        "transaction type",
        "sr no",
        "debit credit balance",
        "bank of india",
        "boi",
        "bkid",
    ],
    support_aliases=[
        "bank of india",
        "bankofindia",
        "boi",
        "bkid",
    ],
)


@dataclass
class BankOfIndiaStatementMetadata(GenericStructureMetadata):
    @property
    def expected_transaction_count(self) -> Optional[int]:
        return None


class BankOfIndiaStructureValidator:
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._delegate = GenericStructureValidator(BANK_OF_INDIA_CONFIG)

    def validate(self, text_content: str, first_page_text: str = "") -> GenericStructureResult:
        header_text = first_page_text or text_content[:8000]
        result = self._delegate.validate(text_content, first_page_text)
        self._patch_metadata(result.metadata, text_content, header_text)
        return result

    def _patch_metadata(self, metadata: GenericStructureMetadata, full_text: str, header_text: str) -> None:
        text = f"{header_text}\n{full_text}"

        if not metadata.account_holder:
            match = re.search(
                r"Account holder name:\s*(.+?)(?:\n|Account number:|Customer ID:|IFSC:)",
                text,
                re.IGNORECASE | re.DOTALL,
            )
            if match:
                metadata.account_holder = " ".join(match.group(1).split())

        if not metadata.account_number:
            match = re.search(r"Account number:\s*(\d{8,20})", text, re.IGNORECASE)
            if match:
                metadata.account_number = match.group(1)

        period_match = re.search(
            r"from:\s*(\d{2}[\-/]\d{2}[\-/]\d{4})\s*to:\s*(\d{2}[\-/]\d{2}[\-/]\d{4})",
            text,
            re.IGNORECASE,
        )
        if period_match:
            metadata.statement_from = period_match.group(1).strip()
            metadata.statement_to = period_match.group(2).strip()

        if metadata.opening_balance is None:
            opening_match = re.search(r"Opening Balance\s*[:\-]?\s*INR\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
            if opening_match:
                metadata.opening_balance = self._parse_amount(opening_match.group(1))

        if metadata.closing_balance is None:
            closing_match = re.search(
                r"(?:Ending|Closing) Balance\s*[:\-]?\s*INR\s*([\d,]+\.\d{2})",
                text,
                re.IGNORECASE,
            )
            if closing_match:
                metadata.closing_balance = self._parse_amount(closing_match.group(1))

        if metadata.ifsc is None:
            ifsc_match = re.search(r"\b(BKID[0-9A-Z]{7})\b", text, re.IGNORECASE)
            if ifsc_match:
                metadata.ifsc = ifsc_match.group(1).upper()

        try:
            from .._shared.rich_metadata import enrich_statement_metadata
            enrich_statement_metadata(metadata, full_text, header_text, ifsc_prefix="BKID")
        except Exception:
            pass

    @staticmethod
    def _parse_amount(value: str) -> Optional[float]:

        try:
            return float(value.replace(",", "").strip())
        except Exception:
            return None


BankOfIndiaStructureError = GenericStructureError
