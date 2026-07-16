"""
Airco Insights - Paytm Bank Parser
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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
class PaytmTransaction:
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
class PaytmParseResult:
    transactions: List[PaytmTransaction]
    total_count: int
    parse_method: str
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_credits: float = 0.0
    total_debits: float = 0.0


class PaytmParseError(Exception):
    """Raised when Paytm Bank parsing fails."""
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class PaytmParser(BaseBankParser):
    BANK_NAME = "Paytm"

    HEADER_RE = re.compile(
        r"^(?P<date>\d{2} [A-Za-z]{3} \d{4})\s+"
        r"(?P<title>.+?)\s+"
        r"(?P<sign>[+-])\s+Rs\.(?P<amount>[\d,]+\.\d{2})\s+Rs\.(?P<balance>[\d,]+\.\d{2})$"
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

    def parse(self, file_path: str, text_content: str = "") -> PaytmParseResult:
        """
        MAIN PARSE METHOD - Now with 3-level fallback strategy.
        
        Flow:
        1. Try existing hardcoded parser (block_text-based)
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
            # Level 1: Try existing Paytm parser logic
            self.logger.info("Level 1: Trying existing Paytm hardcoded parser")
            result = self._parse_existing_hardcoded(file_path, text_content)
            
            if self._is_valid_result(result):
                # Success with hardcoded
                self._record_metrics("hardcoded", True, result.total_count, start_time)
                self._write_parser_metric("hardcoded", True, result.total_count, start_time)
                self.logger.info(f"Level 1 success: {result.total_count} transactions via hardcoded ({result.parse_method})")
                return result
            
            # Level 2: Dynamic fallback
            self.logger.warning("Level 1 failed for Paytm, trying dynamic fallback")
            self._write_parser_metric("hardcoded", False, 0, start_time)
            result = self._parse_dynamic(file_path)
            
            if self._is_valid_result(result):
                # Success with dynamic
                self._record_metrics("dynamic", True, result.total_count, start_time)
                self._write_parser_metric("dynamic", True, result.total_count, start_time)
                self.logger.warning(f"Level 2 success: {result.total_count} transactions via dynamic")
                return result
            
            # Level 3: Unsupported format
            self.logger.error("Level 2 failed for Paytm, adding to unsupported queue")
            self._add_to_unsupported_queue(file_path, "BOTH_PARSERS_FAILED")
            self._record_metrics("unsupported", False, 0, start_time)
            self._write_parser_metric("unsupported", False, 0, start_time)
            
            return self._create_empty_result("Unsupported Paytm statement format")
            
        except Exception as e:
            self.logger.error(f"Parser error for Paytm: {e}", exc_info=True)
            self._add_to_unsupported_queue(file_path, f"PARSER_ERROR: {str(e)}")
            self._record_metrics("error", False, 0, start_time)
            self._write_parser_metric("error", False, 0, start_time)
            return self._create_empty_result(f"Parser error: {str(e)}")

    def _parse_existing_hardcoded(self, file_path: str, text_content: str = "") -> PaytmParseResult:
        """
        Call the original Paytm parser logic.
        This is the existing parse method without fallback.
        """
        if self._is_image_only_pdf(file_path):
            raise PaytmParseError(
                "This PDF appears to be a scanned image and cannot be processed. "
                "Please upload a text-based PDF downloaded directly from Paytm Bank's internet banking portal.",
                error_code="SCANNED_PDF",
                details={"file": file_path}
            )

        transactions: List[PaytmTransaction] = []
        opening_balance: Optional[float] = None
        closing_balance: Optional[float] = None

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                lines = [line.strip() for line in (page.extract_text() or "").splitlines() if line and line.strip()]
                page_transactions = self._parse_page(lines)
                transactions.extend(page_transactions)

        if text_content and opening_balance is None:
            summary_match = re.search(
                r"Rs\.\s*([-\d,]+\.\d{2})\s+Rs\.\s*([-\d,]+\.\d{2})\s+Rs\.\s*([-\d,]+\.\d{2})\s+Rs\.\s*([-\d,]+\.\d{2})\s+OPENING BALANCE TOTAL DEPOSIT TOTAL WITHDRAWAL CLOSING BALANCE",
                text_content,
                re.IGNORECASE | re.DOTALL,
            )
            if summary_match:
                opening_balance = self._parse_amount(summary_match.group(1))

        if not transactions:
            raise GenericParseError(
                "Could not extract transactions from this Paytm PDF.",
                error_code="NO_TRANSACTIONS",
                details={"file": file_path},
            )

        if opening_balance is None:
            opening_balance = self._infer_opening(transactions[0])
        closing_balance = transactions[-1].balance
        total_credits = sum(txn.credit or 0 for txn in transactions)
        total_debits = sum(txn.debit or 0 for txn in transactions)
        return PaytmParseResult(
            transactions=transactions,
            total_count=len(transactions),
            parse_method="block_text",
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits,
        )

    def _parse_dynamic(self, file_path: str) -> PaytmParseResult:
        """
        Dynamic column detection fallback.
        Uses shared DynamicColumnDetector.
        """
        try:
            dynamic_result = self.dynamic_detector.parse(file_path, bank_hint=self.bank_name)
            
            if dynamic_result and dynamic_result.transactions:
                # Convert dynamic result to Paytm format
                return self._convert_dynamic_result(dynamic_result)
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Dynamic parser failed for Paytm: {e}")
            return None

    def _convert_dynamic_result(self, dynamic_result) -> PaytmParseResult:
        """
        Convert DynamicParseResult to PaytmParseResult format.
        """
        # Convert dynamic transactions to PaytmTransaction format
        paytm_transactions = []
        for txn in dynamic_result.transactions:
            paytm_txn = PaytmTransaction(
                date=txn.get("date", ""),
                description=txn.get("description", ""),
                ref_no=txn.get("ref_no", ""),
                debit=self._parse_amount(txn.get("debit")),
                credit=self._parse_amount(txn.get("credit")),
                balance=self._parse_amount(txn.get("balance"))
            )
            paytm_transactions.append(paytm_txn)
        
        # Calculate totals
        total_credits = sum(t.credit or 0 for t in paytm_transactions)
        total_debits = sum(t.debit or 0 for t in paytm_transactions)
        opening_balance = paytm_transactions[0].balance if paytm_transactions else None
        closing_balance = paytm_transactions[-1].balance if paytm_transactions else None
        
        return PaytmParseResult(
            transactions=paytm_transactions,
            total_count=len(paytm_transactions),
            parse_method="dynamic",
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits
        )

    def _is_valid_result(self, result: PaytmParseResult) -> bool:
        """
        Validation for Paytm parsing results.
        """
        if not result:
            return False
        
        # Basic validation
        if result.total_count <= 0:
            return False
        
        if not result.transactions:
            return False
        
        # Paytm-specific validation - minimum threshold
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
            self.logger.warning(f"Added to unsupported queue: Paytm - {reason}")
            
        except Exception as e:
            self.logger.error(f"Failed to add to unsupported queue: {e}")

    def _write_parser_metric(self, method: str, success: bool, transaction_count: int, start_time: datetime = None):
        """Collect parser metric in memory for finalize_job_audit."""
        try:
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000) if start_time else 0
            self._collected_parser_metrics.append({
                'parser_type': method,
                'parser_name': f'PAYTM_{method}',
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

    def _create_empty_result(self, error_message: str) -> PaytmParseResult:
        """
        Create empty result with error message.
        """
        return PaytmParseResult(
            transactions=[],
            total_count=0,
            parse_method="failed",
            opening_balance=None,
            closing_balance=None,
            total_credits=0.0,
            total_debits=0.0
        )

    def _parse_page(self, lines: List[str]) -> List[PaytmTransaction]:
        transactions: List[PaytmTransaction] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if self._is_skip_line(line):
                i += 1
                continue

            header = self.HEADER_RE.match(line)
            if not header:
                i += 1
                continue

            block = [line]
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if self.HEADER_RE.match(next_line) or self._is_skip_line(next_line):
                    break
                block.append(next_line)
                j += 1

            txn = self._build_transaction(header, block[1:])
            if txn:
                transactions.append(txn)
            i = j

        return transactions

    def _build_transaction(self, header: re.Match[str], detail_lines: List[str]) -> Optional[PaytmTransaction]:
        amount = self._parse_amount(header.group("amount"))
        balance = self._parse_amount(header.group("balance"))
        if amount is None or balance is None:
            return None

        sign = header.group("sign")
        title = header.group("title").strip()
        cleaned_detail = [line.strip() for line in detail_lines if line.strip()]
        description = self._build_description(title, cleaned_detail)
        ref_no = self._extract_reference(cleaned_detail)

        debit = amount if sign == "-" else None
        credit = amount if sign == "+" else None

        return PaytmTransaction(
            date=datetime.strptime(header.group("date"), "%d %b %Y").strftime("%Y-%m-%d"),
            description=description,
            ref_no=ref_no,
            debit=debit,
            credit=credit,
            balance=balance,
        )

    def _build_description(self, title: str, detail_lines: List[str]) -> str:
        informative = []
        for line in detail_lines:
            if re.match(r"^\d{1,2}:\d{2} [AP]M$", line):
                continue
            if line.startswith("Transaction ID") or line.startswith("Reference Number") or line.startswith("Reference No") or line.startswith("UPI Reference No") or line.startswith("Mandate Ref. No"):
                continue
            if line.startswith("From Account Number"):
                continue
            informative.append(line)

        description = " | ".join([title, *informative]) if informative else title
        description = re.sub(r"\s+", " ", description).strip()
        return description

    def _extract_reference(self, detail_lines: List[str]) -> str:
        patterns = [
            r"Transaction ID\s*:?\s*([A-Z0-9]+)",
            r"Reference Number:\s*([A-Z0-9]+)",
            r"Reference No\s*:?\s*([A-Za-z0-9]+)",
            r"UPI Reference No\s*:?\s*([A-Za-z0-9]+)",
            r"Mandate Ref\. No\s+([A-Za-z0-9]+)",
        ]
        for line in detail_lines:
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    return match.group(1)[:120]
        return ""

    def _infer_opening(self, txn: PaytmTransaction) -> Optional[float]:
        if txn.credit:
            return round(txn.balance - txn.credit, 2)
        if txn.debit:
            return round(txn.balance + txn.debit, 2)
        return None

    def _is_skip_line(self, line: str) -> bool:
        upper = line.upper().strip()
        skip_tokens = (
            "ACCOUNT STATEMENT FOR:",
            "OPENING BALANCE TOTAL DEPOSIT TOTAL WITHDRAWAL CLOSING BALANCE",
            "ACCOUNT NUMBER ACCOUNT TYPE IFSC MICR NOMINEE",
            "NEVER SHARE",
            "DETAILS CAN LEAD",
            "DATE & TIME TRANSACTION DETAILS AMOUNT AVAILABLE BALANCE",
            "THIS STATEMENT CONTAINS TRANSACTIONS UPTO",
            "TO VIEW TERMS & CONDITIONS",
            "EACH DEPOSITOR IS INSURED",
            "HELD BY HIM/HER",
            "NEED HELP?",
            "**** THIS IS COMPUTER GENERATED",
            "GSTIN -",
            "PPBL NOIDA BRANCH",
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
