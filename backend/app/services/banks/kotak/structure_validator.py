"""
Airco Insights — Kotak Bank Structure Validator
================================================
Validates PDF matches Kotak Mahindra Bank statement format.

Kotak Statement Structure:
- Header: Account Statement, date range
- Account holder name, account number, CRN
- Transaction table: # | Date | Description | Chq/Ref. No. | Withdrawal | Deposit | Balance
- Date format: DD Mon YYYY  (01 Oct 2025)
- IFSC prefix: KKBK
"""

import logging
import re
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class KotakStructureError(Exception):
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details    = details or {}
        super().__init__(message)


@dataclass
class KotakStatementMetadata:
    account_number:  Optional[str] = None
    account_holder:  Optional[str] = None
    statement_from:  Optional[str] = None
    statement_to:    Optional[str] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    crn:             Optional[str] = None
    ifsc:            Optional[str] = None
    branch:          Optional[str] = None
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
class KotakStructureResult:
    is_valid:     bool
    confidence:   float
    metadata:     KotakStatementMetadata
    text_content: str
    error_code:   Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "is_valid":     self.is_valid,
            "confidence":   self.confidence,
            "metadata":     self.metadata.to_dict(),
            "error_code":   self.error_code,
            "error_message": self.error_message,
        }


class KotakStructureValidator:
    """Validates Kotak Mahindra Bank statement structure."""

    KOTAK_MARKERS = [
        r"Kotak\s*Mahindra\s*Bank",
        r"KOTAK\s*BANK",
        r"KKBK\d{7}",          # KKBK IFSC prefix
        r"Account\s*Statement",
        r"Savings\s*Account\s*Transactions",
        r"CRN\s+[x\d]+",
    ]

    ACCOUNT_PATTERNS = [
        r"Account\s*No[.\s]*(\d{10,14})",
        r"Account\s*Number[:\s]*(\d{10,14})",
    ]

    PERIOD_PATTERNS = [
        r"(\d{2}\s+\w+\s+\d{4})\s*[-–]\s*(\d{2}\s+\w+\s+\d{4})",
        r"(\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})\s*[-–]\s*"
        r"(\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})",
    ]

    IFSC_PATTERNS = [
        r"IFSC\s*Code\s*(KKBK\d{7})",
        r"(KKBK\d{7})",
    ]

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, text_content: str, first_page_text: str = "") -> KotakStructureResult:
        self.logger.info("Validating Kotak Bank statement structure")

        header_text = first_page_text if first_page_text else text_content[:6000]
        confidence  = self._check_kotak_markers(header_text)

        if confidence < 0.4:
            raise KotakStructureError(
                "PDF does not appear to be a Kotak Mahindra Bank statement",
                error_code="NOT_KOTAK_STATEMENT",
                details={"confidence": confidence}
            )

        metadata  = self._extract_metadata(text_content, header_text)
        has_table = self._check_transaction_table(text_content)

        if not has_table:
            raise KotakStructureError(
                "Could not identify transaction table in Kotak statement",
                error_code="NO_TRANSACTION_TABLE",
            )

        self.logger.info(
            "Kotak structure validated: account=%s, period=%s to %s",
            metadata.account_number, metadata.statement_from, metadata.statement_to,
        )

        return KotakStructureResult(
            is_valid=True,
            confidence=confidence,
            metadata=metadata,
            text_content=text_content,
        )

    def _check_kotak_markers(self, text: str) -> float:
        markers_found = sum(
            1 for p in self.KOTAK_MARKERS
            if re.search(p, text, re.IGNORECASE)
        )
        return min(markers_found / 2, 1.0)

    def _check_transaction_table(self, text: str) -> bool:
        # Kotak uses DD Mon YYYY dates
        date_pattern  = r'\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}'
        date_matches  = re.findall(date_pattern, text, re.IGNORECASE)
        header_checks = [
            r"Withdrawal\s*\(Dr\.\)",
            r"Deposit\s*\(Cr\.\)",
            r"Savings\s*Account\s*Transactions",
            r"Opening\s*Balance",
        ]
        has_headers = any(re.search(p, text, re.IGNORECASE) for p in header_checks)
        return has_headers or len(date_matches) > 2

    def _extract_metadata(self, full_text: str, header_text: str) -> KotakStatementMetadata:
        metadata = KotakStatementMetadata()

        for pattern in self.ACCOUNT_PATTERNS:
            m = re.search(pattern, full_text, re.IGNORECASE)
            if m:
                metadata.account_number = m.group(1)
                break

        for pattern in self.PERIOD_PATTERNS:
            m = re.search(pattern, full_text, re.IGNORECASE)
            if m:
                metadata.statement_from = m.group(1).strip()
                metadata.statement_to   = m.group(2).strip()
                break

        for pattern in self.IFSC_PATTERNS:
            m = re.search(pattern, full_text, re.IGNORECASE)
            if m:
                metadata.ifsc = m.group(1)
                break

        # CRN
        crn_match = re.search(r'CRN\s+([x\d]+)', full_text, re.IGNORECASE)
        if crn_match:
            metadata.crn = crn_match.group(1)

        # Opening balance
        ob_match = re.search(r'Opening\s*Balance\s*[-–]\s*[-–]\s*[-–]\s*([\d,]+\.\d{2})', full_text)
        if not ob_match:
            ob_match = re.search(r'Opening\s*Balance.*?([\d,]+\.\d{2})', full_text, re.IGNORECASE)
        if ob_match:
            try:
                metadata.opening_balance = float(ob_match.group(1).replace(",", ""))
            except ValueError:
                pass

        try:
            from .._shared.rich_metadata import enrich_statement_metadata
            enrich_statement_metadata(metadata, full_text, header_text, ifsc_prefix="KKBK")
        except Exception:
            pass
        return metadata


    def _parse_amount(self, amount_str: str) -> Optional[float]:
        if not amount_str:
            return None
        try:
            return float(amount_str.replace(",", ""))
        except (ValueError, TypeError):
            return None
