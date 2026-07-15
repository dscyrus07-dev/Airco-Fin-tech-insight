"""
Airco Insights - IDFC Bank Structure Validator
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .._shared.generic_bank import GenericStructureError, GenericStructureMetadata, GenericStructureResult

logger = logging.getLogger(__name__)


@dataclass
class IDFCStatementMetadata(GenericStructureMetadata):
    @property
    def expected_transaction_count(self) -> Optional[int]:
        return None


class IDFCStructureValidator:
    PERIOD_PATTERNS = [
        r"STATEMENT\s+PERIOD\s*:\s*(\d{4}-\d{2}-\d{2})\s+TO\s+(\d{4}-\d{2}-\d{2})",
    ]

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, text_content: str, first_page_text: str = "") -> GenericStructureResult:
        header_text = first_page_text or text_content[:8000]
        confidence = self._check_markers(header_text)
        if confidence < 0.2:
            raise GenericStructureError(
                "PDF does not appear to be an IDFC Bank statement",
                error_code="NOT_IDFC_STATEMENT",
                details={"confidence": confidence},
            )

        metadata = self._extract_metadata(text_content)
        if not self._has_transaction_table(text_content):
            raise GenericStructureError(
                "Could not identify transaction table in IDFC statement",
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
            r"STATEMENT\s+OF\s+ACCOUNT",
            r"IFSC\s*:\s*IDFB[0-9A-Z]{7}",
            r"STATEMENT\s+PERIOD\s*:\s*\d{4}-\d{2}-\d{2}\s+TO\s+\d{4}-\d{2}-\d{2}",
            r"Transaction\s+Date\s+Value\s+Date\s+Particulars\s+Cheque\s+Debit\s+Credit\s+Balance",
            r"Opening\s+Balance\s+Total\s+Debit\s+Total\s+Credit\s+Closing\s+Balance",
        ]
        found = sum(1 for marker in markers if re.search(marker, text, re.IGNORECASE))
        return min(found / 4, 1.0)

    def _has_transaction_table(self, text: str) -> bool:
        return bool(
            re.search(r"Transaction\s+Date\s+Value\s+Date\s+Particulars\s+Cheque\s+Debit\s+Credit\s+Balance", text, re.IGNORECASE)
            or re.search(r"\d{2}-[A-Za-z]{3}-\d{4}\s+\d{2}-[A-Za-z]{3}-\d{4}\s+", text)
        )

    def _extract_metadata(self, text_content: str) -> IDFCStatementMetadata:
        metadata = IDFCStatementMetadata()

        account_match = re.search(r"ACCOUNT\s+NO\s*:\s*(\d{10,18})", text_content, re.IGNORECASE)
        if account_match:
            metadata.account_number = account_match.group(1)

        customer_match = re.search(r"CUSTOMER\s+NAME\s*:\s*([^\n]+)", text_content, re.IGNORECASE)
        if customer_match:
            metadata.account_holder = customer_match.group(1).strip()

        ifsc_match = re.search(r"IFSC\s*:\s*(IDFB[0-9A-Z]{7})", text_content, re.IGNORECASE)
        if ifsc_match:
            metadata.ifsc = ifsc_match.group(1)

        period_match = re.search(self.PERIOD_PATTERNS[0], text_content, re.IGNORECASE)
        if period_match:
            metadata.statement_from = period_match.group(1)
            metadata.statement_to = period_match.group(2)

        summary_match = re.search(
            r"Opening\s+Balance\s+Total\s+Debit\s+Total\s+Credit\s+Closing\s+Balance\s+([-\d,]+\.\d{2})\s+([-\d,]+\.\d{2})\s+([-\d,]+\.\d{2})\s+([-\d,]+\.\d{2})",
            text_content,
            re.IGNORECASE,
        )
        if summary_match:
            metadata.opening_balance = self._parse_amount(summary_match.group(1))
            metadata.total_debits = self._parse_amount(summary_match.group(2))
            metadata.total_credits = self._parse_amount(summary_match.group(3))
            metadata.closing_balance = self._parse_amount(summary_match.group(4))

        if metadata.opening_balance is None:
            opening_match = re.search(r"Opening\s+Balance\s+([-\d,]+\.\d{2})", text_content, re.IGNORECASE)
            if opening_match:
                metadata.opening_balance = self._parse_amount(opening_match.group(1))

        try:
            from .._shared.rich_metadata import enrich_statement_metadata
            enrich_statement_metadata(metadata, text_content, text_content[:8000], ifsc_prefix="IDFB")
        except Exception:
            pass
        return metadata


    def _parse_amount(self, value: str) -> Optional[float]:
        try:
            return float(value.replace(",", "").strip())
        except Exception:
            return None


# Re-export for compatibility
IDFCStructureError = GenericStructureError
