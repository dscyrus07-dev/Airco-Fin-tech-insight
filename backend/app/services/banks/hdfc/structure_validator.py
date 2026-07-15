"""
Airco Insights — HDFC Structure Validator
==========================================
Validates that PDF structure matches HDFC Bank statement format.
Extracts statement metadata (account number, period, summary counts).

HDFC Statement Structure:
- Header: HDFC BANK LIMITED, Account details
- Statement period: From/To dates
- Account summary: Opening balance, Dr Count, Cr Count, Closing balance
- Transaction table with specific column layout

Design: Fail if structure doesn't match HDFC format.
"""

import logging
import re
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class HDFCStructureError(Exception):
    """Raised when PDF structure doesn't match HDFC format."""
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


@dataclass
class HDFCStatementMetadata:
    """Extracted metadata from HDFC statement."""
    account_number: Optional[str] = None
    account_holder: Optional[str] = None
    statement_from: Optional[str] = None
    statement_to: Optional[str] = None
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    dr_count: Optional[int] = None
    cr_count: Optional[int] = None
    total_debits: Optional[float] = None
    total_credits: Optional[float] = None
    branch: Optional[str] = None
    ifsc: Optional[str] = None
    account_type: Optional[str] = None
    email: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    pan: Optional[str] = None
    account_open_date: Optional[str] = None
    joint_holders: Optional[str] = None

    def to_dict(self) -> dict:
        from .._shared.rich_metadata import metadata_to_rich_dict
        return metadata_to_rich_dict(self)

    
    @property
    def expected_transaction_count(self) -> Optional[int]:
        """Total expected transactions (Dr + Cr)."""
        if self.dr_count is not None and self.cr_count is not None:
            return self.dr_count + self.cr_count
        return None


@dataclass
class HDFCStructureResult:
    """Result of HDFC structure validation."""
    is_valid: bool
    confidence: float
    metadata: HDFCStatementMetadata
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


