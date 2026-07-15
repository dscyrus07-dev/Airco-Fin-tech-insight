"""
Airco Insights — Axis Bank Structure Validator
===============================================
Validates that PDF structure matches Axis Bank statement format.
Extracts statement metadata (account number, period, summary).

Axis Statement Structure:
- Header: Account holder name, address
- Statement of Axis Account No: XXXXXXXXXX
- Transaction table: Tran Date | Chq No | Particulars | Debit | Credit | Balance
- Date format: DD-MM-YYYY
- IFSC starts with UTIB (Axis Bank)
"""

import logging
import re
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class AxisStructureError(Exception):
    """Raised when PDF structure doesn't match Axis Bank format."""
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


@dataclass
class AxisStatementMetadata:
    """Extracted metadata from Axis Bank statement."""
    account_number: Optional[str] = None
    account_holder: Optional[str] = None
    statement_from: Optional[str] = None
    statement_to: Optional[str] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    customer_id: Optional[str] = None
    ifsc: Optional[str] = None
    micr: Optional[str] = None
    dr_count: Optional[int] = None
    cr_count: Optional[int] = None
    total_debits: Optional[float] = None
    total_credits: Optional[float] = None
    branch: Optional[str] = None
    account_type: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    pan: Optional[str] = None
    account_open_date: Optional[str] = None
    joint_holders: Optional[str] = None
    crn: Optional[str] = None

    def to_dict(self) -> dict:
        from .._shared.rich_metadata import metadata_to_rich_dict
        return metadata_to_rich_dict(self)

    @property
    def expected_transaction_count(self) -> Optional[int]:
        if self.dr_count is not None and self.cr_count is not None:
            return int(self.dr_count) + int(self.cr_count)
        return None



@dataclass
class AxisStructureResult:
    """Result of Axis structure validation."""
    is_valid: bool
    confidence: float
    metadata: AxisStatementMetadata
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


class AxisStructureValidator:
    """Validates Axis Bank statement structure and extracts metadata."""

    # Axis Bank identification markers
    AXIS_MARKERS = [
        r"Axis\s*Bank",
        r"AXIS\s*BANK",
        r"Statement\s*of\s*Axis\s*Account",
        r"UTIB\d{7}",      # Axis IFSC prefix
        r"Customer\s*ID",   # Axis-specific header label
    ]

    # Account number
    ACCOUNT_PATTERNS = [
        r"Axis\s*Account\s*No\s*[:\s]*(\d{10,18})",
        r"Account\s*No\s*[:\s]*(\d{10,18})",
        r"A/c\s*No[:\s]*(\d{10,18})",
    ]

    # Statement period — Axis format: "From : DD-MM-YYYY To : DD-MM-YYYY"
    PERIOD_PATTERNS = [
        r"[Ff]rom\s*[:\s]*(\d{2}-\d{2}-\d{4})\s*[Tt]o\s*[:\s]*(\d{2}-\d{2}-\d{4})",
        r"[Ff]rom\s*:\s*(\d{2}-\d{2}-\d{4}).*?[Tt]o\s*:\s*(\d{2}-\d{2}-\d{4})",
        r"(\d{2}-\d{2}-\d{4})\s*[Tt]o\s*(\d{2}-\d{2}-\d{4})",
    ]

    # Customer ID
    CUSTOMER_ID_PATTERNS = [
        r"Customer\s*ID\s*[:\s]*(\d{6,12})",
        r"CustID[:\s]*(\d{6,12})",
    ]

    # IFSC — Axis Bank IFSC starts with UTIB
    IFSC_PATTERNS = [
        r"IFSC\s*Code\s*[:\s]*(UTIB\d{7})",
        r"(UTIB\d{7})",
    ]

    # Opening / Closing Balance
    OPENING_BAL_PATTERNS = [
        r"OPENING\s*BALANCE\s*([\d,]+\.\d{2})",
        r"Opening\s*Bal(?:ance)?\s*[:\s]*([\d,]+\.\d{2})",
    ]

    CLOSING_BAL_PATTERNS = [
        r"CLOSING\s*BALANCE\s*([\d,]+\.\d{2})",
        r"Closing\s*Bal(?:ance)?\s*[:\s]*([\d,]+\.\d{2})",
    ]

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def validate(self, text_content: str, first_page_text: str = "") -> AxisStructureResult:
        """Validate Axis Bank statement structure and extract metadata."""
        self.logger.info("Validating Axis Bank statement structure")

        header_text = first_page_text if first_page_text else text_content[:6000]

        confidence = self._check_axis_markers(header_text)

        if confidence < 0.4:
            raise AxisStructureError(
                "PDF does not appear to be an Axis Bank statement",
                error_code="NOT_AXIS_STATEMENT",
                details={"confidence": confidence}
            )

        metadata = self._extract_metadata(text_content, header_text)

        has_table = self._check_transaction_table(text_content)
        if not has_table:
            raise AxisStructureError(
                "Could not identify transaction table in Axis Bank statement",
                error_code="NO_TRANSACTION_TABLE",
                details={}
            )

        self.logger.info(
            "Axis structure validated: account=%s, period=%s to %s",
            metadata.account_number,
            metadata.statement_from,
            metadata.statement_to,
        )

        return AxisStructureResult(
            is_valid=True,
            confidence=confidence,
            metadata=metadata,
            text_content=text_content,
        )

    def _check_axis_markers(self, text: str) -> float:
        """Check for Axis Bank markers and return confidence score."""
        markers_found = 0
        for pattern in self.AXIS_MARKERS:
            if re.search(pattern, text, re.IGNORECASE):
                markers_found += 1

        confidence = min(markers_found / 2, 1.0)
        return confidence

    def _check_transaction_table(self, text: str) -> bool:
        """Check if text contains Axis transaction table structure."""
        date_pattern = r'\d{2}-\d{2}-\d{4}'
        date_matches = re.findall(date_pattern, text)

        header_patterns = [
            r"Tran\s*Date",
            r"Particulars",
            r"Chq\s*No",
            r"OPENING\s*BALANCE",
        ]
        has_headers = any(re.search(p, text, re.IGNORECASE) for p in header_patterns)
        has_dates = len(date_matches) > 2

        return has_headers or has_dates

    def _extract_metadata(self, full_text: str, header_text: str) -> AxisStatementMetadata:
        """Extract statement metadata from text."""
        metadata = AxisStatementMetadata()

        for pattern in self.ACCOUNT_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                metadata.account_number = match.group(1)
                break

        for pattern in self.PERIOD_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
            if match:
                metadata.statement_from = match.group(1)
                metadata.statement_to = match.group(2)
                break

        for pattern in self.CUSTOMER_ID_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                metadata.customer_id = match.group(1)
                break

        for pattern in self.IFSC_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                metadata.ifsc = match.group(1)
                break

        for pattern in self.OPENING_BAL_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                metadata.opening_balance = self._parse_amount(match.group(1))
                break

        for pattern in self.CLOSING_BAL_PATTERNS:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                metadata.closing_balance = self._parse_amount(match.group(1))
                break

        try:
            from .._shared.rich_metadata import enrich_statement_metadata
            enrich_statement_metadata(metadata, full_text, header_text, ifsc_prefix="UTIB")
        except Exception:
            pass
        return metadata


    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse Indian format amount string to float."""
        if not amount_str:
            return None
        try:
            return float(amount_str.replace(",", ""))
        except (ValueError, TypeError):
            return None
