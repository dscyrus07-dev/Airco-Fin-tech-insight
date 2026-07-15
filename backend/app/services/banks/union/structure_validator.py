from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from .._shared.generic_bank import GenericStructureError, GenericStructureMetadata, GenericStructureResult


UnionStructureError = GenericStructureError


@dataclass
class UnionStatementMetadata(GenericStructureMetadata):
    @property
    def expected_transaction_count(self) -> Optional[int]:
        return None


class UnionStructureValidator:
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, text_content: str, first_page_text: str = "") -> GenericStructureResult:
        header_text = first_page_text or text_content[:8000]
        confidence = self._check_markers(header_text)
        if confidence < 0.3:
            raise GenericStructureError(
                "PDF does not appear to be a Union Bank statement",
                error_code="NOT_UNION_STATEMENT",
                details={"confidence": confidence},
            )

        metadata = self._extract_metadata(text_content)
        if not self._has_transaction_table(text_content):
            raise GenericStructureError(
                "Could not identify transaction table in Union Bank statement",
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
            r"Statement\s+of\s+Account",
            r"Union\s+Bank\s+of\s+India",
            r"IFSC\s+(?:Code\s+)?UBIN[0-9A-Z]{7}",
            r"S\.No\s+Date\s+Transaction\s+Id\s+Remarks\s+Amount\(Rs\.\)\s+Balance\(Rs\.\)",
            r"Date\s+Remarks\s+Tran\s+Id-1\s+UTR\s+Number\s+Instr\.\s+ID\s+Withdrawals\s+Deposits\s+Balance",
        ]
        found = sum(1 for marker in markers if re.search(marker, text, re.IGNORECASE))
        return min(found / 3, 1.0)

    def _has_transaction_table(self, text: str) -> bool:
        return bool(
            re.search(r"S\.No\s+Date\s+Transaction\s+Id\s+Remarks\s+Amount\(Rs\.\)\s+Balance\(Rs\.\)", text, re.IGNORECASE)
            or re.search(r"Date\s+Remarks\s+Tran\s+Id-1\s+UTR\s+Number\s+Instr\.\s+ID\s+Withdrawals\s+Deposits\s+Balance", text, re.IGNORECASE)
            or re.search(r"\d{2}[/-]\d{2}[/-]\d{4}\s+.+\s+[\d,]+\.\d{2}\s+\(?[DC]r\)?", text, re.IGNORECASE)
        )

    def _extract_metadata(self, text: str) -> UnionStatementMetadata:
        metadata = UnionStatementMetadata()

        account_match = re.search(r"Account\s+(?:No|Number)\s+(\d{10,20})", text, re.IGNORECASE)
        if account_match:
            metadata.account_number = account_match.group(1)

        name_match = re.search(r"Name\s+(.+?)\s+Customer/CIF\s+ID", text, re.IGNORECASE)
        if name_match:
            metadata.account_holder = name_match.group(1).strip()
        elif re.search(r"Statement of Account", text, re.IGNORECASE):
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            if len(lines) > 1:
                metadata.account_holder = lines[1]

        ifsc_match = re.search(r"IFSC(?:\s+Code)?\s+(UBIN[0-9A-Z]{7})", text, re.IGNORECASE)
        if ifsc_match:
            metadata.ifsc = ifsc_match.group(1)

        period_match = re.search(
            r"Statement\s+Period(?:\s+From)?\s*[:\-]?\s*(\d{2}[/-]\d{2}[/-]\d{4})\s+To\s+(\d{2}[/-]\d{2})\s*/?\s*(\d{4})?",
            text,
            re.IGNORECASE,
        )
        if period_match:
            metadata.statement_from = period_match.group(1)
            metadata.statement_to = f"{period_match.group(2)}/{period_match.group(3)}" if period_match.group(3) else period_match.group(2)

        try:
            from .._shared.rich_metadata import enrich_statement_metadata
            enrich_statement_metadata(metadata, text, text[:8000], ifsc_prefix="UBIN")
        except Exception:
            pass
        return metadata


