"""
Airco Insights - SBI Bank Structure Validator
=============================================
Validates State Bank of India statement formats.

Supports both legacy and newer SBI internet banking layouts:
- Header: SBI / State Bank of India / account statement
- Account number and statement period in either named-month or numeric style
- Transaction tables such as:
  - Txn Date | Value Date | Description | Debit | Credit | Balance
  - Post Date | Value Date | Description | Debit | Credit | Balance
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


class SBIStructureError(Exception):
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


@dataclass
class SBIStatementMetadata:
    account_number: Optional[str] = None
    account_holder: Optional[str] = None
    statement_from: Optional[str] = None
    statement_to: Optional[str] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    crn: Optional[str] = None
    ifsc: Optional[str] = None
    branch: Optional[str] = None
    dr_count: Optional[int] = None
    cr_count: Optional[int] = None
    total_debits: Optional[float] = None
    total_credits: Optional[float] = None
    account_type: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    pan: Optional[str] = None
    account_open_date: Optional[str] = None
    joint_holders: Optional[str] = None
    customer_id: Optional[str] = None
    micr: Optional[str] = None

    def to_dict(self) -> dict:
        from .._shared.rich_metadata import metadata_to_rich_dict
        return metadata_to_rich_dict(self)

    @property
    def expected_transaction_count(self) -> Optional[int]:
        if self.dr_count is not None and self.cr_count is not None:
            return int(self.dr_count) + int(self.cr_count)
        return None



@dataclass
class SBIStructureResult:
    is_valid: bool
    confidence: float
    metadata: SBIStatementMetadata
    text_content: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "metadata": self.metadata.to_dict(),
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


class SBIStructureValidator:
    """Validates State Bank of India statement structure."""

    SBI_MARKERS = [
        r"STATE\s*BANK\s*OF\s*INDIA",
        r"SBI\s*BANK",
        r"SBIN\d{7}",
        r"Account\s*Statement",
        r"Savings\s*Account\s*Transactions",
        r"Account\s*Number",
        r"Balance\s*as\s*on",
    ]

    ACCOUNT_PATTERNS = [
        r"Account\s*No[.\s:]*([Xx\d]{10,18})",
        r"Account\s*Number[:\s]*([Xx\d]{10,18})",
        r"A/C\s*No[.\s:]*([Xx\d]{10,18})",
    ]

    PERIOD_PATTERNS = [
        r"(\d{2}\s+\w+\s+\d{4})\s*[-–]\s*(\d{2}\s+\w+\s+\d{4})",
        r"(\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\s*[-–]\s*"
        r"(\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})",
        r"Statement\s*From\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*To\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
        r"From\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*To\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    ]

    IFSC_PATTERNS = [
        r"IFSC\s*Code\s*(SBIN\d{7})",
        r"(SBIN\d{7})",
    ]

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, text_content: str, first_page_text: str = "") -> SBIStructureResult:
        self.logger.info("Validating SBI statement structure")

        header_text = first_page_text if first_page_text else text_content[:6000]
        confidence = self._check_sbi_markers(header_text)

        if confidence < 0.4:
            raise SBIStructureError(
                "PDF does not appear to be a State Bank of India (SBI) statement",
                error_code="NOT_SBI_STATEMENT",
                details={"confidence": confidence},
            )

        metadata = self._extract_metadata(text_content, header_text)
        has_table = self._check_transaction_table(text_content)

        if not has_table:
            raise SBIStructureError(
                "Could not identify transaction table in SBI statement",
                error_code="NO_TRANSACTION_TABLE",
            )

        self.logger.info(
            "SBI structure validated: account=%s, period=%s to %s",
            metadata.account_number,
            metadata.statement_from,
            metadata.statement_to,
        )

        return SBIStructureResult(
            is_valid=True,
            confidence=confidence,
            metadata=metadata,
            text_content=text_content,
        )

    def _check_sbi_markers(self, text: str) -> float:
        markers_found = sum(
            1 for pattern in self.SBI_MARKERS if re.search(pattern, text, re.IGNORECASE)
        )
        return min(markers_found / 2, 1.0)

    def _check_transaction_table(self, text: str) -> bool:
        date_patterns = [
            r"\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}",
            r"\d{1,2}[/-]\d{1,2}[/-]\d{4}",
        ]
        date_matches = sum(len(re.findall(pattern, text, re.IGNORECASE)) for pattern in date_patterns)
        header_checks = [
            r"Withdrawal\s*\(Dr\.\)",
            r"Deposit\s*\(Cr\.\)",
            r"Savings\s*Account\s*Transactions",
            r"Opening\s*Balance",
            r"DEP\s*TFR",
            r"WDL\s*TFR",
            r"DEBIT\s*ACHDR",
            r"Account\s*Statement",
            r"Txn\s*Date\s+Value\s*Date\s+Description\s+Debit\s+Credit\s+Balance",
            r"Post\s*Date\s+Value\s*Date\s+Description\s+Debit\s+Credit\s+Balance",
            r"Cheque\s*No\.?\s*/?\s*Reference",
        ]
        has_headers = any(re.search(pattern, text, re.IGNORECASE) for pattern in header_checks)
        return has_headers or date_matches > 2

    def _extract_metadata(self, full_text: str, header_text: str) -> SBIStatementMetadata:
        metadata = SBIStatementMetadata()

        for pattern in self.ACCOUNT_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                metadata.account_number = match.group(1)
                break

        for pattern in self.PERIOD_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                metadata.statement_from = match.group(1).strip()
                metadata.statement_to = match.group(2).strip()
                break

        for pattern in self.IFSC_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                metadata.ifsc = match.group(1)
                break

        crn_match = re.search(r"CRN\s+([xX\d]+)", full_text, re.IGNORECASE)
        if crn_match:
            metadata.crn = crn_match.group(1)

        opening_patterns = [
            r"Opening\s*Balance\s*[-–]\s*[-–]\s*[-–]\s*([\d,]+\.\d{2})",
            r"Opening\s*Balance.*?([\d,]+\.\d{2})",
            r"BROUGHT\s+FORWARD\s+([\d,]+\.\d{2})(?:\s+CR|\s+DR)?",
        ]
        metadata.opening_balance = self._first_amount_match(full_text, opening_patterns)

        closing_patterns = [
            r"Closing\s*Balance.*?([\d,]+\.\d{2})",
            r"Available\s*Balance.*?([\d,]+\.\d{2})",
            r"Cleared\s*Balance.*?([\d,]+\.\d{2})",
        ]
        metadata.closing_balance = self._first_amount_match(full_text, closing_patterns)

        try:
            from .._shared.rich_metadata import enrich_statement_metadata
            enrich_statement_metadata(metadata, full_text, header_text, ifsc_prefix="SBIN")
        except Exception:
            pass
        return metadata


    def _first_amount_match(self, text: str, patterns: list[str]) -> Optional[float]:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if not match:
                continue
            parsed = self._parse_amount(match.group(1))
            if parsed is not None:
                return parsed
        return None

    def _parse_amount(self, amount_str: str) -> Optional[float]:
        if not amount_str:
            return None
        try:
            return float(amount_str.replace(",", ""))
        except (ValueError, TypeError):
            return None
