"""
Robust SBI Bank Statement Parser
================================
Enhanced parser that handles multiple SBI PDF formats.
"""

import logging
import re
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

import pdfplumber

# Import shared components for 3-level fallback
from .._shared.base_parser import BaseBankParser
from .._shared.dynamic_column_detector import DynamicColumnDetector
from .._shared.unsupported_format_queue import UnsupportedFormatQueue
from .._shared.parser_metrics import ParserMetrics

logger = logging.getLogger(__name__)


@dataclass
class SBITransaction:
    """Represents a single SBI transaction."""
    date: str  # DD-MM-YYYY format
    description: str
    ref_no: str
    debit: Optional[float]
    credit: Optional[float]
    balance: float

    def to_dict(self):
        return {
            "date": self.date,
            "description": self.description,
            "ref_no": self.ref_no,
            "debit": self.debit,
            "credit": self.credit,
            "balance": self.balance,
        }


@dataclass
class SBIParseResult:
    """Result of parsing an SBI statement."""
    transactions: List[SBITransaction]
    total_count: int
    parse_method: str
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_credits: float = 0.0
    total_debits: float = 0.0


class SBIParseError(Exception):
    """Custom exception for SBI parsing errors."""
    def __init__(self, message: str, error_code: str = "UNKNOWN", details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class SBIParser(BaseBankParser):
    """
    Robust SBI Bank statement parser with multiple format support.
    """

    BANK_NAME = "SBI"


    # Column boundaries (based on actual PDF analysis)
    _REFERENCE_WIDTH = 595.0
    _COL_TXN_DATE_MAX = 90       # Txn Date column
    _COL_VALUE_DATE_MAX = 143    # Value Date column
    _COL_DESC_MAX = 222          # Description column
    _COL_REF_MAX = 302           # Ref No./Cheque No. column
    _COL_BRANCH_MAX = 384         # Branch Code column
    _COL_DEBIT_MAX = 443          # Debit column
    _COL_CREDIT_MAX = 511         # Credit column
    # Balance is everything after CREDIT

    # Y-axis filtering (adjusted based on analysis)
    _DATA_Y_MIN_PAGE1 = 300      # First page starts after headers
    _DATA_Y_MIN_OTHERS = 70      # Other pages start higher
    _DATA_Y_MAX = 800            # Maximum Y coordinate for data

    # Date bucketing tolerance
    _Y_BUCKET = 6
    _NUMERIC_DATE_RE = re.compile(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$')
    _AMOUNT_RE = re.compile(r'(?<!\d)\d[\d,]*\.\d{2}(?!\d)')

    def __init__(self, audit_service=None, job_id=None):
        super().__init__(audit_service=audit_service, job_id=job_id)
        self.bank_name = self.BANK_NAME
        self._hygiene_result = None
        self._collected_parser_metrics = []
        # Initialize 3-level fallback components
        self.dynamic_detector = DynamicColumnDetector()
        self.unsupported_queue = UnsupportedFormatQueue()
        self.metrics = ParserMetrics()

    def parse(self, file_path: str, text_content: str = "") -> SBIParseResult:
        """
        MAIN PARSE METHOD - Now with 3-level fallback strategy.
        
        Flow:
        1. Try existing hardcoded parser (text/coordinate)
        2. If fails, try dynamic column detection
        3. If fails, add to unsupported queue
        """
        start_time = datetime.now()

        try:
            from pathlib import Path as _Path
            from .._shared.hygiene_check import HygieneCheck as _HC
            _hc = _HC(pdf_directory=_Path(file_path).parent)
            _hr = _hc.validate_single_pdf(_Path(file_path), bank_hint=getattr(self, "BANK_NAME", None) or getattr(self, "bank_name", None))
            self._hygiene_result = _hr
            _hc.log_hygiene_check_result(_hr)
        except Exception as _he:
            self.logger.warning(f"Hygiene check failed (non-fatal): {_he}")

        try:
            # Level 1: Try existing SBI parser logic
            self.logger.info("Level 1: Trying existing SBI hardcoded parser")
            result = self._parse_existing_hardcoded(file_path, text_content)
            
            if self._is_valid_result(result):
                # Success with hardcoded
                self._record_metrics("hardcoded", True, result.total_count, start_time)
                self._write_parser_metric("hardcoded", True, result.total_count, start_time)
                self.logger.info(f"Level 1 success: {result.total_count} transactions via hardcoded ({result.parse_method})")
                return result
            
            # Level 2: Dynamic fallback
            self.logger.warning("Level 1 failed for SBI, trying dynamic fallback")
            self._write_parser_metric("hardcoded", False, 0, start_time)
            result = self._parse_dynamic(file_path)
            
            if self._is_valid_result(result):
                # Success with dynamic
                self._record_metrics("dynamic", True, result.total_count, start_time)
                self._write_parser_metric("dynamic", True, result.total_count, start_time)
                self.logger.warning(f"Level 2 success: {result.total_count} transactions via dynamic")
                return result
            
            # Level 3: Unsupported format
            self.logger.error("Level 2 failed for SBI, adding to unsupported queue")
            self._add_to_unsupported_queue(file_path, "BOTH_PARSERS_FAILED")
            self._record_metrics("unsupported", False, 0, start_time)
            self._write_parser_metric("unsupported", False, 0, start_time)
            
            return self._create_empty_result("Unsupported SBI statement format")
            
        except Exception as e:
            self.logger.error(f"Parser error for SBI: {e}", exc_info=True)
            self._add_to_unsupported_queue(file_path, f"PARSER_ERROR: {str(e)}")
            self._record_metrics("error", False, 0, start_time)
            self._write_parser_metric("error", False, 0, start_time)
            return self._create_empty_result(f"Parser error: {str(e)}")

    def _parse_existing_hardcoded(self, file_path: str, text_content: str = "") -> SBIParseResult:
        """
        Call the original SBI parser logic.
        This is the existing parse method without fallback.
        """
        self.logger.info("Parsing SBI Bank statement: %s", file_path)

        # Check for scanned PDFs
        if self._is_image_only_pdf(file_path):
            raise SBIParseError(
                "This PDF appears to be a scanned image and cannot be processed. "
                "Please upload a text-based PDF downloaded directly from SBI's internet banking portal.",
                error_code="SCANNED_PDF",
                details={"file": file_path}
            )

        # Try text-based parsing first for SBI (works better for internet banking PDFs)
        try:
            result = self._parse_with_text_extraction(file_path)
            if result.total_count > 0:
                self.logger.info("Text parsing succeeded: %d transactions", result.total_count)
                return result
        except Exception as e:
            self.logger.warning("Text parsing failed: %s", str(e))

        # Fallback to coordinate-based parsing
        try:
            result = self._parse_with_coordinates(file_path)
            if result.total_count > 0:
                self.logger.info("Coordinate parsing succeeded: %d transactions", result.total_count)
                return result
        except SBIParseError:
            raise
        except Exception as e:
            self.logger.warning("Coordinate parsing failed: %s", str(e))

        # Try text-based parsing as fallback
        try:
            result = self._parse_with_text_extraction(file_path)
            if result.total_count > 0:
                self.logger.info("Text parsing succeeded: %d transactions", result.total_count)
                return result
        except Exception as e:
            self.logger.warning("Text parsing failed: %s", str(e))

        # If we get here, no transactions found
        raise SBIParseError(
            "Could not extract transactions from this PDF. Please ensure it is a valid SBI statement.",
            error_code="NO_TRANSACTIONS",
            details={"file": file_path}
        )

    def _parse_dynamic(self, file_path: str) -> SBIParseResult:
        """
        Dynamic column detection fallback.
        Uses shared DynamicColumnDetector.
        """
        try:
            dynamic_result = self.dynamic_detector.parse(file_path, bank_hint=self.bank_name)
            
            if dynamic_result and dynamic_result.transactions:
                # Convert dynamic result to SBI format
                return self._convert_dynamic_result(dynamic_result)
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Dynamic parser failed for SBI: {e}")
            return None

    def _convert_dynamic_result(self, dynamic_result) -> SBIParseResult:
        """
        Convert DynamicParseResult to SBIParseResult format.
        """
        # Convert dynamic transactions to SBITransaction format
        sbi_transactions = []
        for txn in dynamic_result.transactions:
            sbi_txn = SBITransaction(
                date=txn.get("date", ""),
                description=txn.get("description", ""),
                ref_no=txn.get("ref_no", ""),
                debit=self._parse_amount(txn.get("debit")),
                credit=self._parse_amount(txn.get("credit")),
                balance=self._parse_amount(txn.get("balance"))
            )
            sbi_transactions.append(sbi_txn)
        
        # Calculate totals
        total_credits = sum(t.credit or 0 for t in sbi_transactions)
        total_debits = sum(t.debit or 0 for t in sbi_transactions)
        opening_balance = sbi_transactions[0].balance if sbi_transactions else None
        closing_balance = sbi_transactions[-1].balance if sbi_transactions else None
        
        return SBIParseResult(
            transactions=sbi_transactions,
            total_count=len(sbi_transactions),
            parse_method="dynamic",
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits
        )

    def _is_valid_result(self, result: SBIParseResult) -> bool:
        """
        Validation for SBI parsing results.
        """
        if not result:
            return False
        
        # Basic validation
        if result.total_count <= 0:
            return False
        
        if not result.transactions:
            return False
        
        # SBI-specific validation - minimum threshold
        if result.total_count < 3:
            return False
        
        # Validate first transaction has required fields
        first_txn = result.transactions[0] if result.transactions else None
        if not first_txn:
            return False
        
        # Check for essential fields
        if not first_txn.date:
            return False
        
        if not first_txn.description:
            return False
        
        # Check for amount field (debit or credit)
        if not (first_txn.debit or first_txn.credit):
            return False
        
        return True

    def _add_to_unsupported_queue(self, file_path: str, reason: str):
        """Add failed PDF to unsupported format queue."""
        try:
            entry = {
                "bank": self.bank_name,
                "file": file_path,
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
                "attempts": []  # Could be enhanced to track attempts
            }
            
            self.unsupported_queue.add(entry)
            self.logger.warning(f"Added to unsupported queue: SBI - {reason}")
            
        except Exception as e:
            self.logger.error(f"Failed to add to unsupported queue: {e}")

    def _write_parser_metric(self, method: str, success: bool, transaction_count: int, start_time: datetime = None):
        """Collect parser metric in memory for finalize_job_audit."""
        try:
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000) if start_time else 0
            self._collected_parser_metrics.append({
                'parser_type': method,
                'parser_name': f'SBI_{method}',
                'bank_name': self.bank_name,
                'execution_time_ms': elapsed_ms,
                'transactions_extracted': transaction_count,
                'confidence_score': 95.0 if success else 0.0,
                'status': 'SUCCESS' if success else 'FAILED',
            })
        except Exception as e:
            self.logger.warning(f"Failed to collect parser metric (non-fatal): {e}")

    def _record_metrics(self, method: str, success: bool, transaction_count: int, start_time: datetime = None):
        """Record parsing metrics."""
        try:
            processing_time = (datetime.now() - start_time).total_seconds() * 1000 if start_time is not None else 0
            
            self.metrics.record_attempt(
                bank=self.bank_name,
                method=method,
                success=success,
                transaction_count=transaction_count,
                processing_time_ms=int(processing_time)
            )
            
        except Exception as e:
            self.logger.error(f"Failed to record metrics: {e}")

    def _create_empty_result(self, error_message: str) -> SBIParseResult:
        """
        Create empty result with error message.
        """
        return SBIParseResult(
            transactions=[],
            total_count=0,
            parse_method="failed",
            opening_balance=None,
            closing_balance=None,
            total_credits=0.0,
            total_debits=0.0
        )

    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """
        Parse amount string to float for dynamic results.
        Reuse existing SBI amount parsing logic.
        """
        if not amount_str:
            return None
        # Use existing amount parsing logic from SBI parser
        return float(amount_str.replace(",", "")) if amount_str.replace(",", "").replace(".", "").isdigit() else None

    def _is_image_only_pdf(self, file_path: str) -> bool:
        """Check if PDF is scanned/image-only."""
        try:
            with pdfplumber.open(file_path) as pdf:
                for page_num in range(min(3, len(pdf.pages))):
                    words = pdf.pages[page_num].extract_words()
                    if words and len(words) > 10:
                        return False
                return True
        except Exception as e:
            self.logger.warning("Error checking PDF type: %s", str(e))
            return False

    def _get_scaled_boundaries(self, page_width: float) -> dict:
        """Scale column boundaries based on actual page width."""
        scale = page_width / self._REFERENCE_WIDTH
        return {
            "txn_date_max": self._COL_TXN_DATE_MAX * scale,
            "value_date_max": self._COL_VALUE_DATE_MAX * scale,
            "desc_max": self._COL_DESC_MAX * scale,
            "ref_max": self._COL_REF_MAX * scale,
            "branch_max": self._COL_BRANCH_MAX * scale,
            "debit_max": self._COL_DEBIT_MAX * scale,
            "credit_max": self._COL_CREDIT_MAX * scale,
        }

    def _parse_with_coordinates(self, file_path: str) -> SBIParseResult:
        """Parse using coordinate-based extraction."""
        transactions = []
        opening_balance = None

        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_width = page.width
                bounds = self._get_scaled_boundaries(page_width)
                
                # Different Y-min for first page vs others
                y_min = self._DATA_Y_MIN_PAGE1 if page_num == 0 else self._DATA_Y_MIN_OTHERS
                
                # Extract page lines
                page_txns = self._extract_page_lines(page, bounds, y_min, self._DATA_Y_MAX)
                transactions.extend(page_txns)
                
                # Get opening balance from first transaction on first page
                if page_num == 0 and not opening_balance and page_txns:
                    first_txn = page_txns[0]
                    opening_balance = first_txn.balance
                    if first_txn.credit:
                        opening_balance -= first_txn.credit
                    if first_txn.debit:
                        opening_balance += first_txn.debit

        total_credits = sum(t.credit or 0 for t in transactions)
        total_debits = sum(t.debit or 0 for t in transactions)
        closing = transactions[-1].balance if transactions else None
        transactions = self._normalize_transaction_order(transactions)
        if transactions:
            closing = transactions[-1].balance

        return SBIParseResult(
            transactions=transactions,
            total_count=len(transactions),
            parse_method="coordinate",
            opening_balance=opening_balance,
            closing_balance=closing,
            total_credits=total_credits,
            total_debits=total_debits,
        )

    def _parse_with_text_extraction(self, file_path: str) -> SBIParseResult:
        """Parse using text extraction as fallback."""
        transactions = []
        prev_balance: Optional[float] = None

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines = [line.strip() for line in text.split('\n') if line and line.strip()]
                default_year = self._infer_statement_year(text, lines)

                pending_marker = ""
                pending_lines: List[str] = []
                i = 0
                while i < len(lines):
                    line = lines[i]
                    if self._is_transaction_marker(line):
                        pending_marker = line.strip()
                        pending_lines = []
                        i += 1
                        continue

                    if self._is_transaction_line(line):
                        continuation_lines = []
                        trailing_markers = []
                        j = i + 1
                        while j < len(lines):
                            next_line = lines[j]
                            if self._is_transaction_line(next_line) or self._is_header_or_footer(next_line):
                                break
                            if self._is_pre_transaction_fragment(next_line):
                                break
                            if self._is_transaction_marker(next_line):
                                if self._marker_starts_next_transaction(lines, j):
                                    break
                                trailing_markers.append(next_line.strip())
                                j += 1
                                continue
                            continuation_lines.append(next_line)
                            j += 1
                        txn = self._parse_transaction_line(
                            line,
                            pending_marker,
                            prev_balance,
                            pending_lines=pending_lines,
                            continuation_lines=continuation_lines,
                            trailing_markers=trailing_markers,
                            default_year=default_year,
                        )
                        pending_marker = ""
                        pending_lines = []
                        if txn:
                            transactions.append(txn)
                            prev_balance = txn.balance
                        i = j
                        continue
                    if self._is_header_or_footer(line):
                        pending_lines = []
                    i += 1
                    if not self._is_header_or_footer(line):
                        pending_lines.append(line)

        if not transactions:
            raise SBIParseError(
                "Could not extract transactions from this SBI PDF. Please upload a text-based SBI statement downloaded from internet banking.",
                error_code="NO_TRANSACTIONS",
            )

        total_credits = sum(t.credit or 0 for t in transactions)
        total_debits = sum(t.debit or 0 for t in transactions)
        transactions = self._normalize_transaction_order(transactions)
        closing = transactions[-1].balance if transactions else None

        return SBIParseResult(
            transactions=transactions,
            total_count=len(transactions),
            parse_method="text",
            opening_balance=None,
            closing_balance=closing,
            total_credits=total_credits,
            total_debits=total_debits,
        )

    def _extract_page_lines(self, page, bounds: dict, y_min: float, y_max: float) -> List[SBITransaction]:
        """Extract transactions from a single page using coordinate-based grouping."""
        words = page.extract_words()
        
        # Filter words by Y coordinate
        data_words = [w for w in words if y_min <= w["top"] <= y_max]
        
        if not data_words:
            return []

        # Group words by Y coordinate (bucketing)
        lines = {}
        for word in data_words:
            y_bucket = round(word["top"] / self._Y_BUCKET) * self._Y_BUCKET
            if y_bucket not in lines:
                lines[y_bucket] = {
                    "txn_date": [],
                    "value_date": [],
                    "description": [],
                    "ref_no": [],
                    "branch": [],
                    "debit": [],
                    "credit": [],
                    "balance": [],
                }
            
            x0 = word["x0"]
            text = word["text"]
            
            # Assign to columns based on X coordinate
            if x0 < bounds["txn_date_max"]:
                lines[y_bucket]["txn_date"].append(text)
            elif x0 < bounds["value_date_max"]:
                lines[y_bucket]["value_date"].append(text)
            elif x0 < bounds["desc_max"]:
                lines[y_bucket]["description"].append(text)
            elif x0 < bounds["ref_max"]:
                lines[y_bucket]["ref_no"].append(text)
            elif x0 < bounds["branch_max"]:
                lines[y_bucket]["branch"].append(text)
            elif x0 < bounds["debit_max"]:
                lines[y_bucket]["debit"].append(text)
            elif x0 < bounds["credit_max"]:
                lines[y_bucket]["credit"].append(text)
            else:
                lines[y_bucket]["balance"].append(text)

        # Parse lines into transactions
        transactions = []
        sorted_y = sorted(lines.keys())
        pending_marker = ""
        prev_balance = None
        
        i = 0
        while i < len(sorted_y):
            y = sorted_y[i]
            row = lines[y]
            row_description = " ".join(row["description"]).strip()
            row_reference = " ".join(row["ref_no"]).strip()
            row_branch = " ".join(row["branch"]).strip()

            if self._is_transaction_marker(" ".join(filter(None, [row_description, row_reference, row_branch]))):
                pending_marker = " ".join(filter(None, [row_description, row_reference, row_branch])).strip()
                i += 1
                continue
            
            # Check if this looks like a transaction line (has balance)
            balance_text = " ".join(row["balance"])
            if not balance_text or not self._looks_like_amount(balance_text):
                i += 1
                continue
            
            # Extract date (SBI format: DD Mon YY)
            txn_date_parts = row["txn_date"]
            value_date_parts = row["value_date"]
            
            # Combine date parts
            txn_date_str = " ".join(txn_date_parts)
            
            # Skip if no valid date
            if not self._is_date_like(txn_date_str):
                i += 1
                continue
            
            # Parse date to DD-MM-YYYY
            date = self._normalize_sbi_date(txn_date_str)
            
            # Description (may span multiple lines)
            description_parts = []
            if pending_marker:
                description_parts.append(pending_marker)
                pending_marker = ""
            if row_description:
                description_parts.append(row_description)
            j = i + 1
            while j < len(sorted_y):
                next_y = sorted_y[j]
                next_row = lines[next_y]
                next_description = " ".join(next_row["description"]).strip()
                next_reference = " ".join(next_row["ref_no"]).strip()
                next_branch = " ".join(next_row["branch"]).strip()
                # Continue while we have description but no balance
                if next_description and not next_row["balance"]:
                    if self._is_transaction_marker(" ".join(filter(None, [next_description, next_reference, next_branch]))):
                        description_parts.append(next_description)
                    else:
                        description_parts.append(next_description)
                    j += 1
                else:
                    break
            
            description = " ".join(part for part in description_parts if part).strip()
            
            # Ref no
            ref_no = " ".join(row["ref_no"])
            
            # Parse amounts
            debit = self._parse_amount(" ".join(row["debit"]))
            credit = self._parse_amount(" ".join(row["credit"]))
            balance = self._parse_amount(balance_text)

            if balance is not None and prev_balance is not None and debit is None and credit is None:
                delta = round(balance - prev_balance, 2)
                if delta > 0:
                    credit = delta
                elif delta < 0:
                    debit = abs(delta)
            
            if balance is not None:
                transactions.append(SBITransaction(
                    date=date,
                    description=description,
                    ref_no=ref_no,
                    debit=debit,
                    credit=credit,
                    balance=balance,
                ))
                prev_balance = balance
            
            i = j if j > i + 1 else i + 1

        return transactions

    def _is_transaction_line(self, line: str) -> bool:
        """Check if a line looks like a transaction."""
        # SBI statements commonly use DD/MM/YYYY or DD-MM-YYYY transaction rows.
        has_date = bool(
            re.match(r'^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', line.strip())
            or re.match(r'^\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4}', line.strip())
        )
        has_amount = bool(re.search(r'\d[\d,]*\.\d{2}', line))
        return has_date and has_amount

    def _is_transaction_marker(self, line: str) -> bool:
        """Detect the short line that labels the transaction direction/type."""
        upper = line.upper().strip()
        if not upper or self._is_transaction_line(line):
            return False
        marker_tokens = (
            "DEP TFR", "WDL TFR", "DEBIT ACHDR", "DEBIT ACH DR",
            "ACHDR", "ACH DR", "ACH-DR", "CREDIT", "DEBIT", "TRANSFER",
            "CSH DEP", "CASH DEPOSIT", "CASH DEPOSIT SELF", "CASH WITHDRAWAL",
            "BY CASH", "BROUGHT FORWARD",
        )
        return any(token in upper for token in marker_tokens)

    def _is_header_or_footer(self, line: str) -> bool:
        upper = line.upper().strip()
        if not upper:
            return True
        if "STATEMENT SUMMARY" in upper or "BROUGHT FORWARD" in upper or upper.startswith("CLOSING BALANCE"):
            return True
        header_tokens = (
            "STATE BANK OF INDIA",
            "STATEMENT OF ACCOUNT",
            "ACCOUNT STATEMENT",
            "TXN DATE VALUE DATE DESCRIPTION",
            "TXN DATE VALUE DESCRIPTION",
            "DATE DETAILS DEBIT CREDIT BALANCE",
            "DATE NO.",
            "REF/CHEQUE",
            "REF NO./CHEQUE",
            "PAGE NO.",
            "ACCOUNT NAME",
            "ACCOUNT NUMBER",
            "CUSTOMER NAME",
            "AVAILABLE BALANCE",
            "BALANCE AS ON",
            "SEARCH FOR ",
            "ACCOUNT STATEMENT FROM ",
            "PLEASE DO NOT SHARE YOUR ATM",
            "MEDIA. BANK NEVER ASKS FOR SUCH INFORMATION.",
            "ATM: AUTOMATED TELLER MACHINE",
            "OTP: ONE TIME PASSWORD",
            "PIN: PERSONAL IDENTIFICATION NUMBER",
            "IN CASE YOUR ACCOUNT IS OPERATED BY A LETTER OF AUTHORITY",
            "LAST TRANSACTION DATE AND TIME APPEARING IN THIS STATEMENT",
        )
        return any(token in upper for token in header_tokens)

    def _normalize_transaction_order(self, transactions: List[SBITransaction]) -> List[SBITransaction]:
        if len(transactions) < 2:
            return transactions

        reversed_transactions = list(reversed(transactions))
        current_score = self._orientation_score(transactions)
        reversed_score = self._orientation_score(reversed_transactions)
        if reversed_score < current_score:
            return reversed_transactions
        return transactions

    def _parse_transaction_line(
        self,
        line: str,
        marker: str = "",
        prev_balance: Optional[float] = None,
        pending_lines: Optional[List[str]] = None,
        continuation_lines: Optional[List[str]] = None,
        trailing_markers: Optional[List[str]] = None,
        default_year: Optional[int] = None,
    ) -> Optional[SBITransaction]:
        """Parse a transaction line from text."""
        try:
            stripped = line.strip()

            # Extract the transaction date, value date, and the remainder of the row.
            date_parts = self._split_leading_dates(stripped)
            if not date_parts:
                return None

            date_str, _value_date, body = date_parts
            date = self._normalize_sbi_date(date_str, default_year=default_year)

            amount_matches = list(self._AMOUNT_RE.finditer(body))
            if not amount_matches:
                return None

            balance_match = amount_matches[-1]
            balance = float(balance_match.group(0).replace(',', ''))

            amount = None
            amount_match = None
            inferred_direction: Optional[bool] = None
            if len(amount_matches) >= 2:
                amount_match = amount_matches[-2]
                amount = float(amount_match.group(0).replace(',', ''))
            else:
                pending_amount, pending_direction = self._extract_amount_direction_from_fragments(pending_lines or [])
                if pending_amount is None:
                    pending_amount, pending_direction = self._extract_amount_direction_from_fragments(continuation_lines or [])
                if pending_amount is not None:
                    amount = pending_amount
                    inferred_direction = pending_direction

            description_end = amount_match.start() if amount_match else balance_match.start()
            description_prefix = body[:description_end].strip()
            description_suffix = body[balance_match.end():].strip()
            description_suffix = re.sub(r'^(?:CR|DR)\b', '', description_suffix, flags=re.IGNORECASE).strip(" -|")
            continuation_parts = [
                self._sanitize_description_fragment(part)
                for part in (continuation_lines or [])
            ]
            continuation_parts = [part for part in continuation_parts if part]
            description = " ".join(
                part
                for part in [
                    marker.strip(),
                    *[self._sanitize_description_fragment(part) for part in list(pending_lines or [])],
                    description_prefix,
                    *continuation_parts,
                    *[self._sanitize_description_fragment(part) for part in (trailing_markers or [])],
                    description_suffix,
                ]
                if part
            ).strip()
            description = re.sub(r'\s+', ' ', description).strip(' -|')
            description = re.sub(r'\b20\d{2}\b\s+\b20\d{2}\b', '', description).strip()
            description = re.sub(r'^\b20\d{2}\b(?:\s+\b20\d{2}\b)?\s*', '', description).strip()
            description = re.sub(
                r'^(?:TXN DATE VALUE DESCRIPTION REF NO\./CHEQUE DEBIT CREDIT BALANCE\s*(?:DATE NO\.)?\s*)+',
                '',
                description,
                flags=re.IGNORECASE,
            ).strip()

            marker_upper = (marker or "").upper()
            desc_upper = description.upper()
            is_credit: Optional[bool] = None

            if "CHARG" in desc_upper or "CHARGE" in desc_upper or "CHAR--" in desc_upper:
                is_credit = False

            credit_markers = (
                "DEP", "CR", "CREDIT", "SAL", "REFUND", "REVERSAL", "BY CASH",
                "BY TRANSFER", "CASH DEPOSIT", "CSH DEP",
            )
            debit_markers = (
                "WDL", "DR", "DEBIT", "WITHDRAW", "ATM", "ACH", "CHQ", "RETURN", "BOUNCE", "CHARGE",
                "TO TRANSFER",
            )

            if any(token in marker_upper for token in credit_markers) or "/CR/" in desc_upper or desc_upper.startswith(("BY TRANSFER", "CASH DEPOSIT", "CSH DEP")):
                is_credit = True
            elif any(token in marker_upper for token in debit_markers) or "/DR/" in desc_upper or desc_upper.startswith(("TO TRANSFER", "DEBIT-", "DEBIT ")):
                is_credit = False
            elif prev_balance is not None:
                is_credit = balance >= prev_balance

            if amount is None and prev_balance is not None:
                amount = round(abs(balance - prev_balance), 2)

            if amount is None:
                return None

            if is_credit is None and inferred_direction is not None:
                is_credit = inferred_direction
            if is_credit is None:
                is_credit = True if prev_balance is None else balance >= prev_balance

            debit = None
            credit = None
            if is_credit:
                credit = amount
            else:
                debit = amount
            
            return SBITransaction(
                date=date,
                description=description,
                ref_no="",
                debit=debit,
                credit=credit,
                balance=balance,
            )
        except Exception as e:
            self.logger.warning("Error parsing transaction line: %s", str(e))
            return None

    def _sanitize_description_fragment(self, text: str) -> str:
        fragment = (text or "").strip()
        if not fragment or self._is_header_or_footer(fragment):
            return ""
        fragment = re.sub(
            r'^(?:TXN DATE VALUE DESCRIPTION REF NO\./CHEQUE DEBIT CREDIT BALANCE\s*(?:DATE NO\.)?\s*)+',
            '',
            fragment,
            flags=re.IGNORECASE,
        ).strip()
        fragment = re.sub(r'^DATE\s+NO\.\s*', '', fragment, flags=re.IGNORECASE).strip()
        fragment = re.sub(r'^\b20\d{2}\b(?:\s+\b20\d{2}\b)?\s*', '', fragment).strip()
        fragment = re.sub(r'^\(CID:\d+\)\s*', '', fragment, flags=re.IGNORECASE)
        return fragment.strip(" -|")

    def _is_pre_transaction_fragment(self, line: str) -> bool:
        upper = (line or "").upper().strip()
        if not upper or self._is_header_or_footer(upper) or self._is_transaction_line(upper):
            return False
        return bool(self._AMOUNT_RE.search(upper) and re.search(r'\b(?:CR|DR)\b', upper))

    def _marker_starts_next_transaction(self, lines: List[str], marker_index: int) -> bool:
        lookahead = marker_index + 1
        while lookahead < len(lines):
            candidate = lines[lookahead]
            if self._is_header_or_footer(candidate):
                return False
            if self._is_transaction_line(candidate):
                return False
            if self._is_transaction_marker(candidate):
                return True
            return True
        return False

    def _extract_amount_direction_from_fragments(self, fragments: List[str]) -> Tuple[Optional[float], Optional[bool]]:
        for fragment in reversed(fragments):
            text = (fragment or "").strip()
            if not text:
                continue
            amount_matches = list(self._AMOUNT_RE.finditer(text))
            if not amount_matches:
                continue
            amount = float(amount_matches[-1].group(0).replace(",", ""))
            upper = text.upper()
            if re.search(r'\bDR\b', upper) and not re.search(r'\bCR\b', upper):
                return amount, False
            if re.search(r'\bCR\b', upper) and not re.search(r'\bDR\b', upper):
                return amount, True
            if "UPI/DR/" in upper:
                return amount, False
            if "UPI/CR/" in upper:
                return amount, True
        return None, None

    def _orientation_score(self, transactions: List[SBITransaction]) -> Tuple[int, float]:
        mismatches = 0
        total_difference = 0.0
        for idx in range(1, len(transactions)):
            previous = transactions[idx - 1]
            current = transactions[idx]
            expected_balance = previous.balance + (current.credit or 0) - (current.debit or 0)
            difference = abs(round(expected_balance - current.balance, 2))
            if difference > 0.01:
                mismatches += 1
                total_difference += difference
        return mismatches, round(total_difference, 2)

    def _split_leading_dates(self, text: str) -> Optional[Tuple[str, Optional[str], str]]:
        patterns = [
            (
                r'^(?P<date1>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+'
                r'(?P<date2>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(?P<body>.*)$'
            ),
            (
                r'^(?P<date1>\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})\s+'
                r'(?P<date2>\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})\s+(?P<body>.*)$'
            ),
            (
                r'^(?P<date1>\d{1,2}\s+[A-Za-z]{3})\s+'
                r'(?P<date2>\d{1,2}\s+[A-Za-z]{3})\s+(?P<body>.*)$'
            ),
            (
                r'^(?P<date1>\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+(?P<body>.*)$'
            ),
            (
                r'^(?P<date1>\d{1,2}\s+[A-Za-z]{3}\s+\d{2,4})\s+(?P<body>.*)$'
            ),
            (
                r'^(?P<date1>\d{1,2}\s+[A-Za-z]{3})\s+(?P<body>.*)$'
            ),
        ]
        for pattern in patterns:
            match = re.match(pattern, text, re.IGNORECASE)
            if match:
                return match.group("date1"), match.groupdict().get("date2"), match.group("body").strip()
        return None

    def _looks_like_amount(self, text: str) -> bool:
        """Check if text looks like an amount."""
        # Remove commas and check if it's a number
        cleaned = text.replace(",", "").replace("-", "").strip()
        if not cleaned:
            return False
        try:
            float(cleaned)
            return True
        except ValueError:
            return False

    def _is_date_like(self, text: str) -> bool:
        """Check if text looks like a date."""
        # SBI PDFs may contain either month-name dates or DD/MM/YYYY dates.
        month_name_pattern = r'\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(?:\s+\d{2,4})?'
        numeric_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
        return bool(re.search(month_name_pattern, text, re.IGNORECASE) or re.search(numeric_pattern, text))

    def _normalize_sbi_date(self, date_str: str, default_year: Optional[int] = None) -> str:
        """Convert SBI date formats to DD-MM-YYYY."""
        try:
            # Handle "22 Jan 22" / "22 Jan 2022"
            match = re.match(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{2,4})', date_str.strip(), re.IGNORECASE)
            if match:
                day, month, year = match.groups()
                # Convert 2-digit year to 4-digit
                if len(year) == 2:
                    year = f"20{year}" if int(year) >= 0 else f"19{year}"
                # Convert month name to number
                month_map = {
                    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                }
                month_num = month_map.get(month.capitalize(), '01')
                return f"{day.zfill(2)}-{month_num}-{year}"

            short_match = re.match(r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$', date_str.strip(), re.IGNORECASE)
            if short_match:
                day, month = short_match.groups()
                month_map = {
                    'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                    'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                    'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                }
                inferred_year = str(default_year or datetime.now().year)
                month_num = month_map.get(month.capitalize(), '01')
                return f"{day.zfill(2)}-{month_num}-{inferred_year}"

            numeric = re.match(r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', date_str.strip())
            if numeric:
                day, month, year = numeric.groups()
                if len(year) == 2:
                    year = f"20{year}"
                return f"{day.zfill(2)}-{month.zfill(2)}-{year}"
            
            # Fallback for other formats
            for fmt in ["%d %b %Y", "%d %b %y", "%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y"]:
                try:
                    dt = datetime.strptime(date_str.strip(), fmt)
                    return dt.strftime("%d-%m-%Y")
                except:
                    continue
            
            self.logger.warning("Could not parse date: %s", date_str)
            return date_str
        except Exception as e:
            self.logger.warning("Date parsing error for '%s': %s", date_str, str(e))
            return date_str

    def _infer_statement_year(self, text: str, lines: List[str]) -> Optional[int]:
        patterns = [
            r'Account Statement from \d{1,2}\s+[A-Za-z]{3}\s+(\d{4}) to \d{1,2}\s+[A-Za-z]{3}\s+\d{4}',
            r'Search for \d{1,2}\s+[A-Za-z]{3}\s+(\d{4}) to \d{1,2}\s+[A-Za-z]{3}\s+\d{4}',
            r'Balance as on \d{1,2}\s+[A-Za-z]{3}\s+(\d{4})',
            r'Date\s*:?\s*(\d{1,2}\s+[A-Za-z]{3}\s+(\d{4}))',
        ]
        combined = "\n".join(lines[:40]) if lines else text
        for pattern in patterns:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                year_text = match.group(match.lastindex or 1)
                year_match = re.search(r'(\d{4})', year_text)
                if year_match:
                    return int(year_match.group(1))

        all_years = re.findall(r'\b(20\d{2})\b', combined)
        if all_years:
            return int(all_years[0])
        return None

    def _parse_amount(self, text: str) -> Optional[float]:
        """Parse amount from text, handling Indian number format."""
        if not text or not text.strip():
            return None
        
        try:
            # Remove commas, handle negative values
            cleaned = re.sub(r"\b(?:CR|DR)\b", "", text, flags=re.IGNORECASE)
            cleaned = cleaned.replace(",", "").replace("-", "").strip()
            if cleaned == "" or cleaned == "0" or not any(c.isdigit() for c in cleaned):
                return None
            return float(cleaned)
        except ValueError:
            return None
