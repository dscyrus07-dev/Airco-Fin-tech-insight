from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .._shared.generic_bank import GenericStructureError, GenericStructureMetadata, GenericStructureResult


KarnatakaStructureError = GenericStructureError


@dataclass
class KarnatakaStatementMetadata(GenericStructureMetadata):
    @property
    def expected_transaction_count(self) -> Optional[int]:
        return None


class KarnatakaStructureValidator:
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, text_content: str, first_page_text: str = "") -> GenericStructureResult:
        header_text = first_page_text or text_content[:8000]
        confidence = self._check_markers(header_text)
        if confidence < 0.3:
            raise GenericStructureError(
                "PDF does not appear to be a Karnataka Bank statement",
                error_code="NOT_KARNATAKA_STATEMENT",
                details={"confidence": confidence},
            )

        metadata = self._extract_metadata(text_content)
        if not self._has_transaction_table(text_content):
            raise GenericStructureError(
                "Could not identify transaction table in Karnataka Bank statement",
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
            r"Statement\s+for\s+A/c\s+\d+\s+Between\s+\d{2}-\d{2}-\d{4}\s+and\s+\d{2}-\d{2}-\d{4}",
            r"IFSC\s+Code\s+KARB[0-9A-Z]{7}",
            r"Date\s+Particulars\s+Instrument\s+No\s+Withdrawals\s+Deposits\s+Balance",
            r"Opening\s+Balance\s+[-\d,]+\.\d{2}",
        ]
        found = sum(1 for marker in markers if re.search(marker, text, re.IGNORECASE))
        return min(found / 3, 1.0)

    def _has_transaction_table(self, text: str) -> bool:
        return bool(
            re.search(r"Date\s+Particulars\s+Instrument\s+No\s+Withdrawals\s+Deposits\s+Balance", text, re.IGNORECASE)
            or re.search(r"\d{2}-\d{2}-\d{4}\s+.+\s+[\d,]+\.\d{2}\s+[\d,]+\.\d{2}", text)
        )

    def _extract_metadata(self, text: str) -> KarnatakaStatementMetadata:
        metadata = KarnatakaStatementMetadata()

        account_match = re.search(r"Statement\s+for\s+A/c\s+(\d{10,20})", text, re.IGNORECASE)
        if account_match:
            metadata.account_number = account_match.group(1)

        period_match = re.search(
            r"Statement\s+for\s+A/c\s+\d+\s+Between\s+(\d{2}-\d{2}-\d{4})\s+and\s+(\d{2}-\d{2}-\d{4})",
            text,
            re.IGNORECASE,
        )
        if period_match:
            metadata.statement_from = period_match.group(1)
            metadata.statement_to = period_match.group(2)

        customer_match = re.search(r"Name\s+(.+?)\s+Branch\s+Name", text, re.IGNORECASE)
        if customer_match:
            metadata.account_holder = customer_match.group(1).strip()

        ifsc_match = re.search(r"IFSC\s+Code\s+(KARB[0-9A-Z]{7})", text, re.IGNORECASE)
        if ifsc_match:
            metadata.ifsc = ifsc_match.group(1)

        opening_match = re.search(r"Opening\s+Balance\s+([-\d,]+\.\d{2})", text, re.IGNORECASE)
        if opening_match:
            metadata.opening_balance = self._parse_amount(opening_match.group(1))

        try:
            from .._shared.rich_metadata import enrich_statement_metadata
            enrich_statement_metadata(metadata, text, text[:8000], ifsc_prefix="KARB")
        except Exception:
            pass
        return metadata


    def _parse_amount(self, value: str) -> Optional[float]:
        try:
            return float(value.replace(",", "").strip())
        except Exception:
            return None

