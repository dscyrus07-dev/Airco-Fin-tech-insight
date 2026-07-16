"""
Airco Insights — Axis Bank Parser (Accuracy-First)
====================================================
Extracts transactions from Axis Bank PDF statements with 100% row capture.

Axis Statement Format:
- Columns: Tran Date | Chq No | Particulars | Debit | Credit | Balance | Init.Br
- Date format: DD-MM-YYYY
- Amounts in Indian format: 1,03,766.81
- Multi-line narrations wrapped across lines
- Opening Balance shown as separate row

Column X-Coordinate Boundaries (from PDF analysis):
  Date:         x0 <  90
  Chq No:      90 <= x0 < 132
  Particulars: 132 <= x0 < 340
  Debit:       340 <= x0 < 400
  Credit:      400 <= x0 < 460
  Balance:     460 <= x0 < 535
  Init/Br:     x0 >= 535

Strategy:
1. Coordinate-based column detection (primary)
2. Text-based fallback
3. Balance continuity → debit vs credit determination
4. 100% extraction or fail
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime

# Import shared components for 3-level fallback
from .._shared.base_parser import BaseBankParser
from .._shared.dynamic_column_detector import DynamicColumnDetector
from .._shared.unsupported_format_queue import UnsupportedFormatQueue
from .._shared.parser_metrics import ParserMetrics
from .reconciliation import AxisReconciliation

logger = logging.getLogger(__name__)


class AxisParseError(Exception):
    """Raised when Axis Bank parsing fails."""
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


@dataclass
class AxisTransaction:
    """Single Axis Bank transaction."""
    date: str
    description: str
    debit: Optional[float]
    credit: Optional[float]
    balance: float
    chq_no: str = ""
    raw_line: str = ""
    line_number: int = 0

    def to_dict(self) -> dict:
        return {
            "date": self.date,
            "description": self.description,
            "debit": self.debit,
            "credit": self.credit,
            "balance": self.balance,
            "ref_no": self.chq_no,
        }


@dataclass
class AxisParseResult:
    """Result of Axis Bank parsing."""
    transactions: List[AxisTransaction]
    total_count: int
    parse_method: str
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_credits: float = 0.0
    total_debits: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_count": self.total_count,
            "parse_method": self.parse_method,
            "opening_balance": self.opening_balance,
            "closing_balance": self.closing_balance,
            "total_credits": self.total_credits,
            "total_debits": self.total_debits,
            "warnings": self.warnings,
        }


class AxisParser(BaseBankParser):
    """
    Accuracy-first Axis Bank statement parser.
    Uses coordinate-based column detection from pdfplumber word positions.
    """

    BANK_NAME = "Axis"

    # Date pattern: DD-MM-YYYY
    DATE_RE = re.compile(r'^(\d{2}-\d{2}-\d{4})\s*')
    DATE_EXACT_RE = re.compile(r'^\d{2}-\d{2}-\d{4}$')

    # Amount pattern: Indian format
    AMOUNT_RE = re.compile(r'(\d[\d,]*\.\d{2})')

    # ── Column X-coordinate boundaries (Axis PDF — standard 595-unit width) ────
    # NOTE: Axis debit amounts are right-justified in the debit column; small
    # amounts (e.g. '   30.00') start at x0≈323 due to leading whitespace
    # captured by pdfplumber. Setting _COL_PART_MAX=318 ensures these land
    # in the debit bucket rather than the particulars bucket.
    # These are REFERENCE values for a 595-unit wide PDF.
    # The parser auto-scales them to the actual page width.
    _COL_DATE_MAX   = 90      # Date column:    x0 < 90
    _COL_CHQ_MAX    = 132     # Chq No:        90 <= x0 < 132
    _COL_PART_MAX   = 318     # Particulars:  132 <= x0 < 318
    _COL_DEBIT_MAX  = 400     # Debit:        318 <= x0 < 400
    _COL_CREDIT_MAX = 460     # Credit:       400 <= x0 < 460
    _COL_BAL_MAX    = 535     # Balance:      460 <= x0 < 535
                               # Init/Br:      x0 >= 535
    _REFERENCE_WIDTH = 595.0  # Standard A4 portrait width in PDF units

    # Skip page-header/footer y-zones
    _DATA_Y_MIN = 100          # widened from 200 to catch statements with header at lower y
    _DATA_Y_MAX = 900          # widened from 820
    # Y-bucket size: 8 units merges values 5px apart (opening balance text
    # at y=275 and its balance number at y=270 land in the same bucket)
    _Y_BUCKET = 8

    # Patterns to skip
    SKIP_PATTERNS = [
        "AXIS BANK", "Axis Bank Limited", "Account No", "Customer ID",
        "IFSC Code", "MICR Code", "Nominee Registered", "Registered Mobile",
        "Registered Email", "Scheme", "Statement of Axis", "Statement of Account",
        "Tran Date", "Chq No", "Particulars", "Debit", "Credit", "Balance", "Init.",
        "OPENING BALANCE", "CLOSING BALANCE",
        "This is a computer", "does not require signature",
        "Generated On", "Page", "Continued on", "Branch",
    ]

    def __init__(self, audit_service=None, job_id=None):
        super().__init__(audit_service=audit_service, job_id=job_id)
        self.bank_name = self.BANK_NAME
        self._hygiene_result = None
        self._collected_parser_metrics = []
        self.reconciliation = AxisReconciliation(strict_mode=False)
        # Initialize 3-level fallback components
        self.dynamic_detector = DynamicColumnDetector()
        self.unsupported_queue = UnsupportedFormatQueue()
        self.metrics = ParserMetrics()

    def parse(self, file_path: str, text_content: str = "") -> AxisParseResult:
        """
        MAIN PARSE METHOD - Now with 3-level fallback strategy.
        
        Flow:
        1. Try existing hardcoded parser (coordinate/text)
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
            # Level 1: Try existing Axis parser logic
            self.logger.info("Level 1: Trying existing Axis hardcoded parser")
            result = self._parse_existing_hardcoded(file_path, text_content)
            
            if self._is_valid_result(result):
                # Success with hardcoded
                self._record_metrics("hardcoded", True, result.total_count, start_time)
                self._write_parser_metric("hardcoded", True, result.total_count, start_time)
                self.logger.info(f"Level 1 success: {result.total_count} transactions via hardcoded ({result.parse_method})")
                return result
            
            # Level 2: Dynamic fallback
            self.logger.warning("Level 1 failed for Axis, trying dynamic fallback")
            self._write_parser_metric("hardcoded", False, 0, start_time)
            result = self._parse_dynamic(file_path)
            
            if self._is_valid_result(result):
                # Success with dynamic
                self._record_metrics("dynamic", True, result.total_count, start_time)
                self._write_parser_metric("dynamic", True, result.total_count, start_time)
                self.logger.warning(f"Level 2 success: {result.total_count} transactions via dynamic")
                return result
            
            # Level 3: Unsupported format
            self.logger.error("Level 2 failed for Axis, adding to unsupported queue")
            self._add_to_unsupported_queue(file_path, "BOTH_PARSERS_FAILED")
            self._record_metrics("unsupported", False, 0, start_time)
            self._write_parser_metric("unsupported", False, 0, start_time)
            
            return self._create_empty_result("Unsupported Axis statement format")
            
        except Exception as e:
            self.logger.error(f"Parser error for Axis: {e}", exc_info=True)
            self._add_to_unsupported_queue(file_path, f"PARSER_ERROR: {str(e)}")
            self._record_metrics("error", False, 0, start_time)
            self._write_parser_metric("error", False, 0, start_time)
            return self._create_empty_result(f"Parser error: {str(e)}")

    def _parse_existing_hardcoded(self, file_path: str, text_content: str = "") -> AxisParseResult:
        """
        Call the original Axis parser logic.
        This is the existing parse method without fallback.
        """
        self.logger.info("Parsing Axis Bank statement: %s", file_path)

        # Detect scanned/image-only PDFs early
        if self._is_image_only_pdf(file_path):
            raise AxisParseError(
                "This PDF appears to be a scanned image and cannot be processed. "
                "Please upload a text-based PDF downloaded directly from Axis Bank's internet banking portal.",
                error_code="SCANNED_PDF",
                details={"file": file_path}
            )

        coordinate_result = None
        text_result = None

        try:
            coordinate_result = self._parse_with_coordinates(file_path)
            if coordinate_result.total_count > 0:
                self.logger.info(
                    "Coordinate parsing succeeded: %d transactions",
                    coordinate_result.total_count,
                )
        except AxisParseError:
            raise
        except Exception as e:
            self.logger.warning("Coordinate parsing failed: %s, falling back to text", str(e))

        if not text_content:
            text_content = self._extract_text(file_path)

        text_result = self._parse_with_text(text_content)

        result = self._select_best_parse_result(coordinate_result, text_result)

        if result and result.total_count > 0:
            self.logger.info(
                "Axis parser selected %s parsing: %d transactions",
                result.parse_method,
                result.total_count,
            )
            return result

        if text_result.total_count == 0 and (coordinate_result is None or coordinate_result.total_count == 0):
            raise AxisParseError(
                "No transactions extracted from Axis Bank statement. "
                "Please ensure this is a valid text-based Axis Bank statement PDF.",
                error_code="NO_TRANSACTIONS",
                details={"file": file_path}
            )

        if text_result.total_count > 0:
            self.logger.info("Text parsing succeeded: %d transactions", text_result.total_count)
            return text_result

        if coordinate_result and coordinate_result.total_count > 0:
            return coordinate_result

        raise AxisParseError(
            "No transactions extracted from Axis Bank statement. "
            "Please ensure this is a valid text-based Axis Bank statement PDF.",
            error_code="NO_TRANSACTIONS",
            details={"file": file_path}
        )

    def _parse_dynamic(self, file_path: str) -> AxisParseResult:
        """
        Dynamic column detection fallback.
        Uses shared DynamicColumnDetector.
        """
        try:
            dynamic_result = self.dynamic_detector.parse(file_path, bank_hint=self.bank_name)
            
            if dynamic_result and dynamic_result.transactions:
                # Convert dynamic result to Axis format
                return self._convert_dynamic_result(dynamic_result)
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Dynamic parser failed for Axis: {e}")
            return None

    def _convert_dynamic_result(self, dynamic_result) -> AxisParseResult:
        """
        Convert DynamicParseResult to AxisParseResult format.
        """
        # Convert dynamic transactions to AxisTransaction format
        axis_transactions = []
        for txn in dynamic_result.transactions:
            axis_txn = AxisTransaction(
                date=txn.get("date", ""),
                description=txn.get("description", ""),
                debit=self._parse_amount(txn.get("debit")),
                credit=self._parse_amount(txn.get("credit")),
                balance=self._parse_amount(txn.get("balance")),
                chq_no=txn.get("ref_no", ""),
                raw_line="",  # Not available from dynamic parser
                line_number=0  # Not available from dynamic parser
            )
            axis_transactions.append(axis_txn)
        
        # Calculate totals
        total_credits = sum(t.credit or 0 for t in axis_transactions)
        total_debits = sum(t.debit or 0 for t in axis_transactions)
        opening_balance = axis_transactions[0].balance if axis_transactions else None
        closing_balance = axis_transactions[-1].balance if axis_transactions else None
        
        return AxisParseResult(
            transactions=axis_transactions,
            total_count=len(axis_transactions),
            parse_method="dynamic",
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits,
            warnings=[f"Dynamic parsing with {dynamic_result.confidence:.1f}% confidence"]
        )

    def _is_valid_result(self, result: AxisParseResult) -> bool:
        """
        Validation for Axis parsing results.
        """
        if not result:
            return False
        
        # Basic validation
        if result.total_count <= 0:
            return False
        
        if not result.transactions:
            return False
        
        # Axis-specific validation - minimum threshold
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
            self.logger.warning(f"Added to unsupported queue: Axis - {reason}")
            
        except Exception as e:
            self.logger.error(f"Failed to add to unsupported queue: {e}")

    def _write_parser_metric(self, method: str, success: bool, transaction_count: int, start_time: datetime = None):
        """Collect parser metric in memory for finalize_job_audit."""
        try:
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000) if start_time else 0
            self._collected_parser_metrics.append({
                'parser_type': method,
                'parser_name': f'AXIS_{method}',
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

    def _create_empty_result(self, error_message: str) -> AxisParseResult:
        """
        Create empty result with error message.
        """
        return AxisParseResult(
            transactions=[],
            total_count=0,
            parse_method="failed",
            warnings=[error_message]
        )

    def _assess_parse_result(self, result: AxisParseResult) -> tuple:
        """Score a parse result using balance reconciliation and row count."""
        if not result or not result.transactions:
            return (False, float("inf"), float("inf"), 0)

        try:
            reconciliation = self.reconciliation.reconcile(
                [txn.to_dict() if hasattr(txn, "to_dict") else txn for txn in result.transactions],
                expected_opening=result.opening_balance,
                expected_closing=result.closing_balance,
            )
            return (
                bool(reconciliation.is_reconciled),
                len(reconciliation.mismatches),
                float(reconciliation.final_difference),
                result.total_count,
            )
        except Exception as exc:
            self.logger.warning(
                "Axis parse reconciliation check failed for %s parsing: %s",
                result.parse_method,
                exc,
            )
            return (False, float("inf"), float("inf"), result.total_count)

    def _select_best_parse_result(
        self,
        coordinate_result: Optional[AxisParseResult],
        text_result: Optional[AxisParseResult],
    ) -> Optional[AxisParseResult]:
        """Pick the parse result with the best balance continuity and completeness."""
        candidates = []

        for result in (coordinate_result, text_result):
            if result and result.total_count > 0:
                score = self._assess_parse_result(result)
                candidates.append((score, result))

        if not candidates:
            return coordinate_result or text_result

        def _score_key(item):
            (reconciled, mismatch_count, final_difference, count), _result = item
            return (
                1 if reconciled else 0,
                -mismatch_count,
                -final_difference,
                count,
            )

        return max(candidates, key=_score_key)[1]

    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """
        Parse amount string to float for dynamic results.
        Reuse existing Axis amount parsing logic.
        """
        if not amount_str:
            return None
        return self._clean_amount(amount_str)

    def _is_image_only_pdf(self, file_path: str) -> bool:
        """Return True if the PDF has no extractable text (scanned image)."""
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                pages_to_check = min(3, len(pdf.pages))
                for page in pdf.pages[:pages_to_check]:
                    words = page.extract_words()
                    if words:
                        return False
            return True
        except Exception:
            return False

    def _extract_text(self, file_path: str) -> str:
        """Extract text from PDF using pdfplumber."""
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    pages.append(text)
            return "\n".join(pages)
        except Exception as e:
            raise AxisParseError(
                f"Failed to extract text from PDF: {str(e)}",
                error_code="TEXT_EXTRACTION_FAILED",
                details={"error": str(e)}
            )

    def _get_scaled_boundaries(self, page_width: float) -> dict:
        """Scale column boundaries proportionally to actual page width."""
        scale = page_width / self._REFERENCE_WIDTH
        return {
            "date_max":   self._COL_DATE_MAX   * scale,
            "chq_max":    self._COL_CHQ_MAX    * scale,
            "part_max":   self._COL_PART_MAX   * scale,
            "debit_max":  self._COL_DEBIT_MAX  * scale,
            "credit_max": self._COL_CREDIT_MAX * scale,
            "bal_max":    self._COL_BAL_MAX    * scale,
        }

    def _get_column_dynamic(self, x0: float, bounds: dict) -> str:
        """Assign a word to its column based on dynamically scaled x-coordinate."""
        if x0 < bounds["date_max"]:   return "date"
        if x0 < bounds["chq_max"]:    return "chq_no"
        if x0 < bounds["part_max"]:   return "particulars"
        if x0 < bounds["debit_max"]:  return "debit"
        if x0 < bounds["credit_max"]: return "credit"
        if x0 < bounds["bal_max"]:    return "balance"
        return "init_br"

    @staticmethod
    def _get_column(x0: float) -> str:
        """Assign a word to its column based on x-coordinate (legacy static)."""
        if x0 < AxisParser._COL_DATE_MAX:    return "date"
        if x0 < AxisParser._COL_CHQ_MAX:    return "chq_no"
        if x0 < AxisParser._COL_PART_MAX:   return "particulars"
        if x0 < AxisParser._COL_DEBIT_MAX:  return "debit"
        if x0 < AxisParser._COL_CREDIT_MAX: return "credit"
        if x0 < AxisParser._COL_BAL_MAX:    return "balance"
        return "init_br"

    def _extract_page_lines(self, page, bounds: dict = None) -> list:
        """Extract words from a PDF page, group by y into lines, assign to columns."""
        from collections import defaultdict

        words = page.extract_words(keep_blank_chars=True, x_tolerance=2, y_tolerance=2)
        if not words:
            return []

        # Use dynamic bounds if provided, else fall back to static
        use_dynamic = bounds is not None

        y_groups = defaultdict(list)
        for w in words:
            y_key = round(w["top"] / self._Y_BUCKET) * self._Y_BUCKET
            y_groups[y_key].append(w)

        lines = []
        for y_key in sorted(y_groups.keys()):
            if y_key < self._DATA_Y_MIN or y_key > self._DATA_Y_MAX:
                continue

            line_words = sorted(y_groups[y_key], key=lambda w: w["x0"])

            col_words = defaultdict(list)
            for w in line_words:
                if use_dynamic:
                    col = self._get_column_dynamic(w["x0"], bounds)
                else:
                    col = self._get_column(w["x0"])
                col_words[col].append(w["text"])

            lines.append({
                "y": y_key,
                "date": " ".join(col_words.get("date", [])).strip(),
                "chq_no": " ".join(col_words.get("chq_no", [])).strip(),
                "particulars": " ".join(col_words.get("particulars", [])).strip(),
                "debit": " ".join(col_words.get("debit", [])).strip(),
                "credit": " ".join(col_words.get("credit", [])).strip(),
                "balance": " ".join(col_words.get("balance", [])).strip(),
            })

        return lines

    def _parse_with_coordinates(self, file_path: str) -> AxisParseResult:
        """
        Parse Axis Bank PDF using coordinate-based column detection.

        STRATEGY:
        1. Extract words with x,y positions from each page
        2. Group by y-position into visual lines
        3. Assign words to columns by x-coordinate boundaries
        4. Transaction start = valid DD-MM-YYYY in Date col + valid Balance
        5. Continuation = particulars content without date → append to previous txn
        6. Balance continuity determines withdrawal vs deposit
        """
        import pdfplumber

        transactions = []
        prev_balance = None
        opening_balance = None

        with pdfplumber.open(file_path) as pdf:
            # Determine page width from first page and scale column boundaries
            first_page = pdf.pages[0] if pdf.pages else None
            page_width = float(first_page.width) if first_page else self._REFERENCE_WIDTH
            bounds = self._get_scaled_boundaries(page_width)
            self.logger.info("Axis PDF width=%.1f, scale=%.3f", page_width, page_width / self._REFERENCE_WIDTH)

            for page_num, page in enumerate(pdf.pages):
                lines = self._extract_page_lines(page, bounds)

                for line in lines:
                    date_text = line["date"].strip()
                    balance_text = line["balance"].strip()
                    particulars = line["particulars"].strip()

                    # Check for OPENING BALANCE line
                    if "OPENING" in particulars.upper() or "OPENING" in date_text.upper():
                        bal = self._clean_amount(balance_text)
                        if bal is not None:
                            opening_balance = bal
                            prev_balance = bal
                        continue

                    # Check if this is a transaction start line
                    is_date = bool(self.DATE_EXACT_RE.match(date_text))
                    balance_val = self._clean_amount(balance_text) if balance_text else None

                    if is_date and balance_val is not None:
                        debit_val = self._clean_amount(line["debit"])
                        credit_val = self._clean_amount(line["credit"])

                        # Determine debit/credit from balance movement
                        if prev_balance is not None:
                            balance_change = balance_val - prev_balance
                            if balance_change < -0.005:
                                if not debit_val:
                                    debit_val = round(abs(balance_change), 2)
                                credit_val = None
                            elif balance_change > 0.005:
                                if not credit_val:
                                    credit_val = round(balance_change, 2)
                                debit_val = None
                            else:
                                debit_val = None
                                credit_val = None
                        else:
                            if credit_val and not debit_val:
                                pass
                            elif debit_val and not credit_val:
                                pass
                            elif credit_val and debit_val:
                                credit_val = credit_val
                                debit_val = None

                        txn = AxisTransaction(
                            date=date_text,
                            description=particulars,
                            debit=debit_val,
                            credit=credit_val,
                            balance=balance_val,
                            chq_no=line["chq_no"],
                        )
                        transactions.append(txn)
                        prev_balance = balance_val

                    elif transactions and particulars:
                        # Continuation line — append to previous transaction
                        transactions[-1].description += " " + particulars
                        if line["chq_no"] and not transactions[-1].chq_no:
                            transactions[-1].chq_no = line["chq_no"]

        # Normalize whitespace
        for txn in transactions:
            txn.description = " ".join(txn.description.split())

        self.logger.info("Coordinate parsing: %d transactions", len(transactions))

        total_credits = sum(t.credit or 0 for t in transactions)
        total_debits = sum(t.debit or 0 for t in transactions)
        closing = transactions[-1].balance if transactions else None

        if opening_balance is None and transactions:
            first = transactions[0]
            if first.credit:
                opening_balance = first.balance - first.credit
            elif first.debit:
                opening_balance = first.balance + first.debit

        return AxisParseResult(
            transactions=transactions,
            total_count=len(transactions),
            parse_method="coordinate",
            opening_balance=opening_balance,
            closing_balance=closing,
            total_credits=total_credits,
            total_debits=total_debits,
        )

    def _parse_with_text(self, text_content: str) -> AxisParseResult:
        """Text-based fallback parser for Axis Bank statements."""
        lines = text_content.split("\n")
        raw_entries = []
        current_entry = None
        opening_balance = None

        for line_num, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            if self._should_skip_line(stripped):
                # Check for opening balance
                if "OPENING BALANCE" in stripped.upper():
                    amounts = self._extract_amounts(stripped)
                    if amounts:
                        opening_balance = amounts[-1]
                continue

            date_match = self.DATE_RE.match(stripped)
            if date_match:
                date_str = date_match.group(1)
                rest = stripped[date_match.end():].strip()
                amounts = self._extract_amounts(rest)

                if len(amounts) >= 1:
                    if current_entry:
                        raw_entries.append(current_entry)

                    amount_positions = list(self.AMOUNT_RE.finditer(rest))
                    narration_part = rest[:amount_positions[0].start()].strip() if amount_positions else rest

                    current_entry = {
                        "date": date_str,
                        "narration_parts": [narration_part] if narration_part else [],
                        "amounts": amounts,
                        "line_number": line_num,
                    }
                else:
                    if current_entry:
                        raw_entries.append(current_entry)
                    current_entry = {
                        "date": date_str,
                        "narration_parts": [rest] if rest else [],
                        "amounts": [],
                        "line_number": line_num,
                    }
            else:
                if current_entry:
                    amounts = self._extract_amounts(stripped)
                    if amounts and not current_entry["amounts"]:
                        amount_positions = list(self.AMOUNT_RE.finditer(stripped))
                        if amount_positions:
                            narration_part = stripped[:amount_positions[0].start()].strip()
                            if narration_part:
                                current_entry["narration_parts"].append(narration_part)
                        current_entry["amounts"] = amounts
                    else:
                        current_entry["narration_parts"].append(stripped)

        if current_entry:
            raw_entries.append(current_entry)

        # Convert to transactions
        transactions = []
        prev_balance = opening_balance  # seed from opening balance so first txn uses balance-delta

        for entry in raw_entries:
            amounts = entry["amounts"]
            if not amounts:
                continue

            balance = amounts[-1]
            narration = " ".join(entry["narration_parts"]).strip()

            debit = None
            credit = None

            if prev_balance is not None:
                if balance > prev_balance:
                    credit = round(balance - prev_balance, 2)
                elif balance < prev_balance:
                    debit = round(prev_balance - balance, 2)
            else:
                if len(amounts) >= 2:
                    txn_amount = amounts[-2]
                    narration_upper = narration.upper()
                    if any(kw in narration_upper for kw in ["IMPS/P2A", "CREDIT", "SALARY"]):
                        credit = txn_amount
                    else:
                        debit = txn_amount

            prev_balance = balance

            transactions.append(AxisTransaction(
                date=entry["date"],
                description=narration,
                debit=debit,
                credit=credit,
                balance=balance,
                line_number=entry.get("line_number", 0),
            ))

        total_credits = sum(t.credit or 0 for t in transactions)
        total_debits = sum(t.debit or 0 for t in transactions)
        closing = transactions[-1].balance if transactions else None

        return AxisParseResult(
            transactions=transactions,
            total_count=len(transactions),
            parse_method="text",
            opening_balance=opening_balance,
            closing_balance=closing,
            total_credits=total_credits,
            total_debits=total_debits,
        )

    def _should_skip_line(self, line: str) -> bool:
        """Check if line is header/footer/metadata."""
        upper = line.upper()

        # Transaction rows can legitimately contain header-like words in the
        # narration (for example, "AXIS BANK" may appear inside a UPI payer / payee
        # description). If the line starts with a transaction date, it must be
        # treated as data instead of boilerplate.
        if self.DATE_RE.match(line):
            return False

        for pattern in self.SKIP_PATTERNS:
            if pattern.upper() in upper:
                return True
        return False

    def _extract_amounts(self, text: str) -> List[float]:
        """Extract all Indian-format amounts from text."""
        matches = self.AMOUNT_RE.findall(text)
        amounts = []
        for m in matches:
            val = self._clean_amount(m)
            if val is not None:
                amounts.append(val)
        return amounts

    def _clean_amount(self, val: str) -> Optional[float]:
        """Convert Indian-format amount string to float."""
        if not val or not val.strip():
            return None
        cleaned = val.strip().replace(",", "").replace(" ", "")
        try:
            result = float(cleaned)
            return result if result >= 0 else None
        except (ValueError, TypeError):
            return None
