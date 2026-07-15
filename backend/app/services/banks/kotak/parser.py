"""
Airco Insights — Kotak Bank Parser (Accuracy-First)
=====================================================
Extracts transactions from Kotak Mahindra Bank PDF statements with 100% row capture.

Kotak Statement Format:
- Columns: # | Date | Description | Chq/Ref. No. | Withdrawal (Dr.) | Deposit (Cr.) | Balance
- Date format: DD Mon YYYY  (e.g. 01 Oct 2025)
- Row numbers in first column
- Opening Balance shown as special first row (no date, no row number)
- Amounts in Indian format: 1,04,21.00
- Description spans multiple lines (continuation lines in description column only)
- IFSC prefix: KKBK (Kotak Mahindra Bank)

Column X-Coordinate Boundaries (from PDF analysis):
  Row #:         x0 <  55
  Date:         55 <= x0 < 115
  Description: 115 <= x0 < 270
  Chq/Ref No.: 270 <= x0 < 350
  Withdrawal:  350 <= x0 < 425  (Debit)
  Deposit:     425 <= x0 < 495  (Credit)
  Balance:     x0 >= 495

Strategy:
1. Coordinate-based column detection (primary — most reliable for Kotak)
2. Text-based fallback
3. Balance continuity → debit vs credit
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

logger = logging.getLogger(__name__)

# Kotak date: 01 Oct 2025
_KOTAK_DATE_RE    = re.compile(
    r'^(\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})$',
    re.IGNORECASE
)
_KOTAK_DATE_LOOSE = re.compile(
    r'(\d{2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4})',
    re.IGNORECASE
)
_AMOUNT_RE = re.compile(r'(\d[\d,]*\.\d{2})')


class KotakParseError(Exception):
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details    = details or {}
        super().__init__(message)


@dataclass
class KotakTransaction:
    """Single Kotak Bank transaction."""
    date: str
    description: str
    debit:       Optional[float]
    credit:      Optional[float]
    balance:     float
    ref_no:      str = ""
    row_num:     int = 0
    line_number: int = 0

    def to_dict(self) -> dict:
        return {
            "date":        self.date,
            "description": self.description,
            "debit":       self.debit,
            "credit":      self.credit,
            "balance":     self.balance,
            "ref_no":      self.ref_no,
        }


@dataclass
class KotakParseResult:
    transactions:    List[KotakTransaction]
    total_count:     int
    parse_method:    str
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    total_credits:   float = 0.0
    total_debits:    float = 0.0
    warnings:        List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_count":     self.total_count,
            "parse_method":    self.parse_method,
            "opening_balance": self.opening_balance,
            "closing_balance": self.closing_balance,
            "total_credits":   self.total_credits,
            "total_debits":    self.total_debits,
        }


class KotakParser(BaseBankParser):
    """
    Accuracy-first Kotak Bank statement parser.
    Handles DD Mon YYYY date format and numbered row structure.
    """

    BANK_NAME = "Kotak"

    # ── Column X-coordinate boundaries (Kotak PDF — standard 595-unit width) ──
    # These are REFERENCE values calibrated for a 595-unit wide PDF.
    # The parser auto-scales them to the actual page width at runtime.
    _COL_ROWNUM_MAX  = 55        # Row #:       x0 <  55
    _COL_DATE_MAX    = 115       # Date:       55 <= x0 < 115
    _COL_DESC_MAX    = 270       # Description:115 <= x0 < 270
    _COL_REF_MAX     = 350       # Chq/Ref No.:270 <= x0 < 350
    _COL_WDR_MAX     = 425       # Withdrawal: 350 <= x0 < 425
    _COL_DEP_MAX     = 495       # Deposit:    425 <= x0 < 495
                                  # Balance:    x0 >= 495
    _REFERENCE_WIDTH = 595.0    # Standard A4 portrait width in PDF units

    _DATA_Y_MIN_PAGE1 = 300    # first page: skip account header section at top
    _DATA_Y_MIN_OTHERS = 120   # other pages: capture from near top
    _DATA_Y_MAX = 900          # widened from 820

    SKIP_PATTERNS = [
        "Kotak Mahindra Bank", "KOTAK BANK", "KKBK",
        "Account Statement", "Account No.", "Account Type",
        "CRN", "Branch", "Nominee Registered", "Currency",
        "MICR", "IFSC", "Savings Account Transactions",
        "#", "Date", "Description", "Chq/Ref", "Withdrawal",
        "Deposit", "Balance", "Opening Balance",
        "Statement Generated", "Page",
    ]

    def __init__(self, audit_service=None, job_id=None):
        super().__init__(audit_service=audit_service, job_id=job_id)
        self.bank_name = self.BANK_NAME
        self._hygiene_result = None
        self._collected_parser_metrics = []
        # Initialize 3-level fallback components
        self.dynamic_detector = DynamicColumnDetector()
        self.unsupported_queue = UnsupportedFormatQueue()
        self.metrics = ParserMetrics()

    def parse(self, file_path: str, text_content: str = "") -> KotakParseResult:
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
            _hr = _hc.validate_single_pdf(_Path(file_path))
            self._hygiene_result = _hr
            _hc.log_hygiene_check_result(_hr)
        except Exception as _he:
            self.logger.warning(f"Hygiene check failed (non-fatal): {_he}")

        try:
            # Level 1: Try existing Kotak parser logic
            self.logger.info("Level 1: Trying existing Kotak hardcoded parser")
            result = self._parse_existing_hardcoded(file_path, text_content)
            
            if self._is_valid_result(result):
                # Success with hardcoded
                self._record_metrics("hardcoded", True, result.total_count, start_time)
                self._write_parser_metric("hardcoded", True, result.total_count, start_time)
                self.logger.info(f"Level 1 success: {result.total_count} transactions via hardcoded ({result.parse_method})")
                return result
            
            # Level 2: Dynamic fallback
            self.logger.warning("Level 1 failed for Kotak, trying dynamic fallback")
            self._write_parser_metric("hardcoded", False, 0, start_time)
            result = self._parse_dynamic(file_path)
            
            if self._is_valid_result(result):
                # Success with dynamic
                self._record_metrics("dynamic", True, result.total_count, start_time)
                self._write_parser_metric("dynamic", True, result.total_count, start_time)
                self.logger.warning(f"Level 2 success: {result.total_count} transactions via dynamic")
                return result
            
            # Level 3: Unsupported format
            self.logger.error("Level 2 failed for Kotak, adding to unsupported queue")
            self._add_to_unsupported_queue(file_path, "BOTH_PARSERS_FAILED")
            self._record_metrics("unsupported", False, 0, start_time)
            self._write_parser_metric("unsupported", False, 0, start_time)
            
            return self._create_empty_result("Unsupported Kotak statement format")
            
        except Exception as e:
            self.logger.error(f"Parser error for Kotak: {e}", exc_info=True)
            self._add_to_unsupported_queue(file_path, f"PARSER_ERROR: {str(e)}")
            self._record_metrics("error", False, 0, start_time)
            self._write_parser_metric("error", False, 0, start_time)
            return self._create_empty_result(f"Parser error: {str(e)}")

    def _parse_existing_hardcoded(self, file_path: str, text_content: str = "") -> KotakParseResult:
        """
        Call the original Kotak parser logic.
        This is the existing parse method without fallback.
        """
        self.logger.info("Parsing Kotak Bank statement: %s", file_path)

        # Detect scanned/image-only PDFs early
        if self._is_image_only_pdf(file_path):
            raise KotakParseError(
                "This PDF appears to be a scanned image and cannot be processed. "
                "Please upload a text-based PDF downloaded directly from Kotak Bank's internet banking portal.",
                error_code="SCANNED_PDF",
                details={"file": file_path}
            )

        try:
            result = self._parse_with_coordinates(file_path)
            if result.total_count > 0:
                self.logger.info("Coordinate parsing: %d transactions", result.total_count)
                return result
        except KotakParseError:
            raise
        except Exception as e:
            self.logger.warning("Coordinate parsing failed: %s — falling back to text", str(e))

        if not text_content:
            text_content = self._extract_text(file_path)

        result = self._parse_with_text(text_content)

        if result.total_count == 0:
            raise KotakParseError(
                "No transactions extracted from Kotak Bank statement. "
                "Please ensure this is a valid text-based Kotak Bank statement PDF.",
                error_code="NO_TRANSACTIONS",
                details={"file": file_path}
            )

        self.logger.info("Text parsing: %d transactions", result.total_count)
        return result

    def _parse_dynamic(self, file_path: str) -> KotakParseResult:
        """
        Dynamic column detection fallback.
        Uses shared DynamicColumnDetector.
        """
        try:
            dynamic_result = self.dynamic_detector.parse(file_path, bank_hint=self.bank_name)
            
            if dynamic_result and dynamic_result.transactions:
                # Convert dynamic result to Kotak format
                return self._convert_dynamic_result(dynamic_result)
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Dynamic parser failed for Kotak: {e}")
            return None

    def _convert_dynamic_result(self, dynamic_result) -> KotakParseResult:
        """
        Convert DynamicParseResult to KotakParseResult format.
        """
        # Convert dynamic transactions to KotakTransaction format
        kotak_transactions = []
        for txn in dynamic_result.transactions:
            kotak_txn = KotakTransaction(
                date=txn.get("date", ""),
                description=txn.get("description", ""),
                debit=self._parse_amount(txn.get("debit")),
                credit=self._parse_amount(txn.get("credit")),
                balance=self._parse_amount(txn.get("balance")),
                ref_no=txn.get("ref_no", ""),
                row_num=0,  # Not available from dynamic parser
                line_number=0  # Not available from dynamic parser
            )
            kotak_transactions.append(kotak_txn)
        
        # Calculate totals
        total_credits = sum(t.credit or 0 for t in kotak_transactions)
        total_debits = sum(t.debit or 0 for t in kotak_transactions)
        opening_balance = kotak_transactions[0].balance if kotak_transactions else None
        closing_balance = kotak_transactions[-1].balance if kotak_transactions else None
        
        return KotakParseResult(
            transactions=kotak_transactions,
            total_count=len(kotak_transactions),
            parse_method="dynamic",
            opening_balance=opening_balance,
            closing_balance=closing_balance,
            total_credits=total_credits,
            total_debits=total_debits,
            warnings=[f"Dynamic parsing with {dynamic_result.confidence:.1f}% confidence"]
        )

    def _is_valid_result(self, result: KotakParseResult) -> bool:
        """
        Validation for Kotak parsing results.
        """
        if not result:
            return False
        
        # Basic validation
        if result.total_count <= 0:
            return False
        
        if not result.transactions:
            return False
        
        # Kotak-specific validation - minimum threshold
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
            self.logger.warning(f"Added to unsupported queue: Kotak - {reason}")
            
        except Exception as e:
            self.logger.error(f"Failed to add to unsupported queue: {e}")

    def _write_parser_metric(self, method: str, success: bool, transaction_count: int, start_time: datetime = None):
        """Collect parser metric in memory for finalize_job_audit."""
        try:
            elapsed_ms = int((datetime.now() - start_time).total_seconds() * 1000) if start_time else 0
            self._collected_parser_metrics.append({
                'parser_type': method,
                'parser_name': f'KOTAK_{method}',
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

    def _create_empty_result(self, error_message: str) -> KotakParseResult:
        """
        Create empty result with error message.
        """
        return KotakParseResult(
            transactions=[],
            total_count=0,
            parse_method="failed",
            warnings=[error_message]
        )

    def _parse_amount(self, amount_str: str) -> Optional[float]:
        """
        Parse amount string to float for dynamic results.
        Reuse existing Kotak amount parsing logic.
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
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    pages.append(page.extract_text() or "")
            return "\n".join(pages)
        except Exception as e:
            raise KotakParseError(
                f"Failed to extract text: {str(e)}",
                error_code="TEXT_EXTRACTION_FAILED",
            )

    def _get_scaled_boundaries(self, page_width: float) -> dict:
        """Scale column boundaries proportionally to actual page width."""
        scale = page_width / self._REFERENCE_WIDTH
        return {
            "rownum_max": self._COL_ROWNUM_MAX * scale,
            "date_max":   self._COL_DATE_MAX   * scale,
            "desc_max":   self._COL_DESC_MAX   * scale,
            "ref_max":    self._COL_REF_MAX    * scale,
            "wdr_max":    self._COL_WDR_MAX    * scale,
            "dep_max":    self._COL_DEP_MAX    * scale,
        }

    def _get_column_dynamic(self, x0: float, bounds: dict) -> str:
        if x0 < bounds["rownum_max"]: return "rownum"
        if x0 < bounds["date_max"]:   return "date"
        if x0 < bounds["desc_max"]:   return "description"
        if x0 < bounds["ref_max"]:    return "ref_no"
        if x0 < bounds["wdr_max"]:    return "withdrawal"
        if x0 < bounds["dep_max"]:    return "deposit"
        return "balance"

    @staticmethod
    def _get_column(x0: float) -> str:
        if x0 < KotakParser._COL_ROWNUM_MAX:  return "rownum"
        if x0 < KotakParser._COL_DATE_MAX:    return "date"
        if x0 < KotakParser._COL_DESC_MAX:    return "description"
        if x0 < KotakParser._COL_REF_MAX:     return "ref_no"
        if x0 < KotakParser._COL_WDR_MAX:     return "withdrawal"
        if x0 < KotakParser._COL_DEP_MAX:     return "deposit"
        return "balance"

    def _extract_page_lines(self, page, bounds: dict = None, page_num: int = 1) -> list:
        from collections import defaultdict

        words = page.extract_words(keep_blank_chars=True, x_tolerance=2, y_tolerance=2)
        if not words:
            return []

        use_dynamic = bounds is not None
        y_min = self._DATA_Y_MIN_PAGE1 if page_num == 0 else self._DATA_Y_MIN_OTHERS
        y_groups = defaultdict(list)
        for w in words:
            y_key = round(w["top"] / 5) * 5
            y_groups[y_key].append(w)

        lines = []
        for y_key in sorted(y_groups.keys()):
            if y_key < y_min or y_key > self._DATA_Y_MAX:
                continue

            line_words = sorted(y_groups[y_key], key=lambda w: w["x0"])
            col_words  = defaultdict(list)
            for w in line_words:
                if use_dynamic:
                    col = self._get_column_dynamic(w["x0"], bounds)
                else:
                    col = self._get_column(w["x0"])
                col_words[col].append(w["text"])

            lines.append({
                "y":           y_key,
                "rownum":      " ".join(col_words.get("rownum",      [])).strip(),
                "date":        " ".join(col_words.get("date",        [])).strip(),
                "description": " ".join(col_words.get("description", [])).strip(),
                "ref_no":      " ".join(col_words.get("ref_no",      [])).strip(),
                "withdrawal":  " ".join(col_words.get("withdrawal",  [])).strip(),
                "deposit":     " ".join(col_words.get("deposit",     [])).strip(),
                "balance":     " ".join(col_words.get("balance",     [])).strip(),
            })

        return lines

    def _parse_with_coordinates(self, file_path: str) -> KotakParseResult:
        """
        Parse Kotak Bank PDF using coordinate-based column detection.

        Kotak-specific handling:
        - Row numbers in the # column (1, 2, 3...)
        - Opening Balance row: rownum="-", date="-", description="Opening Balance", balance=N
        - Date format: DD Mon YYYY
        - Continuation lines have description text only (no date, no balance)
        """
        import pdfplumber

        transactions    = []
        prev_balance    = None
        opening_balance = None

        with pdfplumber.open(file_path) as pdf:
            first_page = pdf.pages[0] if pdf.pages else None
            page_width = float(first_page.width) if first_page else self._REFERENCE_WIDTH
            bounds = self._get_scaled_boundaries(page_width)
            self.logger.info("Kotak PDF width=%.1f, scale=%.3f", page_width, page_width / self._REFERENCE_WIDTH)

            for page_num, page in enumerate(pdf.pages):
                lines = self._extract_page_lines(page, bounds, page_num=page_num)

                for line in lines:
                    date_text    = line["date"].strip()
                    desc_text    = line["description"].strip()
                    balance_text = line["balance"].strip()
                    rownum_text  = line["rownum"].strip()

                    # Skip header rows
                    if self._is_header_line(date_text, desc_text, rownum_text):
                        continue

                    # Opening balance row: description = "Opening Balance"
                    if "Opening Balance" in desc_text and not _KOTAK_DATE_RE.match(date_text):
                        bal = self._clean_amount(balance_text)
                        if bal is not None:
                            opening_balance = bal
                            prev_balance    = bal
                        continue

                    balance_val = self._clean_amount(balance_text)
                    is_date     = bool(_KOTAK_DATE_RE.match(date_text))

                    if is_date and balance_val is not None:
                        wdr_val = self._clean_amount(line["withdrawal"])
                        dep_val = self._clean_amount(line["deposit"])

                        # Determine debit/credit from balance movement
                        if prev_balance is not None:
                            balance_change = balance_val - prev_balance
                            if balance_change < -0.005:
                                if not wdr_val:
                                    wdr_val = round(abs(balance_change), 2)
                                dep_val = None
                            elif balance_change > 0.005:
                                if not dep_val:
                                    dep_val = round(balance_change, 2)
                                wdr_val = None
                            else:
                                wdr_val = None
                                dep_val = None
                        else:
                            if dep_val and not wdr_val:
                                pass
                            elif wdr_val and not dep_val:
                                pass

                        # Normalize date to YYYY-MM-DD
                        normalized_date = self._normalize_kotak_date(date_text)

                        txn = KotakTransaction(
                            date=normalized_date or date_text,
                            description=desc_text,
                            debit=wdr_val,
                            credit=dep_val,
                            balance=balance_val,
                            ref_no=line["ref_no"],
                        )
                        transactions.append(txn)
                        prev_balance = balance_val

                    elif transactions and desc_text:
                        # Continuation line — append description
                        transactions[-1].description += " " + desc_text
                        if line["ref_no"] and not transactions[-1].ref_no:
                            transactions[-1].ref_no = line["ref_no"]

        # Normalize whitespace
        for txn in transactions:
            txn.description = " ".join(txn.description.split())

        self.logger.info("Kotak coordinate parsing: %d transactions", len(transactions))

        total_credits = sum(t.credit or 0 for t in transactions)
        total_debits  = sum(t.debit  or 0 for t in transactions)
        closing       = transactions[-1].balance if transactions else None

        if opening_balance is None and transactions:
            first = transactions[0]
            if first.credit:
                opening_balance = first.balance - first.credit
            elif first.debit:
                opening_balance = first.balance + first.debit

        return KotakParseResult(
            transactions=transactions,
            total_count=len(transactions),
            parse_method="coordinate",
            opening_balance=opening_balance,
            closing_balance=closing,
            total_credits=total_credits,
            total_debits=total_debits,
        )

    def _parse_with_text(self, text_content: str) -> KotakParseResult:
        """Text-based fallback for Kotak Bank statements."""
        lines           = text_content.split("\n")
        raw_entries     = []
        current_entry   = None
        opening_balance = None

        for line_num, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                continue

            # Opening Balance line
            if "Opening Balance" in stripped:
                amounts = _AMOUNT_RE.findall(stripped)
                if amounts:
                    try:
                        opening_balance = float(amounts[-1].replace(",", ""))
                    except ValueError:
                        pass
                continue

            if self._should_skip_line(stripped):
                continue

            # Look for Kotak date pattern
            date_match = _KOTAK_DATE_LOOSE.search(stripped)
            if date_match:
                date_str = date_match.group(1)
                rest     = stripped[date_match.end():].strip()
                amounts  = [float(m.replace(",", "")) for m in _AMOUNT_RE.findall(rest)]

                if amounts:
                    if current_entry:
                        raw_entries.append(current_entry)

                    amount_positions = list(_AMOUNT_RE.finditer(rest))
                    narration_part   = rest[:amount_positions[0].start()].strip() if amount_positions else rest

                    current_entry = {
                        "date":           self._normalize_kotak_date(date_str) or date_str,
                        "narration_parts": [narration_part] if narration_part else [],
                        "amounts":        amounts,
                        "line_number":    line_num,
                    }
                else:
                    if current_entry:
                        raw_entries.append(current_entry)
                    current_entry = {
                        "date":           self._normalize_kotak_date(date_str) or date_str,
                        "narration_parts": [rest] if rest else [],
                        "amounts":        [],
                        "line_number":    line_num,
                    }
            else:
                if current_entry:
                    amounts = [float(m.replace(",", "")) for m in _AMOUNT_RE.findall(stripped)]
                    if amounts and not current_entry["amounts"]:
                        amount_positions = list(_AMOUNT_RE.finditer(stripped))
                        narration_part   = stripped[:amount_positions[0].start()].strip() if amount_positions else ""
                        if narration_part:
                            current_entry["narration_parts"].append(narration_part)
                        current_entry["amounts"] = amounts
                    else:
                        current_entry["narration_parts"].append(stripped)

        if current_entry:
            raw_entries.append(current_entry)

        transactions = []
        prev_balance = None

        for entry in raw_entries:
            amounts = entry["amounts"]
            if not amounts:
                continue

            balance   = amounts[-1]
            narration = " ".join(entry["narration_parts"]).strip()
            debit     = None
            credit    = None

            if prev_balance is not None:
                if balance > prev_balance:
                    credit = round(balance - prev_balance, 2)
                elif balance < prev_balance:
                    debit  = round(prev_balance - balance, 2)
            else:
                if len(amounts) >= 2:
                    txn_amount = amounts[-2]
                    if any(kw in narration.upper() for kw in ["CREDIT", "SALARY", "UPI-"]):
                        credit = txn_amount
                    else:
                        debit  = txn_amount

            prev_balance = balance

            transactions.append(KotakTransaction(
                date=entry["date"],
                description=narration,
                debit=debit,
                credit=credit,
                balance=balance,
                line_number=entry.get("line_number", 0),
            ))

        total_credits = sum(t.credit or 0 for t in transactions)
        total_debits  = sum(t.debit  or 0 for t in transactions)
        closing       = transactions[-1].balance if transactions else None

        return KotakParseResult(
            transactions=transactions,
            total_count=len(transactions),
            parse_method="text",
            opening_balance=opening_balance,
            closing_balance=closing,
            total_credits=total_credits,
            total_debits=total_debits,
        )

    def _is_header_line(self, date_text: str, desc_text: str, rownum_text: str) -> bool:
        upper_desc = desc_text.upper()
        if upper_desc in ("DATE", "DESCRIPTION", "BALANCE", "WITHDRAWAL (DR.)",
                          "DEPOSIT (CR.)", "CHQ/REF. NO.", "#",
                          "SAVINGS ACCOUNT TRANSACTIONS"):
            return True
        if upper_desc.startswith("STATEMENT GENERATED"):
            return True
        return False

    def _should_skip_line(self, line: str) -> bool:
        upper = line.upper()
        for p in self.SKIP_PATTERNS:
            if p.upper() in upper:
                return True
        return False

    def _normalize_kotak_date(self, date_str: str) -> Optional[str]:
        """Convert DD Mon YYYY → YYYY-MM-DD."""
        for fmt in ["%d %b %Y", "%d %B %Y"]:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _clean_amount(self, val: str) -> Optional[float]:
        if not val or not val.strip():
            return None
        cleaned = val.strip().replace(",", "").replace(" ", "")
        try:
            result = float(cleaned)
            return result if result >= 0 else None
        except (ValueError, TypeError):
            return None
