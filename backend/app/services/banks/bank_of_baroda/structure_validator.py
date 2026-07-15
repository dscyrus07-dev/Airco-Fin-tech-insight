"""
Airco Insights - Bank of Baroda Structure Validator
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .._shared.generic_bank import GenericStructureError, GenericStructureMetadata, GenericStructureResult

logger = logging.getLogger(__name__)


@dataclass
class BankOfBarodaStatementMetadata(GenericStructureMetadata):
    dr_count: Optional[int] = None
    cr_count: Optional[int] = None
    total_debits: Optional[float] = None
    total_credits: Optional[float] = None
    ifsc: Optional[str] = None

    @property
    def expected_transaction_count(self) -> Optional[int]:
        if self.dr_count is not None and self.cr_count is not None:
            return self.dr_count + self.cr_count
        return None


class BankOfBarodaStructureValidator:
    PERIOD_PATTERNS = [
        r"Account\s*Statement\s*from\s*(\d{2}-\d{2}-\d{4})\s*to\s*(\d{2}-\d{2}-\d{4})",
    ]

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, text_content: str, first_page_text: str = "") -> GenericStructureResult:
        header_text = first_page_text or text_content[:8000]
        confidence = self._check_markers(header_text)
        if confidence < 0.3:
            raise GenericStructureError(
                "PDF does not appear to be a Bank of Baroda statement",
                error_code="NOT_BANK_OF_BARODA_STATEMENT",
                details={"confidence": confidence},
            )

        metadata = self._extract_metadata(text_content)
        if not self._has_transaction_table(text_content):
            raise GenericStructureError(
                "Could not identify transaction table in Bank of Baroda statement",
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
            r"Account\s*Statement\s*from",
            r"bob World",
            r"BARB0[A-Z0-9]{6}",
            r"Serial\s+Transaction\s+Value\s+Description\s+Cheque\s+Debit\s+Credit\s+Balance",
        ]
        found = sum(1 for marker in markers if re.search(marker, text, re.IGNORECASE))
        return min(found / 3, 1.0)

    def _has_transaction_table(self, text: str) -> bool:
        return bool(
            re.search(r"Serial\s+Transaction\s+Value\s+Description\s+Cheque\s+Debit\s+Credit\s+Balance", text, re.IGNORECASE)
            or re.search(r"\n\d+\s+\d{2}-\d{2}-\d{4}\s+\d{2}-\d{2}-\d{4}\s+", text)
        )

    def _extract_metadata(self, text: str) -> BankOfBarodaStatementMetadata:
        metadata = BankOfBarodaStatementMetadata()

        period_match = re.search(self.PERIOD_PATTERNS[0], text, re.IGNORECASE)
        if period_match:
            metadata.statement_from = period_match.group(1)
            metadata.statement_to = period_match.group(2)

        account_ifsc_match = re.search(
            r"Account\s*Number\s+IFSC\s*Code\s+([0-9]{10,18})\s+([A-Z0-9]{11})",
            text,
            re.IGNORECASE,
        )
        if account_ifsc_match:
            metadata.account_number = account_ifsc_match.group(1)
            raw_ifsc = account_ifsc_match.group(2)
            if re.match(r"^BARB0[A-Z0-9]{6}$", raw_ifsc, re.IGNORECASE):
                metadata.ifsc = raw_ifsc
            else:
                metadata.ifsc = raw_ifsc

        holder_match = re.search(
            r"Account\s*Name\s+Branch\s*Name\s+([A-Z0-9 .&/-]+?)\s{2,}|Account\s*Name\s+Branch\s*Name\s*\n([^\n]+)",
            text,
            re.IGNORECASE,
        )
        if holder_match:
            metadata.account_holder = (holder_match.group(1) or holder_match.group(2) or "").strip()

        opening_match = re.search(
            r"\d+\s+\d{2}-\d{2}-\d{4}\s+Opening\s+Balance\s+-\s+-\s+([\d,]+\.\d{2})",
            text,
            re.IGNORECASE,
        )
        if opening_match:
            metadata.opening_balance = self._parse_amount(opening_match.group(1))

        for pat in (
            r"Total\s+Debit\s*[:\-]?\s*([\d,]+\.\d{2})",
            r"Debit\s+Total\s*[:\-]?\s*([\d,]+\.\d{2})",
        ):
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                metadata.total_debits = self._parse_amount(m.group(1))
                break

        for pat in (
            r"Total\s+Credit\s*[:\-]?\s*([\d,]+\.\d{2})",
            r"Credit\s+Total\s*[:\-]?\s*([\d,]+\.\d{2})",
        ):
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                metadata.total_credits = self._parse_amount(m.group(1))
                break

        dr_m = re.search(r"No\.\s*of\s*Debit\s*Transactions?\s*[:\-]?\s*(\d+)", text, re.IGNORECASE)
        if dr_m:
            metadata.dr_count = int(dr_m.group(1))
        cr_m = re.search(r"No\.\s*of\s*Credit\s*Transactions?\s*[:\-]?\s*(\d+)", text, re.IGNORECASE)
        if cr_m:
            metadata.cr_count = int(cr_m.group(1))

        if metadata.dr_count is None and metadata.cr_count is None:
            total_m = re.search(r"Total\s*Transactions?\s*[:\-]?\s*(\d+)", text, re.IGNORECASE)
            if total_m:
                total = int(total_m.group(1))
                metadata.dr_count = total // 2
                metadata.cr_count = total - metadata.dr_count

        try:
            from .._shared.rich_metadata import enrich_statement_metadata
            enrich_statement_metadata(metadata, text, text[:8000], ifsc_prefix="BARB")
        except Exception:
            pass
        return metadata


    def _parse_amount(self, value: str) -> Optional[float]:
        try:
            return float(value.replace(",", "").strip())
        except Exception:
            return None


# Re-export for compatibility
BankOfBarodaStructureError = GenericStructureError
