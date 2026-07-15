"""
Airco Insights — Dynamic Column Detector (Level 2 Fallback)
=============================================================
Detects column headers automatically and parses transactions.
Used when hardcoded coordinate parsers fail.

Works across all bank formats by detecting headers dynamically.
"""

import pdfplumber
import re
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class DetectedHeader:
    """A detected column header with its position."""
    name: str
    text: str
    x_center: float
    y_position: float
    x_min: float = 0.0
    x_max: float = 0.0


@dataclass
class DynamicParseResult:
    """Result from dynamic column detection."""
    transactions: List[Dict[str, Any]] = field(default_factory=list)
    total_count: int = 0
    headers_detected: List[str] = field(default_factory=list)
    parse_method: str = "dynamic"
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)


class DynamicColumnDetector:
    """
    Detects column headers automatically and parses transactions.
    Fallback for when hardcoded coordinates fail.
    """
    
    # Universal header patterns - comprehensive coverage for all banks
    HEADER_PATTERNS = {
        "date": [
            r"^date$",
            r"^txn\s*date",
            r"^transaction\s*date",
            r"^value\s*date",
            r"^posting\s*date",
            r"^tran\s*date",
        ],
        "description": [
            r"^narration",
            r"^particulars",
            r"^description",
            r"^details",
            r"^remarks",
            r"^transaction\s*details",
            r"^particular",
        ],
        "debit": [
            r"^debit",
            r"^withdrawal",
            r"^dr\.?",
            r"^withdrawals",
            r"^outflow",
            r"^debits",
            r"^withdrawal\s*amount",
        ],
        "credit": [
            r"^credit",
            r"^deposit",
            r"^cr\.?",
            r"^deposits",
            r"^inflow",
            r"^credits",
            r"^deposit\s*amount",
        ],
        "balance": [
            r"^balance",
            r"^closing\s*balance",
            r"^running\s*balance",
            r"^balance\s*amount",
            r"^avl\s*balance",
            r"^available\s*balance",
        ],
        "ref": [
            r"ref\.?\s*no",
            r"^reference",
            r"^chq",
            r"^cheque",
            r"^mode",
            r"^chq\.?\s*no",
            r"^reference\s*no",
            r"^transaction\s*ref",
        ],
    }
    
    def __init__(self):
        self.headers_found: Dict[str, DetectedHeader] = {}
        self.y_threshold = 25  # Row height tolerance (reduced for better precision)
        self.min_headers_required = 3  # Need at least date, description, and one amount column
        self.column_tolerance = 70  # Distance tolerance for column matching
        
    def parse(self, file_path: str, bank_hint: str = None) -> Optional[DynamicParseResult]:
        """
        Parse PDF using dynamic column detection.
        
        Args:
            file_path: Path to the PDF file
            bank_hint: Optional bank name for logging
            
        Returns:
            DynamicParseResult with transactions, or None if parsing failed
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                if not pdf.pages:
                    logger.warning(f"No pages found in PDF: {file_path}")
                    return None
                
                first_page = pdf.pages[0]
                words = first_page.extract_words(
                    keep_blank_chars=True,
                    x_tolerance=2,
                    y_tolerance=2
                )
                
                if not words:
                    logger.warning(f"No words extracted from PDF: {file_path}")
                    return None
                
                logger.info(f"Extracted {len(words)} words from first page of {bank_hint or 'unknown bank'}")
                
                # Step 1: Find header row (top 30% of page)
                header_region_height = first_page.height * 0.30
                header_candidates = [w for w in words if w["top"] < header_region_height]
                
                logger.info(f"Analyzing {len(header_candidates)} words in header region")
                
                self._detect_headers(header_candidates)
                
                if len(self.headers_found) < self.min_headers_required:
                    logger.warning(
                        f"Insufficient headers detected: {len(self.headers_found)} found, "
                        f"{self.min_headers_required} required. Found: {list(self.headers_found.keys())}"
                    )
                    return None
                
                logger.info(f"Detected headers: {list(self.headers_found.keys())}")
                
                # Step 2: Parse transactions using detected headers
                transactions = []
                page_warnings = []
                
                for page_num, page in enumerate(pdf.pages):
                    page_words = page.extract_words(
                        keep_blank_chars=True,
                        x_tolerance=2,
                        y_tolerance=2
                    )
                    
                    if not page_words:
                        continue
                    
                    rows = self._group_into_rows(page_words)
                    logger.debug(f"Page {page_num + 1}: Grouped into {len(rows)} rows")
                    
                    for row_idx, row in enumerate(rows):
                        txn = self._parse_row(row)
                        if txn:
                            transactions.append(txn)
                        
                        # Limit to prevent runaway processing
                        if len(transactions) >= 5000:
                            page_warnings.append("Limited to 5000 transactions")
                            break
                    
                    if len(transactions) >= 5000:
                        break
                
                # Calculate confidence based on headers detected
                confidence = self._calculate_confidence()
                
                result = DynamicParseResult(
                    transactions=transactions,
                    total_count=len(transactions),
                    headers_detected=list(self.headers_found.keys()),
                    parse_method="dynamic",
                    confidence=confidence,
                    warnings=page_warnings
                )
                
                logger.info(
                    f"Dynamic parsing complete for {bank_hint or 'unknown bank'}: "
                    f"{result.total_count} transactions, confidence={confidence:.1f}%"
                )
                
                return result
                
        except Exception as e:
            logger.error(f"Dynamic column detection failed: {str(e)}", exc_info=True)
            return None
    
    def _detect_headers(self, words: List[Dict]):
        """Find column headers in the word list."""
        self.headers_found = {}
        
        for word in words:
            text = word["text"].strip()
            if not text:
                continue
                
            text_lower = text.lower()
            x = word["x0"] + (word["x1"] - word["x0"]) / 2  # Center x
            
            for header_type, patterns in self.HEADER_PATTERNS.items():
                if header_type in self.headers_found:
                    continue  # Already found this header
                    
                for pattern in patterns:
                    if re.search(pattern, text_lower, re.IGNORECASE):
                        # Calculate boundaries for this column
                        width = word["x1"] - word["x0"]
                        x_min = word["x0"] - width * 0.5
                        x_max = word["x1"] + width * 1.5
                        
                        self.headers_found[header_type] = DetectedHeader(
                            name=header_type,
                            text=text,
                            x_center=x,
                            y_position=word["top"],
                            x_min=x_min,
                            x_max=x_max
                        )
                        logger.debug(f"Detected header '{header_type}' at x={x:.1f}: '{text}'")
                        break
    
    def _group_into_rows(self, words: List[Dict]) -> List[List[Dict]]:
        """Group words into rows based on y-position."""
        # Skip header region (already processed)
        header_y_max = max(
            (h.y_position for h in self.headers_found.values()),
            default=0
        ) + 50  # Add margin below headers
        
        # Group by y-position (with tolerance)
        y_groups = defaultdict(list)
        for w in words:
            if w["top"] < header_y_max:
                continue  # Skip header region
                
            y_key = round(w["top"] / self.y_threshold) * self.y_threshold
            y_groups[y_key].append(w)
        
        # Sort by y-position and return rows
        sorted_rows = []
        for y_key in sorted(y_groups.keys()):
            row_words = y_groups[y_key]
            # Sort words within row by x-position
            row_words.sort(key=lambda w: w["x0"])
            sorted_rows.append(row_words)
        
        return sorted_rows
    
    def _parse_row(self, row_words: List[Dict]) -> Optional[Dict[str, Any]]:
        """Parse a single row using detected headers."""
        if not row_words:
            return None
            
        row_data: Dict[str, str] = {h: "" for h in self.headers_found.keys()}
        
        for word in row_words:
            x = word["x0"] + (word["x1"] - word["x0"]) / 2
            text = word["text"].strip()
            
            # Find closest header column
            closest_header = None
            closest_distance = float('inf')
            
            for header_type, header in self.headers_found.items():
                dist = abs(x - header.x_center)
                # Check if within column boundaries and closer than current best
                if dist < closest_distance and dist < self.column_tolerance:
                    closest_distance = dist
                    closest_header = header_type
            
            if closest_header:
                # Append text to this column
                if row_data[closest_header]:
                    row_data[closest_header] += " " + text
                else:
                    row_data[closest_header] = text
        
        # Validate row has minimum required fields
        has_date = bool(row_data.get("date"))
        has_description = bool(row_data.get("description"))
        has_amount = bool(row_data.get("debit") or row_data.get("credit"))
        
        # Additional validation: date should look like a date
        if has_date:
            date_str = row_data["date"]
            # Quick check for common date patterns
            date_patterns = [
                r'\d{2}[/-]\d{2}[/-]\d{4}',  # DD-MM-YYYY or DD/MM/YYYY
                r'\d{2}\s+[A-Za-z]{3}\s+\d{4}',  # DD MMM YYYY
                r'\d{2}[/-]\d{2}[/-]\d{2}',  # DD-MM-YY
            ]
            has_valid_date = any(re.search(p, date_str) for p in date_patterns)
            if not has_valid_date:
                has_date = False
        
        if has_date and has_description and has_amount:
            return {
                "date": row_data.get("date", "").strip(),
                "description": row_data.get("description", "").strip(),
                "debit": self._clean_amount(row_data.get("debit")),
                "credit": self._clean_amount(row_data.get("credit")),
                "balance": self._clean_amount(row_data.get("balance")),
                "ref_no": row_data.get("ref", "").strip(),
                "parse_method": "dynamic",
            }
        
        return None
    
    def _clean_amount(self, amount_str: Optional[str]) -> Optional[str]:
        """Clean amount string for further processing."""
        if not amount_str:
            return None
        
        cleaned = amount_str.strip()
        
        # Remove common non-numeric characters but keep digits, commas, dots
        cleaned = re.sub(r'[^\d,\.\-]', '', cleaned)
        
        # Validate it looks like an amount
        if not re.search(r'\d', cleaned):
            return None
            
        return cleaned if cleaned else None
    
    def _calculate_confidence(self) -> float:
        """Calculate confidence score based on headers detected."""
        required_headers = {"date", "description"}
        optional_headers = {"debit", "credit", "balance", "ref"}
        
        has_required = all(h in self.headers_found for h in required_headers)
        has_amount = "debit" in self.headers_found or "credit" in self.headers_found
        
        if not has_required or not has_amount:
            return 0.0
        
        # Base confidence for having required headers
        confidence = 70.0
        
        # Bonus for additional headers
        optional_found = sum(1 for h in optional_headers if h in self.headers_found)
        confidence += optional_found * 5  # +5% per optional header
        
        # Cap at 95% (dynamic is never as confident as hardcoded)
        return min(confidence, 95.0)
