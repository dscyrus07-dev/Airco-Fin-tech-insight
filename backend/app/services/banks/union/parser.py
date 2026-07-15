from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber

from .._shared.generic_bank import GenericParseError

# Import shared components for 3-level fallback
from .._shared.base_parser import BaseBankParser
from .._shared.dynamic_column_detector import DynamicColumnDetector
from .._shared.unsupported_format_queue import UnsupportedFormatQueue
from .._shared.parser_metrics import ParserMetrics


class UnionParseError(Exception):
    """Raised when Union Bank parsing fails."""
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


@dataclass
class UnionTransaction:
    date: str
    description: str
    ref_no: str
    debit: Optional[float]
    credit: Optional[float]
    balance: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "description": self.description,
            "ref_no": self.ref_no,
            "debit": self.debit,
            "credit": self.credit,
            "balance": self.balance,
        }


@dataclass
class UnionParseResult:
    transactions: List[UnionTransaction]
    total_count: int
    parse_method: str
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_credits: float = 0.0
    total_debits: float = 0.0


class UnionParser(BaseBankParser):
    BANK_NAME = "Union"

    FULL_ROW_RE = re.compile(
        r"^(?P<serial>\d+)\s+"
        r"(?P<date>\d{2}/\d{2}/\d{4})\s+"
        r"(?P<rest>.+?)\s+"
        r"(?P<amount>[\d,]+\.\d{2})\s+\((?P<amount_marker>Dr|Cr)\)\s+"
        r"(?P<balance>[\d,]+\.\d{2})\s+\((?P<balance_marker>Dr|Cr)\)$"
    )
    HISTORY_ROW_RE = re.compile(
        r"^(?P<date>\d{2}-\d{2}-\d{4})\s+"
        r"(?P<rest>.+?)\s+"
        r"(?P<amount>[\d,]+\.\d{2})\s+"
        r"(?P<balance>[\d,]+\.\d{2})$"
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

    def parse(self, file_path: str, text_content: str = "") -> UnionParseResult:
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
            _hr = _hc.validate_single_pdf(_Path(file_path))
            self._hygiene_result = _hr
            _hc.log_hygiene_check_result(_hr)
        except Exception as _he:
            self.logger.warning(f"Hygiene check failed (non-fatal): {_he}")

        try:
            # Level 1: Try existing Union parser logic
            self.logger.info("Level 1: Trying existing Union hardcoded parser")
            result = self._parse_existing_hardcoded(file_path, text_content)
            
            if self._is_valid_result(result):
                # Success with hardcoded
                self._record_metrics("hardcoded", True, result.total_count, start_time)
                self._write_parser_metric("hardcoded", True, result.total_count, start_time)
                self.logger.info(f"Level 1 success: {result.total_count} transactions via hardcoded ({result.parse_method})")
                return result
            
            # Level 2: Dynamic fallback
            self.logger.warning("Level 1 failed for Union, trying dynamic fallback")
            self._write_parser_metric("hardcoded", False, 0, start_time)
            result = self._parse_dynamic(file_path)
            
            if self._is_valid_result(result):
                # Success with dynamic
                self._record_metrics("dynamic", True, result.total_count, start_time)
                self._write_parser_metric("dynamic", True, result.total_count, start_time)
                self.logger.warning(f"Level 2 success: {result.total_count} transactions via dynamic")
                return result
            
            # Level 3: Unsupported format
            self.logger.error("Level 2 failed for Union, adding to unsupported queue")
            self._add_to_unsupported_queue(file_path, "BOTH_PARSERS_FAILED")
            self._record_metrics("unsupported", False, 0, start_time)
            self._write_parser_metric("unsupported", False, 0, start_time)
            
            return self._create_empty_result("Unsupported Union statement format")
            
        except Exception as e:
            self.logger.error(f"Parser error for Union: {e}", exc_info=True)
            self._add_to_unsupported_queue(file_path, f"PARSER_ERROR: {str(e)}")
            self._record_metrics("error", False, 0, start_time)
            self._write_parser_metric("error", False, 0, start_time)
            return self._create_empty_result(f"Parser error: {str(e)}")

    def _parse_existing_hardcoded(self, file_path: str, text_content: str = "") -> UnionParseResult:
        """
        Call the original Union parser logic.
        This is the existing parse method without fallback.
        """
        if self._is_image_only_pdf(file_path):
            raise UnionParseError(
                "This PDF appears to be a scanned image and cannot be processed. "
                "Please upload a text-based PDF downloaded directly from Union Bank's internet banking portal.",
                error_code="SCANNED_PDF",
                details={"file": file_path}
            )

        transactions: List[UnionTransaction] = []
        prev_balance: Optional[float] = None

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                lines = [line.strip() for line in (page.extract_text() or "").splitlines() if line and line.strip()]
                page_transactions, prev_balance = self._parse_lines(lines, prev_balance)
                transactions.extend(page_transactions)

        if not transactions:
            raise GenericParseError(
                "Could not extract transactions from this Union Bank PDF.",
                error_code="NO_TRANSACTIONS",
                details={"file": file_path},
            )

        transactions = self._normalize_order(transactions)
        opening_balance = self._infer_opening(transactions[0])
        closing_balance = transactions[-1].balance if transactions else None
        total_credits = sum(txn.credit or 0 for txn in transactions)
        total_debits = sum(txn.debit or 0 for txn in transactions)

        return UnionParseResult(
            transactions=transactions,
            total_count=len(transactions),
            parse_method="text",
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits,
        )

    def _parse_dynamic(self, file_path: str) -> UnionParseResult:
        """
        Dynamic column detection fallback.
        Uses shared DynamicColumnDetector.
        """
        try:
            dynamic_result = self.dynamic_detector.parse(file_path, bank_hint=self.bank_name)
            
            if dynamic_result and dynamic_result.transactions:
                # Convert dynamic result to Union format
                return self._convert_dynamic_result(dynamic_result)
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Dynamic parser failed for Union: {e}")
            return None

    def _convert_dynamic_result(self, dynamic_result) -> UnionParseResult:
        """
        Convert DynamicParseResult to UnionParseResult format.
        """
        # Convert dynamic transactions to UnionTransaction format
        union_transactions = []
        for txn in dynamic_result.transactions:
            union_txn = UnionTransaction(
                date=txn.get("date", ""),
                description=txn.get("description", ""),
                ref_no=txn.get("ref_no", ""),
                debit=self._parse_amount(txn.get("debit")),
                credit=self._parse_amount(txn.get("credit")),
                balance=self._parse_amount(txn.get("balance"))
            )
            union_transactions.append(union_txn)
        
        # Calculate totals
        total_credits = sum(t.credit or 0 for t in union_transactions)
        total_debits = sum(t.debit or 0 for t in union_transactions)
        opening_balance = union_transactions[0].balance if union_transactions else None
        closing_balance = union_transactions[-1].balance if union_transactions else None
        
        return UnionParseResult(
            transactions=union_transactions,
            total_count=len(union_transactions),
            parse_method="dynamic",
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits
        )

    def _is_valid_result(self, result: UnionParseResult) -> bool:
        """
        Validation for Union parsing results.
        """
        if not result:
            return False
        
        # Basic validation
        if result.total_count <= 0:
            return False
        
        if not result.transactions:
            return False
        
        # Union-specific validation - minimum threshold
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
            self.logger.warning(f"Added to unsupported queue: Union - {reason}")
            
        except Exception as e:
            self.logger.error(f"Failed to add to unsupported queue: {e}")

    def _write_parser_metric(self, method: str, success: bool, transaction_count: int, start_time: datetime = None):
        """Collect parser metric in memory for finalize_job_audit."""
        try:
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000) if start_time else 0
            self._collected_parser_metrics.append({
                'parser_type': method,
                'parser_name': f'UNION_{method}',
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

    def _create_empty_result(self, error_message: str) -> UnionParseResult:
        """
        Create empty result with error message.
        """
        return UnionParseResult(
            transactions=[],
            total_count=0,
            parse_method="failed",
            opening_balance=None,
            closing_balance=None,
            total_credits=0.0,
            total_debits=0.0
        )

    def _parse_lines(self, lines: List[str], prev_balance: Optional[float]) -> Tuple[List[UnionTransaction], Optional[float]]:
        transactions: List[UnionTransaction] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if self._is_skip_line(line):
                i += 1
                continue

            row_match = self.FULL_ROW_RE.match(line)
            mode = "full"
            if not row_match:
                row_match = self.HISTORY_ROW_RE.match(line)
                mode = "history"

            if row_match:
                suffix_lines: List[str] = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    if self.FULL_ROW_RE.match(next_line) or self.HISTORY_ROW_RE.match(next_line) or self._is_skip_line(next_line):
                        break
                    suffix_lines.append(next_line)
                    j += 1

                txn, prev_balance = self._build_transaction(row_match, suffix_lines, prev_balance, mode)
                if txn:
                    transactions.append(txn)
                i = j
                continue
            i += 1

        return transactions, prev_balance

    def _build_transaction(
        self,
        row_match: re.Match[str],
        suffix_lines: List[str],
        prev_balance: Optional[float],
        mode: str,
    ) -> Tuple[Optional[UnionTransaction], Optional[float]]:
        amount = self._parse_amount(row_match.group("amount"))
        balance = self._parse_amount(row_match.group("balance"))
        if amount is None or balance is None:
            return None, prev_balance

        balance_marker = row_match.groupdict().get("balance_marker")
        if balance_marker and balance_marker.upper() == "DR":
            balance = -abs(balance)

        raw_rest = row_match.group("rest")
        description = self._build_description(raw_rest, suffix_lines, mode)
        ref_no = self._extract_reference(description, raw_rest)
        debit, credit = self._infer_direction(
            description=description,
            amount=amount,
            prev_balance=prev_balance,
            current_balance=balance,
            amount_marker=row_match.groupdict().get("amount_marker"),
            raw_rest=raw_rest,
        )

        txn = UnionTransaction(
            date=self._normalize_date(row_match.group("date")),
            description=description,
            ref_no=ref_no,
            debit=debit,
            credit=credit,
            balance=balance,
        )
        return txn, balance

    def _build_description(self, raw_rest: str, suffix_lines: List[str], mode: str) -> str:
        text = raw_rest.strip()
        if mode == "full":
            text = re.sub(r"^S\d+\s+", "", text)
        else:
            text = re.sub(r"\s+S\d+\s+(?:-|\w+)?\s*$", "", text)
            text = re.sub(r"\s+S\d+\s+", " ", text)
        text = re.sub(r"\s+-\s*$", "", text).strip()
        suffix = " ".join(line.strip() for line in suffix_lines if line.strip())
        combined = " ".join(part for part in [text, suffix] if part).strip()
        combined = re.sub(r"\s+", " ", combined)
        return self._clean_multiline(combined)

    def _infer_direction(
        self,
        description: str,
        amount: float,
        prev_balance: Optional[float],
        current_balance: float,
        amount_marker: Optional[str],
        raw_rest: str,
    ) -> Tuple[Optional[float], Optional[float]]:
        amount_abs = abs(amount)
        desc_upper = description.upper()
        raw_upper = raw_rest.upper()

        if amount_marker:
            return (amount_abs, None) if amount_marker.upper() == "DR" else (None, amount_abs)

        if prev_balance is not None:
            delta = round(current_balance - prev_balance, 2)
            if abs(delta - amount_abs) <= 1.0:
                return None, amount_abs
            if abs(delta + amount_abs) <= 1.0:
                return amount_abs, None

        credit_markers = ("UPIAB/", "IMPSAB/", "MOBFT FROM:", "NEFT:", "/CR/", "INT.", "POSITIVE PAY")
        debit_markers = ("UPIAR/", "NACH/", "EMANCH/", "MOBFT TO:", "/DR/", "POS:", "RTNCHG", "SMS CHARGES")
        if any(marker in raw_upper or marker in desc_upper for marker in credit_markers):
            return None, amount_abs
        if any(marker in raw_upper or marker in desc_upper for marker in debit_markers):
            return amount_abs, None

        return amount_abs, None

    def _extract_reference(self, description: str, raw_rest: str) -> str:
        txn_match = re.search(r"\b(S\d{6,10})\b", raw_rest)
        if txn_match:
            return txn_match.group(1)
        patterns = [
            r"\b(UPI[ABR]{1,2}/[0-9/]+)",
            r"\b(IMPSAB/[0-9]+)",
            r"\b(NACH/[0-9/]+)",
            r"\b(EMANCH/[0-9/\-A-Z]+)",
            r"\b(MOBFT (?:to|from): [^/]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                return match.group(1)[:120]
        return ""

    def _clean_multiline(self, text: str) -> str:
        cleaned = text
        replacements = [
            (r"gundojisravant", "gundojisravant"),
            (r"cf\.\s*trillionloa", "cf.trillionloa"),
            (r"paytm-\s*(\d+)", r"paytm-\1"),
            (r"BHARATPE\.\s*(\d+)", r"BHARATPE.\1"),
            (r"/CR/\s*", "/CR/"),
            (r"/DR/\s*", "/DR/"),
            (r"\s+@\s*", "@"),
            (r"\s+/\s*", "/"),
            (r"\s+-\s+", "-"),
        ]
        for pattern, target in replacements:
            cleaned = re.sub(pattern, target, cleaned, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", cleaned).strip()

    def _infer_opening(self, txn: UnionTransaction) -> Optional[float]:
        if txn.credit:
            return round(txn.balance - txn.credit, 2)
        if txn.debit:
            return round(txn.balance + txn.debit, 2)
        return None

    def _normalize_order(self, transactions: List[UnionTransaction]) -> List[UnionTransaction]:
        if len(transactions) < 2:
            return transactions
        return list(reversed(transactions)) if transactions[0].date > transactions[-1].date else transactions

    def _normalize_date(self, date_text: str) -> str:
        fmt = "%d/%m/%Y" if "/" in date_text else "%d-%m-%Y"
        return datetime.strptime(date_text, fmt).strftime("%Y-%m-%d")

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

    def _is_skip_line(self, line: str) -> bool:
        upper = line.upper().strip()
        if not upper:
            return True
        exact_or_contains_tokens = (
            "SCAN THE QR CODE", "DETAILS OF STATEMENT", "TO DOWNLOAD VYOM ON", "STATEMENT OF ACCOUNT",
            "UNION BANK OF INDIA", "E-MAIL", "EMAIL ID", "STATEMENT DATE", "STATEMENT PERIOD",
            "RECORDS FROM ", "S.NO DATE TRANSACTION ID REMARKS AMOUNT(RS.) BALANCE(RS.)",
            "DATE REMARKS TRAN ID-1 UTR NUMBER INSTR. ID WITHDRAWALS DEPOSITS BALANCE",
            "NNEEFFTT", "RRTTGGSS", "BBBBPPSS", "HTTP", "FOR ANY QUERIES",
            "THIS IS A SYSTEM GENERATED OUTPUT", "TO AVAIL OUR LOAN PRODUCTS", "PAGE NO",
        )
        if any(token in upper for token in exact_or_contains_tokens):
            return True

        metadata_prefixes = ("NAME ", "ADDRESS ", "CITY ", "STATE ", "COUNTRY ", "ZIP ", "MOBILE NO", "HOME BRANCH")
        return upper.startswith(metadata_prefixes)

