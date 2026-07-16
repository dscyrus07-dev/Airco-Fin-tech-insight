"""
Airco Insights - Unknown Bank Parser
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
class UnknownTransaction:
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
class UnknownParseResult:
    transactions: List[UnknownTransaction]
    total_count: int
    parse_method: str
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_credits: float = 0.0
    total_debits: float = 0.0


class UnknownParseError(Exception):
    """Raised when Unknown bank parsing fails."""
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


class UnknownParser(BaseBankParser):
    BANK_NAME = "Unknown"

    ROW_RE = re.compile(
        r"^(?P<date>\d{2}-[A-Za-z]{3}-\d{2})"
        r"(?P<rest>.+?)\s+"
        r"(?P<amount>[\d,]+\.\d{2})\s+"
        r"(?P<balance>[\d,]+\.\d{2})\((?P<marker>Cr|Dr)\)$"
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

    def parse(self, file_path: str, text_content: str = "") -> UnknownParseResult:
        """
        MAIN PARSE METHOD - Now with 3-level fallback strategy.
        
        Flow:
        1. Try existing hardcoded parser (targeted_text-based)
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
            # Level 1: Try existing Unknown parser logic
            self.logger.info("Level 1: Trying existing Unknown hardcoded parser")
            result = self._parse_existing_hardcoded(file_path, text_content)
            
            if self._is_valid_result(result):
                # Success with hardcoded
                self._record_metrics("hardcoded", True, result.total_count, start_time)
                self._write_parser_metric("hardcoded", True, result.total_count, start_time)
                self.logger.info(f"Level 1 success: {result.total_count} transactions via hardcoded ({result.parse_method})")
                return result
            
            # Level 2: Dynamic fallback
            self.logger.warning("Level 1 failed for Unknown, trying dynamic fallback")
            self._write_parser_metric("hardcoded", False, 0, start_time)
            result = self._parse_dynamic(file_path)
            
            if self._is_valid_result(result):
                # Success with dynamic
                self._record_metrics("dynamic", True, result.total_count, start_time)
                self._write_parser_metric("dynamic", True, result.total_count, start_time)
                self.logger.warning(f"Level 2 success: {result.total_count} transactions via dynamic")
                return result
            
            # Level 3: Unsupported format
            self.logger.error("Level 2 failed for Unknown, adding to unsupported queue")
            self._add_to_unsupported_queue(file_path, "BOTH_PARSERS_FAILED")
            self._record_metrics("unsupported", False, 0, start_time)
            self._write_parser_metric("unsupported", False, 0, start_time)
            
            return self._create_empty_result("Unsupported Unknown statement format")
            
        except Exception as e:
            self.logger.error(f"Parser error for Unknown: {e}", exc_info=True)
            self._add_to_unsupported_queue(file_path, f"PARSER_ERROR: {str(e)}")
            self._record_metrics("error", False, 0, start_time)
            self._write_parser_metric("error", False, 0, start_time)
            return self._create_empty_result(f"Parser error: {str(e)}")

    def _parse_existing_hardcoded(self, file_path: str, text_content: str = "") -> UnknownParseResult:
        """
        Call the original Unknown parser logic.
        This is the existing parse method without fallback.
        """
        if self._is_image_only_pdf(file_path):
            raise UnknownParseError(
                "This PDF appears to be a scanned image and cannot be processed. "
                "Please upload a text-based PDF.",
                error_code="SCANNED_PDF",
                details={"file": file_path}
            )

        transactions: List[UnknownTransaction] = []
        in_account_section = False
        opening_balance: Optional[float] = None
        prev_balance: Optional[float] = None

        if text_content:
            opening_match = re.search(r"OpeningBalance\s+([-\d,]+\.\d{2})\([CD]r\)", text_content, re.IGNORECASE)
            if opening_match:
                opening_balance = self._parse_amount(opening_match.group(1))
                prev_balance = opening_balance

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                lines = [line.strip() for line in (page.extract_text() or "").splitlines() if line.strip()]
                for i, line in enumerate(lines):
                    if "StatementofBankingAccount" in line:
                        in_account_section = True
                    if not in_account_section:
                        continue
                    if "StatementSummary" in line or "Summary StatementofStandaloneTermDeposit" in line or "DetailedStatementofTermDeposit" in line:
                        in_account_section = False
                        continue
                    if self._is_skip_line(line):
                        continue

                    row = self.ROW_RE.match(line)
                    if row:
                        suffix_lines: List[str] = []
                        j = i + 1
                        while j < len(lines):
                            nxt = lines[j]
                            if self.ROW_RE.match(nxt) or self._is_skip_line(nxt) or "StatementSummary" in nxt or "Summary StatementofStandaloneTermDeposit" in nxt:
                                break
                            suffix_lines.append(nxt)
                            j += 1
                        txn, prev_balance = self._build_transaction(row, suffix_lines, prev_balance)
                        if txn:
                            transactions.append(txn)

        if not transactions:
            raise GenericParseError(
                "Could not extract transactions from this unknown-bank PDF.",
                error_code="NO_TRANSACTIONS",
                details={"file": file_path},
            )

        if opening_balance is None:
            opening_balance = self._infer_opening(transactions[0])
        closing_balance = transactions[-1].balance
        total_credits = sum(txn.credit or 0 for txn in transactions)
        total_debits = sum(txn.debit or 0 for txn in transactions)
        return UnknownParseResult(
            transactions=transactions,
            total_count=len(transactions),
            parse_method="targeted_text",
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits,
        )

    def _parse_dynamic(self, file_path: str) -> UnknownParseResult:
        """
        Dynamic column detection fallback.
        Uses shared DynamicColumnDetector.
        """
        try:
            dynamic_result = self.dynamic_detector.parse(file_path, bank_hint=self.bank_name)
            
            if dynamic_result and dynamic_result.transactions:
                # Convert dynamic result to Unknown format
                return self._convert_dynamic_result(dynamic_result)
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Dynamic parser failed for Unknown: {e}")
            return None

    def _convert_dynamic_result(self, dynamic_result) -> UnknownParseResult:
        """
        Convert DynamicParseResult to UnknownParseResult format.
        """
        # Convert dynamic transactions to UnknownTransaction format
        unknown_transactions = []
        for txn in dynamic_result.transactions:
            unknown_txn = UnknownTransaction(
                date=txn.get("date", ""),
                description=txn.get("description", ""),
                ref_no=txn.get("ref_no", ""),
                debit=self._parse_amount(txn.get("debit")),
                credit=self._parse_amount(txn.get("credit")),
                balance=self._parse_amount(txn.get("balance"))
            )
            unknown_transactions.append(unknown_txn)
        
        # Calculate totals
        total_credits = sum(t.credit or 0 for t in unknown_transactions)
        total_debits = sum(t.debit or 0 for t in unknown_transactions)
        opening_balance = unknown_transactions[0].balance if unknown_transactions else None
        closing_balance = unknown_transactions[-1].balance if unknown_transactions else None
        
        return UnknownParseResult(
            transactions=unknown_transactions,
            total_count=len(unknown_transactions),
            parse_method="dynamic",
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits
        )

    def _is_valid_result(self, result: UnknownParseResult) -> bool:
        """
        Validation for Unknown parsing results.
        """
        if not result:
            return False
        
        # Basic validation
        if result.total_count <= 0:
            return False
        
        if not result.transactions:
            return False
        
        # Unknown-specific validation - minimum threshold
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
            self.logger.warning(f"Added to unsupported queue: Unknown - {reason}")
            
        except Exception as e:
            self.logger.error(f"Failed to add to unsupported queue: {e}")

    def _write_parser_metric(self, method: str, success: bool, transaction_count: int, start_time: datetime = None):
        """Collect parser metric in memory for finalize_job_audit."""
        try:
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000) if start_time else 0
            self._collected_parser_metrics.append({
                'parser_type': method,
                'parser_name': f'UNKNOWN_{method}',
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

    def _create_empty_result(self, error_message: str) -> UnknownParseResult:
        """
        Create empty result with error message.
        """
        return UnknownParseResult(
            transactions=[],
            total_count=0,
            parse_method="failed",
            opening_balance=None,
            closing_balance=None,
            total_credits=0.0,
            total_debits=0.0
        )

    def _build_transaction(
        self,
        row: re.Match[str],
        suffix_lines: List[str],
        prev_balance: Optional[float],
    ) -> Tuple[Optional[UnknownTransaction], Optional[float]]:
        date_text = row.group("date")
        rest = row.group("rest").strip()
        description = " ".join([rest, *suffix_lines]).strip()
        description = self._clean_description(description)

        amount = self._parse_amount(row.group("amount"))
        balance = self._parse_amount(row.group("balance"))
        if balance is None or amount is None:
            return None, prev_balance
        if row.group("marker").upper() == "DR":
            balance = -abs(balance)

        # Opening row stores amount in deposit slot; keep it out of transactions
        if description.upper().startswith("OPENINGBALANCE"):
            return None, prev_balance

        debit, credit = self._infer_direction(description, amount, prev_balance, balance)

        ref_match = re.search(r"\b((?:UPI|TBMS|IMPS)-[A-Z0-9-]+|UPI-[0-9]+|TBMS-[0-9]+|IMPS-[0-9]+)\b", description, re.IGNORECASE)
        ref_no = ref_match.group(1) if ref_match else ""

        txn = UnknownTransaction(
            date=datetime.strptime(date_text, "%d-%b-%y").strftime("%Y-%m-%d"),
            description=description,
            ref_no=ref_no,
            debit=debit,
            credit=credit,
            balance=balance,
        )
        return txn, balance

    def _clean_description(self, text: str) -> str:
        cleaned = text
        replacements = [
            (r"fromPh", "from PhonePe"),
            (r"StatementSummary.*$", ""),
            (r"\s+", " "),
        ]
        for pattern, target in replacements:
            cleaned = re.sub(pattern, target, cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    def _infer_opening(self, txn: UnknownTransaction) -> Optional[float]:
        if txn.credit:
            return round(txn.balance - txn.credit, 2)
        if txn.debit:
            return round(txn.balance + txn.debit, 2)
        return None

    def _infer_direction(
        self,
        description: str,
        amount: float,
        prev_balance: Optional[float],
        balance: float,
    ) -> Tuple[Optional[float], Optional[float]]:
        desc_upper = description.upper()
        amount_abs = abs(amount)

        if prev_balance is not None:
            delta = round(balance - prev_balance, 2)
            if delta >= 0 and abs(delta - amount_abs) <= 1.0:
                return None, amount_abs
            if delta <= 0 and abs(delta + amount_abs) <= 1.0:
                return amount_abs, None

        credit_markers = ("TDINT:", "RECD:IMPS/", "PAYMENT FROM PHONEPE", "FROMPH")
        debit_markers = ("CHRG:", "REMCHRGS:", "UPI/")
        if any(token in desc_upper for token in credit_markers):
            return None, amount_abs
        if any(token in desc_upper for token in debit_markers):
            return amount_abs, None
        return amount_abs, None

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

    def _parse_amount(self, value: Optional[str]) -> Optional[float]:
        if not value:
            return None
        try:
            return float(value.replace(",", "").strip())
        except Exception:
            return None

    def _is_skip_line(self, line: str) -> bool:
        upper = line.upper().strip()
        skip_tokens = (
            "STATEMENTOFBANKINGACCOUNT",
            "DATE NARRATION CHQ/REF NO. WITHDRAWAL(DR) DEPOSIT(CR) BALANCE",
            "STATEMENTSUMMARY",
            "OPENINGBALANCE",
            "TOTALWITHDRAWALAMOUNT",
            "TOTALDEPOSITAMOUNT",
            "CLOSINGBALANCE",
            "SWEEPTDBALANCE",
            "ENDOFSTATEMENT",
            "THISISSYSTEMGENERATEDREPORT",
            "A1",
        )
        return any(token in upper for token in skip_tokens)
