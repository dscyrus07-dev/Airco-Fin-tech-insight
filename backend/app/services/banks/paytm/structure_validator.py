"""
Airco Insights - Paytm Bank Structure Validator
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .._shared.generic_bank import GenericStructureError, GenericStructureMetadata, GenericStructureResult

logger = logging.getLogger(__name__)


@dataclass
class PaytmStatementMetadata(GenericStructureMetadata):
    @property
    def expected_transaction_count(self) -> Optional[int]:
        return None


class PaytmStructureValidator:
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, text_content: str, first_page_text: str = "") -> GenericStructureResult:
        header_text = first_page_text or text_content[:8000]
        confidence = self._check_markers(header_text)
        if confidence < 0.2:
            raise GenericStructureError(
                "PDF does not appear to be a Paytm Bank statement",
                error_code="NOT_PAYTM_STATEMENT",
                details={"confidence": confidence},
            )

        metadata = self._extract_metadata(text_content)
        if not self._has_transaction_table(text_content):
            raise GenericStructureError(
                "Could not identify transaction blocks in Paytm statement",
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
            r"Account statement for:\d{2} [A-Za-z]{3} \d{4} to \d{2} [A-Za-z]{3} \d{4}",
            r"OPENING BALANCE TOTAL DEPOSIT TOTAL WITHDRAWAL CLOSING BALANCE",
            r"ACCOUNT NUMBER ACCOUNT TYPE IFSC MICR NOMINEE",
            r"DATE & TIME TRANSACTION DETAILS AMOUNT AVAILABLE BALANCE",
            r"PYTM\d{7,10}",
        ]
        found = sum(1 for marker in markers if re.search(marker, text, re.IGNORECASE))
        return min(found / 4, 1.0)

    def _has_transaction_table(self, text: str) -> bool:
        return bool(
            re.search(r"DATE\s*&\s*TIME\s+TRANSACTION\s+DETAILS\s+AMOUNT\s+AVAILABLE\s+BALANCE", text, re.IGNORECASE)
            or re.search(r"\d{2} [A-Za-z]{3} \d{4} .+[+-] Rs\.[\d,]+\.\d{2} Rs\.[\d,]+\.\d{2}", text)
        )

    def _extract_metadata(self, text: str) -> PaytmStatementMetadata:
        metadata = PaytmStatementMetadata()

        name_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
        if name_line:
            metadata.account_holder = name_line

        account_match = re.search(r"\n(\d{12})\s+(?:Current|Savings)\s+Account\s+(PYTM\d{7,10})", text, re.IGNORECASE)
        if account_match:
            metadata.account_number = account_match.group(1)
            metadata.ifsc = account_match.group(2)
        else:
            account_match = re.search(r"ACCOUNT NUMBER ACCOUNT TYPE IFSC MICR NOMINEE\s+(\d{12})", text, re.IGNORECASE)
            if account_match:
                metadata.account_number = account_match.group(1)
            ifsc_match = re.search(r"\b(PYTM\d{7,10})\b", text)
            if ifsc_match:
                metadata.ifsc = ifsc_match.group(1)

        period_match = re.search(
            r"Account statement for:(\d{2} [A-Za-z]{3} \d{4}) to (\d{2} [A-Za-z]{3} \d{4})",
            text,
            re.IGNORECASE,
        )
        if period_match:
            metadata.statement_from = period_match.group(1)
            metadata.statement_to = period_match.group(2)

        summary_match = re.search(
            r"Rs\.\s*([-\d,]+\.\d{2})\s+Rs\.\s*([-\d,]+\.\d{2})\s+Rs\.\s*([-\d,]+\.\d{2})\s+Rs\.\s*([-\d,]+\.\d{2})\s+OPENING BALANCE TOTAL DEPOSIT TOTAL WITHDRAWAL CLOSING BALANCE",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if summary_match:
            metadata.opening_balance = self._parse_amount(summary_match.group(1))
            metadata.total_credits = self._parse_amount(summary_match.group(2))
            metadata.total_debits = self._parse_amount(summary_match.group(3))
            metadata.closing_balance = self._parse_amount(summary_match.group(4))

        try:
            from .._shared.rich_metadata import enrich_statement_metadata
            enrich_statement_metadata(metadata, text, text[:8000], ifsc_prefix="PYTM")
        except Exception:
            pass
        return metadata


    def _parse_amount(self, value: str) -> Optional[float]:
        try:
            return float(value.replace(",", "").strip())
        except Exception:
            return None


# Re-export for compatibility
PaytmStructureError = GenericStructureError
