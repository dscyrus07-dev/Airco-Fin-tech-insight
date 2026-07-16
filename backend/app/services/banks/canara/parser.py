"""
Airco Insights - Canara Bank Parser
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Tuple

import pdfplumber

from .._shared.generic_bank import GenericParseError

# Import shared components for 3-level fallback
from .._shared.base_parser import BaseBankParser
from .._shared.dynamic_column_detector import DynamicColumnDetector
from .._shared.unsupported_format_queue import UnsupportedFormatQueue
from .._shared.parser_metrics import ParserMetrics

logger = logging.getLogger(__name__)


@dataclass
class CanaraTransaction:
    date: str
    description: str
    ref_no: str
    debit: Optional[float]
    credit: Optional[float]
    balance: float

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "description": self.description,
            "ref_no": self.ref_no,
            "debit": self.debit,
            "credit": self.credit,
            "balance": self.balance,
        }



@dataclass
class CanaraParseResult:
    transactions: List[CanaraTransaction]
    total_count: int
    parse_method: str
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_credits: float = 0.0
    total_debits: float = 0.0


class CanaraParseError(Exception):
    """Raised when Canara Bank parsing fails."""
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class CanaraParser(BaseBankParser):
    BANK_NAME = "Canara"

    ROW_RE = re.compile(
        r"^(?P<txn_date>\d{2}-\d{2}-\d{4})\s+"
        r"(?P<txn_time>\d{2}:\d{2}:\d{2})\s+"
        r"(?P<value_date>\d{2}\s+[A-Za-z]{3}\s+\d{4})\s+"
        r"(?P<rest>.*)$"
    )
    def __init__(self, audit_service=None, job_id=None):
        super().__init__(audit_service=audit_service, job_id=job_id)
        self.bank_name = self.BANK_NAME
        self._hygiene_result = None
        self._collected_parser_metrics = []
        # Initialize 3-level fallback components
        self.dynamic_detector = DynamicColumnDetector()
        self.unsupported_queue = UnsupportedFormatQueue()
        self.metrics = ParserMetrics()

    def parse(self, file_path: str, text_content: str = "") -> CanaraParseResult:
        """
        MAIN PARSE METHOD - Now with 3-level fallback strategy.
        
        Flow:
        1. Try existing hardcoded parser (text-based)
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
            # Level 1: Try existing Canara parser logic
            self.logger.info("Level 1: Trying existing Canara hardcoded parser")
            result = self._parse_existing_hardcoded(file_path, text_content)
            
            if self._is_valid_result(result):
                # Success with hardcoded
                self._record_metrics("hardcoded", True, result.total_count, start_time)
                self._write_parser_metric("hardcoded", True, result.total_count, start_time)
                self.logger.info(f"Level 1 success: {result.total_count} transactions via hardcoded ({result.parse_method})")
                return result
            
            # Level 2: Dynamic fallback
            self.logger.warning("Level 1 failed for Canara, trying dynamic fallback")
            self._write_parser_metric("hardcoded", False, 0, start_time)
            result = self._parse_dynamic(file_path)
            
            if self._is_valid_result(result):
                # Success with dynamic
                self._record_metrics("dynamic", True, result.total_count, start_time)
                self._write_parser_metric("dynamic", True, result.total_count, start_time)
                self.logger.warning(f"Level 2 success: {result.total_count} transactions via dynamic")
                return result
            
            # Level 3: Unsupported format
            self.logger.error("Level 2 failed for Canara, adding to unsupported queue")
            self._add_to_unsupported_queue(file_path, "BOTH_PARSERS_FAILED")
            self._record_metrics("unsupported", False, 0, start_time)
            self._write_parser_metric("unsupported", False, 0, start_time)
            
            return self._create_empty_result("Unsupported Canara statement format")
            
        except Exception as e:
            self.logger.error(f"Parser error for Canara: {e}", exc_info=True)
            self._add_to_unsupported_queue(file_path, f"PARSER_ERROR: {str(e)}")
            self._record_metrics("error", False, 0, start_time)
            self._write_parser_metric("error", False, 0, start_time)
            return self._create_empty_result(f"Parser error: {str(e)}")

    def _parse_existing_hardcoded(self, file_path: str, text_content: str = "") -> CanaraParseResult:
        """
        Call the original Canara parser logic.
        This is the existing parse method without fallback.
        """
        if self._is_image_only_pdf(file_path):
            raise CanaraParseError(
                "This PDF appears to be a scanned image and cannot be processed. "
                "Please upload a text-based PDF downloaded directly from Canara Bank's internet banking portal.",
                error_code="SCANNED_PDF",
                details={"file": file_path}
            )

        transactions: List[CanaraTransaction] = []
        opening_balance: Optional[float] = None
        closing_balance: Optional[float] = None
        prev_balance: Optional[float] = None

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                lines = [line.strip() for line in (page.extract_text() or "").splitlines() if line and line.strip()]
                page_transactions, page_opening, prev_balance = self._parse_lines(lines, prev_balance)
                if opening_balance is None and page_opening is not None:
                    opening_balance = page_opening
                if page_transactions:
                    closing_balance = page_transactions[-1].balance
                transactions.extend(page_transactions)

        if not transactions:
            raise GenericParseError(
                "Could not extract transactions from this Canara PDF.",
                error_code="NO_TRANSACTIONS",
                details={"file": file_path},
            )

        total_credits = sum(txn.credit or 0 for txn in transactions)
        total_debits = sum(txn.debit or 0 for txn in transactions)
        return CanaraParseResult(
            transactions=transactions,
            total_count=len(transactions),
            parse_method="text",
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits,
        )

    def _parse_dynamic(self, file_path: str) -> CanaraParseResult:
        """
        Dynamic column detection fallback.
        Uses shared DynamicColumnDetector.
        """
        try:
            dynamic_result = self.dynamic_detector.parse(file_path, bank_hint=self.bank_name)
            
            if dynamic_result and dynamic_result.transactions:
                # Convert dynamic result to Canara format
                return self._convert_dynamic_result(dynamic_result)
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Dynamic parser failed for Canara: {e}")
            return None

    def _convert_dynamic_result(self, dynamic_result) -> CanaraParseResult:
        """
        Convert DynamicParseResult to CanaraParseResult format.
        """
        # Convert dynamic transactions to CanaraTransaction format
        canara_transactions = []
        for txn in dynamic_result.transactions:
            canara_txn = CanaraTransaction(
                date=txn.get("date", ""),
                description=txn.get("description", ""),
                ref_no=txn.get("ref_no", ""),
                debit=self._parse_amount(txn.get("debit")),
                credit=self._parse_amount(txn.get("credit")),
                balance=self._parse_amount(txn.get("balance"))
            )
            canara_transactions.append(canara_txn)
        
        # Calculate totals
        total_credits = sum(t.credit or 0 for t in canara_transactions)
        total_debits = sum(t.debit or 0 for t in canara_transactions)
        opening_balance = canara_transactions[0].balance if canara_transactions else None
        closing_balance = canara_transactions[-1].balance if canara_transactions else None
        
        return CanaraParseResult(
            transactions=canara_transactions,
            total_count=len(canara_transactions),
            parse_method="dynamic",
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits
        )

    def _is_valid_result(self, result: CanaraParseResult) -> bool:
        """
        Validation for Canara parsing results.
        """
        if not result:
            return False
        
        # Basic validation
        if result.total_count <= 0:
            return False
        
        if not result.transactions:
            return False
        
        # Canara-specific validation - minimum threshold
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
            self.logger.warning(f"Added to unsupported queue: Canara - {reason}")
            
        except Exception as e:
            self.logger.error(f"Failed to add to unsupported queue: {e}")

    def _write_parser_metric(self, method: str, success: bool, transaction_count: int, start_time: datetime = None):
        """Collect parser metric in memory for finalize_job_audit."""
        try:
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000) if start_time else 0
            self._collected_parser_metrics.append({
                'parser_type': method,
                'parser_name': f'CANARA_{method}',
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

    def _create_empty_result(self, error_message: str) -> CanaraParseResult:
        """
        Create empty result with error message.
        """
        return CanaraParseResult(
            transactions=[],
            total_count=0,
            parse_method="failed",
            opening_balance=None,
            closing_balance=None,
            total_credits=0.0,
            total_debits=0.0
        )

    def _parse_lines(
        self,
        lines: List[str],
        prev_balance: Optional[float],
    ) -> Tuple[List[CanaraTransaction], Optional[float], Optional[float]]:
        transactions: List[CanaraTransaction] = []
        pending_lines: List[str] = []
        opening_balance: Optional[float] = None

        i = 0
        while i < len(lines):
            line = lines[i]

            opening_match = re.search(r"Opening\s*Balance\s*Rs\.\s*([-\d,]+\.\d{2})", line, re.IGNORECASE)
            if opening_match and opening_balance is None:
                opening_balance = self._parse_amount(opening_match.group(1))
                if prev_balance is None:
                    # Use the statement opening balance as the first transaction's
                    # prior balance so the initial row can be directionally inferred
                    # from the balance delta instead of falling back to debit.
                    prev_balance = opening_balance
                i += 1
                continue

            if self._is_skip_line(line):
                pending_lines = []
                i += 1
                continue

            row_match = self.ROW_RE.match(line)
            if row_match:
                suffix_lines: List[str] = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if self.ROW_RE.match(next_line) or self._is_skip_line(next_line):
                        break
                    suffix_lines.append(next_line)
                    j += 1

                txn, prev_balance = self._build_transaction(row_match, pending_lines, suffix_lines, prev_balance)
                pending_lines = []
                if txn:
                    transactions.append(txn)
                i = j
                continue

            pending_lines.append(line)
            i += 1

        return transactions, opening_balance, prev_balance

    def _build_transaction(
        self,
        row_match: re.Match[str],
        pending_lines: List[str],
        suffix_lines: List[str],
        prev_balance: Optional[float],
    ) -> Tuple[Optional[CanaraTransaction], Optional[float]]:
        full_rest = " ".join(part.strip() for part in [row_match.group("rest"), *suffix_lines] if part).strip()
        full_rest = re.sub(r"\s+", " ", full_rest)
        full_rest = self._strip_footer_noise(full_rest)
        parsed_tail = self._extract_amount_and_balance(full_rest)
        if not parsed_tail:
            return None, prev_balance

        lead, amount, balance = parsed_tail
        if amount is None or balance is None:
            return None, prev_balance

        amount_abs = abs(amount)
        combined_description = " ".join(part for part in [*pending_lines, lead] if part).strip()
        combined_description = re.sub(r"\s+", " ", combined_description)

        debit, credit = self._infer_direction(combined_description, amount, balance, prev_balance)
        ref_no = self._extract_reference(combined_description)

        txn = CanaraTransaction(
            date=datetime.strptime(row_match.group("txn_date"), "%d-%m-%Y").strftime("%Y-%m-%d"),
            description=combined_description,
            ref_no=ref_no,
            debit=debit,
            credit=credit,
            balance=balance,
        )
        return txn, balance

    def _extract_amount_and_balance(self, text: str) -> Optional[Tuple[str, Optional[float], Optional[float]]]:
        matches = list(re.finditer(r"-?[\d,]+\.\d{2}", text))
        if len(matches) < 2:
            return None
        amount_match = matches[-2]
        balance_match = matches[-1]
        lead = text[:amount_match.start()].strip()
        amount = self._parse_amount(amount_match.group(0))
        balance = self._parse_amount(balance_match.group(0))
        lead = re.sub(r"\b[0-9A-Z]{2,14}\b\s*$", "", lead).strip()
        return lead, amount, balance

    def _infer_direction(
        self,
        description: str,
        amount: float,
        balance: float,
        prev_balance: Optional[float],
    ) -> Tuple[Optional[float], Optional[float]]:
        desc_upper = description.upper()
        amount_abs = abs(amount)

        credit_markers = (" CR", "CREDIT", "GROSS INT CR", "NEFT CR", "IMPS-CR", "UPI/CR/", "FD REDEEM", "GST REV")
        debit_markers = (" DR", "DEBIT", "ECS ", "ATM CASH", "SMS CHARGES", "CHARGES", "DRAWDOWN", "IB OAT", "INSTL PAY")

        if prev_balance is not None:
            delta = round(balance - prev_balance, 2)
            if abs(delta - amount_abs) <= 1.0:
                return None, amount_abs
            if abs(delta + amount_abs) <= 1.0:
                return amount_abs, None

        if amount < 0:
            return amount_abs, None
        if any(marker in desc_upper for marker in credit_markers):
            return None, amount_abs
        if any(marker in desc_upper for marker in debit_markers):
            return amount_abs, None

        return amount_abs, None

    def _extract_reference(self, description: str) -> str:
        patterns = [
            r"\b(\d{12})\b",
            r"\b(IMPS/[A-Z0-9/.-]+)",
            r"\b(UPI/[A-Z0-9/.*@_-]+)",
            r"\b(NEFT\s+Cr-[A-Z0-9-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return match.group(1)[:120]
        return ""

    def _strip_footer_noise(self, text: str) -> str:
        cut_tokens = [
            "Disclaimer:",
            "UNLESS THE CONSTITUENT BRINGS",
            "END OF STATEMENT",
            "Page ",
        ]
        result = text
        for token in cut_tokens:
            pos = result.find(token)
            if pos >= 0:
                result = result[:pos].strip()
        return result

    def _is_skip_line(self, line: str) -> bool:
        upper = line.upper().strip()
        skip_tokens = (
            "CURRENT & SAVING ACCOUNT STATEMENT",
            "ACCOUNT STATEMENT AS OF",
            "ACCOUNT HOLDERS",
            "ACCOUNT HOLDERS NAME",
            "CUSTOMER ID",
            "BRANCH NAME",
            "MICR CODE",
            "IFSC CODE",
            "SEARCHED BY FROM",
            "ACCOUNT NUMBER",
            "ACCOUNT CURRENCY",
            "PRODUCT NAME",
            "OPENING BALANCE RS.",
            "CLOSING BALANCE RS.",
            "TXN DATE VALUE DATE CHEQUE NO. DESCRIPTION BRANCH DEBIT CREDIT BALANCE",
            "CODE",
            "PAGE ",
            "DISCLAIMER:",
            "END OF STATEMENT",
            "ONLINE COMPLAINT REGISTRATION PORTAL",
            "TOLL FREE NO",
        )
        return any(token in upper for token in skip_tokens)

    def _is_image_only_pdf(self, file_path: str) -> bool:
        """Return True if the PDF has no extractable text (scanned image)."""
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    if len(text.strip()) > 20:
                        return False
            return True
        except Exception:
            return False

    def _parse_amount(self, value: str) -> Optional[float]:
        try:
            return float(value.replace(",", "").strip())
        except Exception:
            return None


