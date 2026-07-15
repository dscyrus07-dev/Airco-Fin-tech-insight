"""
Airco Insights - Unknown Bank Structure Validator
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .._shared.generic_bank import GenericStructureError, GenericStructureMetadata, GenericStructureResult

logger = logging.getLogger(__name__)


@dataclass
class UnknownStatementMetadata(GenericStructureMetadata):
    @property
    def expected_transaction_count(self) -> Optional[int]:
        return None


class UnknownStructureValidator:
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, text_content: str, first_page_text: str = "") -> GenericStructureResult:
        header_text = first_page_text or text_content[:8000]
        confidence = self._check_markers(header_text)
        if confidence < 0.35:
            raise GenericStructureError(
                "PDF does not match the supported emergency unknown-bank format",
                error_code="NOT_SUPPORTED_UNKNOWN_STATEMENT",
                details={"confidence": confidence},
            )

        metadata = self._extract_metadata(text_content)
        if not self._has_transaction_table(text_content):
            raise GenericStructureError(
                "Could not identify transaction table in unknown-bank statement",
                error_code="NO_TRANSACTION_TABLE",
                details={},
            )

        return GenericStructureResult(
            is_valid=True,
            confidence=confidence,
            metadata=metadata,
            text_content=text_content,
        )

    def _check_markers(self, text: str) -> float:
        markers = [
            r"StatementofBankingAccount",
            r"CRN\s+No\.\s+\d+",
            r"Account\s+No\.\s+\d+",
            r"Date\s+Narration\s+Chq/Ref\s+No\.\s+Withdrawal\(Dr\)\s+Deposit\(Cr\)\s+Balance",
        ]
        found = sum(1 for marker in markers if re.search(marker, text, re.IGNORECASE))
        return min(found / 3, 1.0)

    def _has_transaction_table(self, text: str) -> bool:
        return bool(
            re.search(r"Date\s+Narration\s+Chq/Ref\s+No\.\s+Withdrawal\(Dr\)\s+Deposit\(Cr\)\s+Balance", text, re.IGNORECASE)
            and re.search(r"\d{2}-[A-Za-z]{3}-\d{2}.+\d+\.\d{2}\([CD]r\)", text)
        )

    def _extract_metadata(self, text: str) -> UnknownStatementMetadata:
        metadata = UnknownStatementMetadata()
        first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if first_line:
            name_match = re.match(r"(.+?)\s+Period\s+\d{2}-[A-Za-z]{3}-\d{2}to\d{2}-[A-Za-z]{3}-\d{2}", first_line)
            metadata.account_holder = name_match.group(1).strip() if name_match else first_line

        period_match = re.search(r"Period\s+(\d{2}-[A-Za-z]{3}-\d{2})to(\d{2}-[A-Za-z]{3}-\d{2})", text, re.IGNORECASE)
        if period_match:
            metadata.statement_from = period_match.group(1)
            metadata.statement_to = period_match.group(2)

        account_match = re.search(r"Account\s+No\.\s+(\d{8,20})", text, re.IGNORECASE)
        if account_match:
            metadata.account_number = account_match.group(1)

        opening_match = re.search(r"OpeningBalance\s+([-\d,]+\.\d{2})\([CD]r\)", text, re.IGNORECASE)
        if opening_match:
            metadata.opening_balance = self._parse_amount(opening_match.group(1))

        closing_match = re.search(r"ClosingBalance\s+([-\d,]+\.\d{2})\([CD]r\)", text, re.IGNORECASE)
        if closing_match:
            metadata.closing_balance = self._parse_amount(closing_match.group(1))

        try:
            from .._shared.rich_metadata import enrich_statement_metadata
            enrich_statement_metadata(metadata, text, text[:8000])
        except Exception:
            pass
        return metadata


    def _parse_amount(self, value: str) -> Optional[float]:
        try:
            return float(value.replace(",", "").strip())
        except Exception:
            return None


# Re-export for compatibility
UnknownStructureError = GenericStructureError
