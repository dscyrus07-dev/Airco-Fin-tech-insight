"""
Airco Insights - Canara Bank Structure Validator
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .._shared.generic_bank import GenericStructureError, GenericStructureMetadata, GenericStructureResult

logger = logging.getLogger(__name__)


@dataclass
class CanaraStatementMetadata(GenericStructureMetadata):
    @property
    def expected_transaction_count(self) -> Optional[int]:
        return None


class CanaraStructureValidator:
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, text_content: str, first_page_text: str = "") -> GenericStructureResult:
        header_text = first_page_text or text_content[:8000]
        confidence = self._check_markers(header_text)
        if confidence < 0.3:
            raise GenericStructureError(
                "PDF does not appear to be a Canara Bank statement",
                error_code="NOT_CANARA_STATEMENT",
                details={"confidence": confidence},
            )

        metadata = self._extract_metadata(text_content)
        if not self._has_transaction_table(text_content):
            raise GenericStructureError(
                "Could not identify transaction table in Canara statement",
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
            r"Current\s*&\s*Saving\s*Account\s*Statement",
            r"Canara\s*Bank",
            r"CNRB",
            r"IFSC\s*Code\s+CNRB[0-9A-Z]{7}",
            r"Txn\s*Date\s+Value\s*Date\s+Cheque\s*No\.\s+Description\s+Branch\s+Debit\s+Credit\s+Balance",
            r"Searched\s*By\s*From\s+\d{2}\s+[A-Za-z]{3}\s+\d{4}\s+To\s+\d{2}\s+[A-Za-z]{3}\s+\d{4}",
        ]
        found = sum(1 for marker in markers if re.search(marker, text, re.IGNORECASE))
        return min(found / 3, 1.0)

    def _has_transaction_table(self, text: str) -> bool:
        return bool(
            re.search(r"Txn\s*Date\s+Value\s*Date\s+Cheque\s*No\.\s+Description\s+Branch\s+Debit\s+Credit\s+Balance", text, re.IGNORECASE)
            or re.search(r"\d{2}-\d{2}-\d{4}\s+\d{2}:\d{2}:\d{2}\s+\d{2}\s+[A-Za-z]{3}\s+\d{4}", text)
        )

    def _extract_metadata(self, text: str) -> CanaraStatementMetadata:
        metadata = CanaraStatementMetadata()

        holder_match = re.search(r"Account\s*Holders?'?\s*Name\s+([^\n]+)", text, re.IGNORECASE)
        if not holder_match:
            holder_match = re.search(r"Account\s*Holders\s*Name\s+([^\n]+)", text, re.IGNORECASE)
        if holder_match:
            metadata.account_holder = holder_match.group(1).strip()

        account_match = re.search(r"Account\s*Number\s+(\d{10,18})", text, re.IGNORECASE)
        if account_match:
            metadata.account_number = account_match.group(1)

        ifsc_match = re.search(r"IFSC\s*Code\s+(CNRB[0-9A-Z]{7})", text, re.IGNORECASE)
        if ifsc_match:
            metadata.ifsc = ifsc_match.group(1)

        period_match = re.search(
            r"Searched\s*By\s*From\s+(\d{2}\s+[A-Za-z]{3}\s+\d{4})\s+To\s+(\d{2}\s+[A-Za-z]{3}\s+\d{4})",
            text,
            re.IGNORECASE,
        )
        if period_match:
            metadata.statement_from = period_match.group(1).strip()
            metadata.statement_to = period_match.group(2).strip()

        opening_match = re.search(r"Opening\s*Balance\s*Rs\.\s*([-\d,]+\.\d{2})", text, re.IGNORECASE)
        if opening_match:
            metadata.opening_balance = self._parse_amount(opening_match.group(1))

        closing_match = re.search(r"Closing\s*Balance\s*Rs\.\s*([-\d,]+\.\d{2})", text, re.IGNORECASE)
        if closing_match:
            metadata.closing_balance = self._parse_amount(closing_match.group(1))

        try:
            from .._shared.rich_metadata import enrich_statement_metadata
            enrich_statement_metadata(metadata, text, text[:8000], ifsc_prefix="CNRB")
        except Exception:
            pass
        return metadata


    def _parse_amount(self, value: str) -> Optional[float]:
        try:
            return float(value.replace(",", "").strip())
        except Exception:
            return None


# Re-export for compatibility
CanaraStructureError = GenericStructureError