class HDFCStructureValidator:
    """
    Validates HDFC Bank statement structure and extracts metadata.
    """
    
    # HDFC identification patterns
    HDFC_MARKERS = [
        r"HDFC\s*BANK",
        r"HDFCBANK",
        r"HDFC\s*Bank\s*Limited",
        r"HDFCBANKLIMITED",
    ]
    
    # Account number patterns — HDFC often packs as "AccountNo : 5010..."
    ACCOUNT_PATTERNS = [
        r"Account\s*No\s*[:\.\s]+(\d{10,14})",
        r"AccountNo\s*[:\.\s]+(\d{10,14})",
        r"A/c\s*No\s*[:\.\s]+(\d{10,14})",
        r"Account\s*Number\s*[:\.\s]+(\d{10,14})",
        r"AccountNo\s*[:\.\s]*(\d{10,14})",
    ]

    # Statement period patterns
    PERIOD_PATTERNS = [
        r"Statement\s*From\s*[:\.\s]*(\d{2}/\d{2}/\d{2,4})\s*(?:To|to|TO)\s*[:\.\s]*(\d{2}/\d{2}/\d{2,4})",
        r"StatementFrom\s*[:\.\s]*(\d{2}/\d{2}/\d{2,4})\s*(?:To|to|TO)\s*[:\.\s]*(\d{2}/\d{2}/\d{2,4})",
        r"From\s*[:\.\s]*(\d{2}/\d{2}/\d{2,4})\s*To\s*[:\.\s]*(\d{2}/\d{2}/\d{2,4})",
        r"Period\s*[:\.\s]*(\d{2}/\d{2}/\d{2,4})\s*-\s*(\d{2}/\d{2}/\d{2,4})",
    ]

    # Summary patterns (HDFC-specific)
    OPENING_BAL_PATTERNS = [
        r"Opening\s*Balance\s*[:\.\s]*([\d,]+\.\d{2})",
        r"OpeningBalance\s*[:\.\s]*([\d,]+\.\d{2})",
    ]

    CLOSING_BAL_PATTERNS = [
        r"Closing\s*Bal(?:ance)?\s*[:\.\s]*([\d,]+\.\d{2})",
        r"ClosingBal(?:ance)?\s*[:\.\s]*([\d,]+\.\d{2})",
    ]

    DR_COUNT_PATTERNS = [
        r"Dr\s*Count\s*[:\.\s]*(\d+)",
        r"DrCount\s*[:\.\s]*(\d+)",
        r"Debit\s*Count\s*[:\.\s]*(\d+)",
    ]

    CR_COUNT_PATTERNS = [
        r"Cr\s*Count\s*[:\.\s]*(\d+)",
        r"CrCount\s*[:\.\s]*(\d+)",
        r"Credit\s*Count\s*[:\.\s]*(\d+)",
    ]

    TOTAL_DEBITS_PATTERNS = [
        r"Total\s*Debits?\s*[:\.\s]*([\d,]+\.\d{2})",
        r"Debits\s*[:\.\s]*([\d,]+\.\d{2})",
    ]

    TOTAL_CREDITS_PATTERNS = [
        r"Total\s*Credits?\s*[:\.\s]*([\d,]+\.\d{2})",
        r"Credits\s*[:\.\s]*([\d,]+\.\d{2})",
    ]

    IFSC_PATTERNS = [
        r"RTGS/?NEFT\s*IFSC\s*[:\.\s]*(HDFC\d{7})",
        r"IFSC\s*[:\.\s]*(HDFC\d{7})",
        r"(HDFC\d{7})",
    ]

    EMAIL_PATTERNS = [
        r"Email\s*[:\.\s]*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})",
    ]

    OPEN_DATE_PATTERNS = [
        r"A/?C\s*Open\s*Date\s*[:\.\s]*(\d{2}/\d{2}/\d{2,4})",
        r"A/COpenDate\s*[:\.\s]*(\d{2}/\d{2}/\d{2,4})",
        r"Account\s*Open\s*Date\s*[:\.\s]*(\d{2}/\d{2}/\d{2,4})",
    ]

    ACCOUNT_TYPE_PATTERNS = [
        r"Account\s*Type\s*[:\.\s]*([A-Za-z /\-]+)",
        r"AccountType\s*[:\.\s]*([A-Za-z /\-]+)",
        # Product label often sits after account number: "AccountNo : 5010... PRIME"
        r"AccountNo\s*[:\.\s]*\d{10,14}\s+([A-Z]{3,})",
    ]

    BRANCH_PATTERNS = [
        r"Account\s*Branch\s*[:\.\s]*([A-Za-z0-9 .\-/]+)",
        r"AccountBranch\s*[:\.\s]*([A-Za-z0-9 .\-/]+)",
    ]

    # Customer mobile — ignore bank toll-free (1800...)
    MOBILE_PATTERNS = [
        r"(?:Mobile|Mob(?:ile)?\s*No|Phone)\s*[:\.\s]*([6-9]\d{9})",
        r"(?:Mobile|Mob(?:ile)?\s*No)\s*[:\.\s]*(\+?91[\-\s]?[6-9]\d{9})",
    ]

    PAN_PATTERNS = [
        r"\bPAN\s*[:\.\s]*([A-Z]{5}\d{4}[A-Z])\b",
    ]

    JOINT_HOLDER_PATTERNS = [
        r"JOINT\s*HOLDERS?\s*[:\.\s]*([A-Za-z .,]{2,80}?)(?:\s+RTGS|\s+IFSC|\s+MICR|\s+Branch|\n|$)",
        r"JOINTHOLDERS\s*[:\.\s]*([A-Za-z .,]{2,80}?)(?:\s+RTGS|\s+IFSC|\s+MICR|\s+Branch|\n|$)",
    ]
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def validate(self, text_content: str, first_page_text: str = "") -> HDFCStructureResult:
        """
        Validate that text content is from HDFC Bank statement.
        
        Args:
            text_content: Full extracted text from PDF
            first_page_text: First page text for header validation
            
        Returns:
            HDFCStructureResult with validation status and metadata
            
        Raises:
            HDFCStructureError: If structure doesn't match HDFC format
        """
        self.logger.info("Validating HDFC statement structure")
        
        # Use first page for header checks if available
        header_text = first_page_text if first_page_text else text_content[:5000]
        
        # Step 1: Verify HDFC bank markers
        confidence = self._check_hdfc_markers(header_text)
        
        if confidence < 0.5:
            raise HDFCStructureError(
                "PDF does not appear to be an HDFC Bank statement",
                error_code="NOT_HDFC_STATEMENT",
                details={"confidence": confidence}
            )
        
        # Step 2: Extract metadata
        metadata = self._extract_metadata(text_content, header_text)
        
        # Step 3: Validate minimum required fields
        if not metadata.account_number:
            self.logger.warning("Could not extract account number")
        
        # Check for transaction table markers
        has_table = self._check_transaction_table(text_content)
        if not has_table:
            raise HDFCStructureError(
                "Could not identify transaction table in HDFC statement",
                error_code="NO_TRANSACTION_TABLE",
                details={"has_date_column": False}
            )
        
        self.logger.info(
            "HDFC structure validated: account=%s, period=%s to %s, dr=%s cr=%s",
            metadata.account_number,
            metadata.statement_from,
            metadata.statement_to,
            metadata.dr_count,
            metadata.cr_count,
        )
        
        return HDFCStructureResult(
            is_valid=True,
            confidence=confidence,
            metadata=metadata,
            text_content=text_content,
        )
    
    def _check_hdfc_markers(self, text: str) -> float:
        """Check for HDFC bank markers and return confidence score."""
        text_upper = text.upper()
        
        markers_found = 0
        for pattern in self.HDFC_MARKERS:
            if re.search(pattern, text, re.IGNORECASE):
                markers_found += 1
        
        # Check for IFSC code starting with HDFC
        if re.search(r"HDFC\d{7}", text):
            markers_found += 1
        
        # Calculate confidence based on markers found
        confidence = min(markers_found / 2, 1.0)
        
        return confidence
    
    def _check_transaction_table(self, text: str) -> bool:
        """Check if text contains HDFC transaction table structure."""
        # Look for date patterns that indicate transaction rows
        date_pattern = r'\d{2}/\d{2}/\d{2,4}'
        date_matches = re.findall(date_pattern, text)
        
        # HDFC statements typically have column headers
        header_patterns = [
            r"Date\s*Narration",
            r"DateNarration",
            r"Withdrawal.*Deposit.*Balance",
            r"Chq\./Ref\.No",
        ]
        
        has_headers = any(re.search(p, text, re.IGNORECASE) for p in header_patterns)
        has_dates = len(date_matches) > 2
        
        return has_headers or has_dates
    
    def _extract_metadata(self, full_text: str, header_text: str) -> HDFCStatementMetadata:
        """Extract statement metadata from packed HDFC header text."""
        metadata = HDFCStatementMetadata()
        # Prefer header block; fall back to full text for summary totals.
        text = header_text or full_text
        search_text = full_text or text

        for pattern in self.ACCOUNT_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                metadata.account_number = match.group(1)
                break

        for pattern in self.PERIOD_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                metadata.statement_from = match.group(1)
                metadata.statement_to = match.group(2)
                break

        for pattern in self.OPENING_BAL_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                metadata.opening_balance = self._parse_amount(match.group(1))
                break

        for pattern in self.CLOSING_BAL_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                metadata.closing_balance = self._parse_amount(match.group(1))
                break

        for pattern in self.DR_COUNT_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                try:
                    metadata.dr_count = int(match.group(1))
                except ValueError:
                    pass
                break

        for pattern in self.CR_COUNT_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                try:
                    metadata.cr_count = int(match.group(1))
                except ValueError:
                    pass
                break

        for pattern in self.IFSC_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                metadata.ifsc = match.group(1).upper()
                break

        for pattern in self.TOTAL_DEBITS_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                metadata.total_debits = self._parse_amount(match.group(1))
                break

        for pattern in self.TOTAL_CREDITS_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                metadata.total_credits = self._parse_amount(match.group(1))
                break

        for pattern in self.EMAIL_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                metadata.email = match.group(1).strip()
                break

        for pattern in self.OPEN_DATE_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                metadata.account_open_date = match.group(1)
                break

        for pattern in self.ACCOUNT_TYPE_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                raw = re.sub(r"\s+", " ", match.group(1)).strip(" :.-")
                # Drop trailing labels that bleed into the capture
                raw = re.split(r"\b(?:CustID|AccountNo|IFSC|Branch|Email|Phone)\b", raw, maxsplit=1)[0].strip()
                if raw and raw.upper() not in {"NA", "N/A", "NONE"}:
                    metadata.account_type = raw.upper()
                    break

        for pattern in self.BRANCH_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                branch = re.sub(r"\s+", " ", match.group(1)).strip()
                branch = re.split(r"\b(?:Address|City|State|Email|Phone)\b", branch, maxsplit=1)[0].strip(" :")
                if branch:
                    metadata.branch = branch
                    break

        for pattern in self.MOBILE_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                mobile = re.sub(r"\D", "", match.group(1))
                if mobile.startswith("91") and len(mobile) == 12:
                    mobile = mobile[2:]
                # Skip bank helplines (1800...)
                if len(mobile) == 10 and not mobile.startswith("1800"):
                    metadata.mobile = mobile
                    break

        for pattern in self.PAN_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                metadata.pan = match.group(1).upper()
                break

        for pattern in self.JOINT_HOLDER_PATTERNS:
            match = re.search(pattern, search_text, re.IGNORECASE)
            if match:
                joint = re.sub(r"\s+", " ", match.group(1)).strip(" :,-")
                if joint and joint.upper() not in {"NA", "N/A", "NONE", "NIL"}:
                    metadata.joint_holders = joint
                    break

        metadata.account_holder = self._extract_account_holder(text)
        metadata.address = self._extract_address(text)
        try:
            from .._shared.rich_metadata import enrich_statement_metadata
            enrich_statement_metadata(metadata, search_text, header_text, ifsc_prefix="HDFC")
        except Exception:
            pass
        return metadata

    def _extract_account_holder(self, text: str) -> Optional[str]:
        """Extract customer name from HDFC address block (e.g. MS MANTAPUDIPADMAVATHI)."""
        if not text:
            return None
        # Prefer explicit labels when present
        labeled = re.search(
            r"(?:Account\s*Name|Customer\s*Name|Name)\s*[:\.\s]+([A-Z][A-Za-z .]{2,60})",
            text,
            re.IGNORECASE,
        )
        if labeled:
            name = re.sub(r"\s+", " ", labeled.group(1)).strip(" :")
            name = re.split(r"\b(?:Account|Address|City|State|Email|Phone|Cust)\b", name, maxsplit=1)[0].strip()
            if len(name) >= 3:
                return name.upper()

        # HDFC packed layout: salutation + name on its own line near address block
        for match in re.finditer(
            r"(?m)^\s*((?:MR|MRS|MS|M/S|SMT|SHRI|SHREE)\.?\s+[A-Z][A-Z .]{2,50})\s*$",
            text,
            re.IGNORECASE,
        ):
            name = re.sub(r"\s+", " ", match.group(1)).strip()
            # Skip bank legal entity lines
            if "HDFC" in name.upper() or "BANK" in name.upper():
                continue
            return name.upper()

        # Fallback: "MS NAME" embedded without line breaks
        embedded = re.search(
            r"\b((?:MR|MRS|MS|M/S|SMT|SHRI)\.?\s+[A-Z]{3,}(?:\s+[A-Z]{2,}){0,4})\b",
            text,
            re.IGNORECASE,
        )
        if embedded:
            name = re.sub(r"\s+", " ", embedded.group(1)).strip()
            if "HDFC" not in name.upper() and "BANK" not in name.upper():
                return name.upper()
        return None


    def _extract_address(self, text: str) -> Optional[str]:
        """Build a single-line address from HDFC Address/City/State block."""
        if not text:
            return None
        addr_match = re.search(
            r"Address\s*[:\.\s]+(.+?)(?:City\s*[:\.\s]|State\s*[:\.\s]|Email\s*[:\.\s]|Phoneno|Phone\s*no)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        city_match = re.search(r"City\s*[:\.\s]+([A-Za-z0-9 .\-/]+)", text, re.IGNORECASE)
        state_match = re.search(r"State\s*[:\.\s]+([A-Za-z0-9 .\-/]+)", text, re.IGNORECASE)

        parts = []
        if addr_match:
            raw = addr_match.group(1)
            # Drop customer name lines that sit inside the address block
            cleaned_lines = []
            for line in re.split(r"[\n\r]+", raw):
                line = re.sub(r"\s+", " ", line).strip(" ,")
                if not line:
                    continue
                if re.match(r"^(?:MR|MRS|MS|M/S|SMT|SHRI)\b", line, re.IGNORECASE):
                    continue
                if re.match(r"^W/?O\b", line, re.IGNORECASE):
                    continue
                cleaned_lines.append(line)
            if cleaned_lines:
                parts.append(", ".join(cleaned_lines))

        if city_match:
            city = re.sub(r"\s+", " ", city_match.group(1)).strip()
            city = re.split(r"\b(?:MS|MR|MRS|State|Email|Phone)\b", city, maxsplit=1)[0].strip(" ,")
            if city:
                parts.append(city)
        if state_match:
            state = re.sub(r"\s+", " ", state_match.group(1)).strip()
            state = re.split(r"\b(?:W/?O|Phone|Email|ODLimit|Currency)\b", state, maxsplit=1)[0].strip(" ,")
            if state:
                parts.append(state)

        # PIN often appears near CustID block: "RAJAM532127"
        pin_match = re.search(r"\b([A-Z]{3,})(\d{6})\b", text)
        if pin_match and pin_match.group(2) not in " ".join(parts):
            parts.append(f"{pin_match.group(1)} {pin_match.group(2)}")

        address = ", ".join(p for p in parts if p)
        return address or None
    
    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """Parse Indian format amount string to float."""
        if not amount_str:
            return None
        try:
            cleaned = amount_str.replace(",", "")
            return float(cleaned)
        except (ValueError, TypeError):
            return None
