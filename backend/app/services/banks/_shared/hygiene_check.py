import os
import logging
import re
import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING
from dataclasses import dataclass
from pypdf import PdfReader
import pdfplumber

if TYPE_CHECKING:
    from app.services.audit import AuditService

# Configure logging
logger = logging.getLogger(__name__)

# In-process cache: avoid re-running hygiene on the same PDF within one job
_HYGIENE_CACHE: Dict[str, Tuple[float, "HygieneCheckResult"]] = {}
# Avoid double audit writes when hygiene is re-logged by bank parsers
_HYGIENE_LOGGED_JOBS: set = set()



def get_cached_hygiene(pdf_path: Path | str) -> Optional["HygieneCheckResult"]:
    """Return cached hygiene result when file mtime matches."""
    try:
        path = Path(pdf_path)
        key = str(path.resolve())
        mtime = path.stat().st_mtime
        hit = _HYGIENE_CACHE.get(key)
        if hit and hit[0] == mtime:
            return hit[1]
    except Exception:
        return None
    return None


def cache_hygiene_result(pdf_path: Path | str, result: "HygieneCheckResult") -> None:
    try:
        path = Path(pdf_path)
        key = str(path.resolve())
        mtime = path.stat().st_mtime
        _HYGIENE_CACHE[key] = (mtime, result)
        # Bound cache size
        if len(_HYGIENE_CACHE) > 64:
            oldest = next(iter(_HYGIENE_CACHE))
            _HYGIENE_CACHE.pop(oldest, None)
    except Exception:
        pass


@dataclass
class HygieneCheckResult:
    """Result of PDF hygiene check"""
    is_healthy: bool
    file_name: str
    page_count: int
    bank_name: str
    format_id: str
    transaction_count: int
    start_date: Optional[str]
    end_date: Optional[str]
    user_id: str
    goal_id: str
    issues: List[str]
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging"""
        return {
            "File Name": self.file_name,
            "No of Pages": self.page_count,
            "Bank Name": self.bank_name,
            "Format ID": self.format_id,
            "No of Transactions": self.transaction_count,
            "Start Date": self.start_date or "N/A",
            "End Date": self.end_date or "N/A",
            "User ID": self.user_id,
            "Goal ID": self.goal_id,
            "Issues": self.issues,
            "Warnings": self.warnings
        }

class HygieneCheck:
    # Canonical bank key -> format-id prefix
    BANK_CODE_MAP = {
        'hdfc': 'HDF',
        'axis': 'AXI',
        'icici': 'ICI',
        'bank of india': 'BOI',
        'indian bank': 'IDB',
        'sbi': 'SBI',
        'kotak': 'KOT',
        'idfc': 'IDF',
        'canara': 'CAN',
        'union': 'UNI',
        'bank of baroda': 'BOB',
        'karnataka bank': 'KAR',
        'paytm': 'PAY',
        'unknown': 'UNK',
    }

    # Aliases / display variants -> canonical key
    BANK_ALIASES = {
        'hdfc': 'hdfc',
        'hdfc bank': 'hdfc',
        'hdfc bank limited': 'hdfc',
        'axis': 'axis',
        'axis bank': 'axis',
        'axis bank limited': 'axis',
        'icici': 'icici',
        'icici bank': 'icici',
        'icici bank limited': 'icici',
        'bank of india': 'bank of india',
        'bankofindia': 'bank of india',
        'boi': 'bank of india',
        'indian bank': 'indian bank',
        'indianbank': 'indian bank',
        'sbi': 'sbi',
        'state bank': 'sbi',
        'state bank of india': 'sbi',
        'kotak': 'kotak',
        'kotak bank': 'kotak',
        'kotak mahindra': 'kotak',
        'kotak mahindra bank': 'kotak',
        'idfc': 'idfc',
        'idfc bank': 'idfc',
        'idfc first': 'idfc',
        'idfc first bank': 'idfc',
        'canara': 'canara',
        'canara bank': 'canara',
        'union': 'union',
        'union bank': 'union',
        'union bank of india': 'union',
        'bank of baroda': 'bank of baroda',
        'bankofbaroda': 'bank of baroda',
        'bob': 'bank of baroda',
        'karnataka': 'karnataka bank',
        'karnataka bank': 'karnataka bank',
        'paytm': 'paytm',
        'paytm bank': 'paytm',
        'paytm payments bank': 'paytm',
        'unknown': 'unknown',
    }

    # Strong phrase / IFSC patterns on *normalized* text (spaces, no underscores)
    # Weights: longer / IFSC beats short tokens. No generic "account statement".
    BANK_TEXT_PATTERNS = [
        ('bank of baroda', [
            (r'\bbank of baroda\b', 12),
            (r'\bbaroda\b', 4),
            (r'\bbarbo[0-9a-z]{6,}\b', 14),
            (r'\bbob\b', 3),
        ]),
        ('union', [
            (r'\bunion bank of india\b', 12),
            (r'\bunion bank\b', 9),
            (r'\bubin[0-9a-z]{6,}\b', 14),
        ]),
        ('hdfc', [
            (r'\bhdfc bank limited\b', 14),
            (r'\bhdfc bank\b', 12),
            (r'\bhdfc\b', 10),
            (r'\bhdfc0[0-9a-z]{6,}\b', 14),
        ]),
        ('axis', [
            (r'\baxis bank limited\b', 14),
            (r'\baxis bank\b', 12),
            (r'\baxis\b', 9),
            (r'\butib0[0-9a-z]{6,}\b', 14),
        ]),
        ('icici', [
            (r'\bicici bank limited\b', 14),
            (r'\bicici bank\b', 12),
            (r'\bicici\b', 10),
            (r'\bicic0[0-9a-z]{6,}\b', 14),
        ]),
        # Order matters for scoring ties: full "bank of india" before short BOI
        ('bank of india', [
            (r'\bbank of india\b', 12),
            (r'\bbkid[0-9a-z]{6,}\b', 14),
            (r'\bboi\b', 4),
        ]),
        ('indian bank', [
            (r'\bindian bank\b', 12),
            (r'\bidib0[0-9a-z]{6,}\b', 14),
        ]),
        ('sbi', [
            (r'\bstate bank of india\b', 14),
            (r'\bstate bank\b', 10),
            (r'\bsbin0[0-9a-z]{6,}\b', 14),
            (r'\bsbi\b', 8),
        ]),
        ('kotak', [
            (r'\bkotak mahindra bank\b', 14),
            (r'\bkotak mahindra\b', 12),
            (r'\bkotak bank\b', 11),
            (r'\bkotak\b', 9),
            (r'\bkkbk0[0-9a-z]{6,}\b', 14),
        ]),
        ('idfc', [
            (r'\bidfc first bank\b', 14),
            (r'\bidfc first\b', 12),
            (r'\bidfc bank\b', 11),
            (r'\bidfc\b', 9),
            (r'\bidfb0[0-9a-z]{6,}\b', 14),
        ]),
        ('canara', [
            (r'\bcanara bank\b', 12),
            (r'\bcanara\b', 9),
            (r'\bcnrb0[0-9a-z]{6,}\b', 14),
        ]),
        ('karnataka bank', [
            (r'\bkarnataka bank\b', 12),
            (r'\bkarnataka\b', 7),
            (r'\bkarb0[0-9a-z]{6,}\b', 14),
        ]),
        ('paytm', [
            (r'\bpaytm payments bank\b', 14),
            (r'\bpaytm bank\b', 12),
            (r'\bpaytm\b', 9),
            (r'\bpytm0[0-9a-z]{6,}\b', 14),
        ]),
    ]

    # Compact filename tokens (no spaces) — catches hdfcsiva, HDFC_Bank, etc.
    FILENAME_TOKEN_HINTS = [
        ('hdfc', 'hdfc', 15),
        ('icici', 'icici', 15),
        ('axis', 'axis', 12),
        ('kotak', 'kotak', 12),
        ('idfc', 'idfc', 12),
        ('canara', 'canara', 12),
        ('paytm', 'paytm', 12),
        ('karnataka', 'karnataka bank', 12),
        ('unionbank', 'union', 14),
        ('union', 'union', 8),
        ('baroda', 'bank of baroda', 12),
        ('bankofbaroda', 'bank of baroda', 15),
        ('bankofindia', 'bank of india', 15),
        ('indianbank', 'indian bank', 15),
        ('statebank', 'sbi', 14),
        ('sbin', 'sbi', 12),
        ('sbi', 'sbi', 10),
        ('idib', 'indian bank', 14),
        ('bkid', 'bank of india', 14),
        ('hdfc0', 'hdfc', 16),
        ('icic0', 'icici', 16),
        ('utib0', 'axis', 16),
    ]

    def __init__(self, pdf_directory, audit_service: Optional['AuditService'] = None, job_id: Optional[str] = None):
        self.pdf_directory = Path(pdf_directory)
        self.audit_service = audit_service
        self.job_id = job_id
        self.bank_mapping = self.load_bank_mapping()
        self.bank_keywords = {
            'hdfc': ['hdfc', 'hdfc bank'],
            'icici': ['icici', 'icici bank'],
            'bank of india': ['bank of india', 'bankofindia', 'boi', 'bkid', 'detailed statement'],
            'indian bank': ['indian bank', 'idib', 'account activity'],
            'axis': ['axis', 'axis bank'],
            'sbi': ['sbi', 'state bank', 'state bank of india'],
            'kotak': ['kotak', 'kotak bank'],
            'idfc': ['idfc', 'idfc first bank'],
            'canara': ['canara', 'canara bank'],
            'union': ['union', 'union bank'],
            'bank of baroda': ['bank of baroda', 'bob'],
            'karnataka bank': ['karnataka bank'],
            'paytm': ['paytm', 'paytm payments bank']
        }
    
    def load_bank_mapping(self):
        """Load bank mapping from CSV file"""
        mapping = {}
        try:
            csv_path = Path(__file__).parent / 'bank_mapping.csv'
            logger.info(f"Looking for bank mapping at: {csv_path}")
            logger.info(f"CSV exists: {csv_path.exists()}")
            
            if csv_path.exists():
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        mapping[row['Name']] = row['Bank']
                logger.info(f"Loaded bank mapping with {len(mapping)} entries")
            else:
                logger.warning("bank_mapping.csv not found, using fallback detection")
        except Exception as e:
            logger.error(f"Error loading bank mapping: {e}")
        return mapping

    @staticmethod
    def _normalize_for_match(text: str) -> str:
        """Lowercase and turn non-alnum into spaces so HDFC_Bank / hdfcsiva match."""
        if not text:
            return ""
        return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()

    def canonicalize_bank_name(self, bank_name: Optional[str]) -> str:
        """Map any alias / UI label to a canonical bank key."""
        if not bank_name:
            return "unknown"
        raw = bank_name.strip().lower()
        if raw in self.BANK_ALIASES:
            return self.BANK_ALIASES[raw]
        compact = re.sub(r'[^a-z0-9]+', '', raw)
        for alias, canonical in self.BANK_ALIASES.items():
            if re.sub(r'[^a-z0-9]+', '', alias) == compact:
                return canonical
        # Last-resort substring on known tokens
        for token, canonical, _w in self.FILENAME_TOKEN_HINTS:
            if token in compact and len(token) >= 4:
                return canonical
        return raw if raw in self.BANK_CODE_MAP else "unknown"

    def _score_bank_candidates(self, text: str) -> Dict[str, int]:
        """Score bank matches on normalized text (phrases + IFSC)."""
        scores: Dict[str, int] = {}
        norm = self._normalize_for_match(text)
        if not norm:
            return scores

        for bank_name, patterns in self.BANK_TEXT_PATTERNS:
            score = 0
            for pattern, weight in patterns:
                if re.search(pattern, norm, re.IGNORECASE):
                    score = max(score, weight)
            if score > 0:
                scores[bank_name] = scores.get(bank_name, 0) + score
        return scores

    def _score_filename_tokens(self, filename: str) -> Dict[str, int]:
        """Score compact filename tokens (hdfcsiva, HDFC_Bank_Statement, …)."""
        scores: Dict[str, int] = {}
        compact = re.sub(r'[^a-z0-9]+', '', (filename or '').lower())
        if not compact or compact.startswith('tmp'):
            # Still allow bank token inside tmp-prefixed originals that keep name
            pass
        for token, bank, weight in self.FILENAME_TOKEN_HINTS:
            if token in compact:
                scores[bank] = max(scores.get(bank, 0), weight)
        # Phrase scoring on spaced filename
        phrase_scores = self._score_bank_candidates(filename or '')
        for bank, score in phrase_scores.items():
            scores[bank] = max(scores.get(bank, 0), score + 2)
        return scores

    def _pick_best_bank(self, scores: Dict[str, int], min_score: int = 6) -> Optional[str]:
        if not scores:
            return None
        best_bank, best_score = max(scores.items(), key=lambda item: item[1])
        if best_score < min_score:
            return None
        # Ambiguous: require clear margin when top two are close
        ranked = sorted(scores.values(), reverse=True)
        if len(ranked) > 1 and ranked[0] == ranked[1]:
            return None
        if len(ranked) > 1 and ranked[0] - ranked[1] < 2 and ranked[0] < 12:
            return None
        return best_bank

    def detect_bank_name(
        self,
        pdf_path,
        original_filename: Optional[str] = None,
        bank_hint: Optional[str] = None,
        header_text: Optional[str] = None,
    ) -> str:
        """Detect bank: user hint → original filename → path name → PDF header."""
        # 1) Explicit user / job selection (highest trust when valid)
        if bank_hint:
            canonical = self.canonicalize_bank_name(bank_hint)
            if canonical != "unknown":
                return canonical

        # 2) Original upload name + temp path name
        names = []
        if original_filename:
            names.append(original_filename)
        try:
            names.append(Path(pdf_path).name)
        except Exception:
            pass

        combined_name_scores: Dict[str, int] = {}
        for name in names:
            for bank, score in self._score_filename_tokens(name).items():
                combined_name_scores[bank] = max(combined_name_scores.get(bank, 0), score)
        picked = self._pick_best_bank(combined_name_scores, min_score=8)
        if picked:
            return picked

        # 3) PDF header / sample text
        text = header_text
        if text is None:
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    if pdf.pages:
                        text = pdf.pages[0].extract_text() or ""
            except Exception as e:
                logger.error(f"Error reading PDF content for bank detection: {e}")
                text = ""
        text_scores = self._score_bank_candidates(text or "")
        picked = self._pick_best_bank(text_scores, min_score=8)
        if picked:
            return picked

        return "unknown"

    def get_pdf_page_count(self, pdf_path):
        """Extract number of pages from PDF"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                return len(pdf_reader.pages)
        except Exception as e:
            logger.error(f"Error reading page count for {pdf_path}: {e}")
            return 0

    
    def extract_transactions_and_dates(self, pdf_path, max_pages: int = 4):
        """Extract approximate txn count + date range from PDF (fast sample).

        Scans only a few first/last pages. No table extraction — text lines only.
        Full transaction extraction still happens in the bank parser.
        """
        transactions = []
        dates = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)
                if total_pages <= max_pages:
                    page_indexes = list(range(total_pages))
                else:
                    head = list(range(min(2, total_pages)))
                    tail = list(range(max(total_pages - 2, 0), total_pages))
                    page_indexes = sorted(set(head + tail))

                date_patterns = [
                    r'\b(\d{2})[-/](\d{2})[-/](\d{4})\b',
                    r'\b(\d{2})[-/](\d{2})[-/](\d{2})\b',
                    r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})\b',
                ]

                for idx in page_indexes:
                    page = pdf.pages[idx]
                    # layout=False is faster for hygiene sampling
                    text = page.extract_text() or ""
                    if not text:
                        continue

                    for pattern in date_patterns:
                        matches = re.findall(pattern, text, re.IGNORECASE)
                        for match in matches:
                            try:
                                if len(match) == 3:
                                    if match[1].isalpha():
                                        date_str = f"{match[0]} {match[1]} {match[2]}"
                                        date_obj = datetime.strptime(date_str, '%d %b %Y')
                                    else:
                                        day, month, year = match
                                        if len(year) == 2:
                                            year = '20' + year
                                        date_obj = datetime.strptime(f"{day}-{month}-{year}", '%d-%m-%Y')
                                    dates.append(date_obj)
                            except Exception:
                                continue

                    for line in text.split('\n'):
                        if self._is_transaction_line(line):
                            transactions.append(line.strip())
                            if len(transactions) >= 40:
                                break
                    if len(transactions) >= 40:
                        break

        except Exception as e:
            logger.error(f"Error extracting transactions from {pdf_path}: {e}")

        transactions = list(set(transactions))

        start_date = None
        end_date = None
        if dates:
            dates = sorted(dates)
            start_date = dates[0].strftime('%Y-%m-%d')
            end_date = dates[-1].strftime('%Y-%m-%d')

        return len(transactions), start_date, end_date


    
    def _is_transaction_line(self, line):
        """Check if a line looks like a transaction"""
        # Various transaction patterns
        patterns = [
            # Line with amount and date
            r'\d+[.,]\d{2}.*\d{1,2}[-/]\d{1,2}[-/]\d{2,4}',
            r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}.*\d+[.,]\d{2}',
            # Line with amount only (but with transaction-like keywords)
            r'\d+[.,]\d{2}.*(debit|credit|withdraw|deposit|transfer|upi|neft|rtgs|imps)',
            # Line with date and description
            r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}.*\w{3,}',
            # Amount with currency symbol
            r'[₹$Rs\.]\s*\d+[.,]\d{2}',
            # Just amount (fallback)
            r'\b\d+[.,]\d{2}\b'
        ]
        
        line_lower = line.lower()
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                # Exclude header/footer lines
                if not any(word in line_lower for word in ['page', 'total', 'balance', 'statement', 'account']):
                    return True
        return False
    
    def _is_transaction_row(self, row_text):
        """Check if a table row looks like a transaction"""
        row_lower = row_text.lower()
        # Look for rows with amounts and transaction indicators
        has_amount = bool(re.search(r'\d+[.,]\d{2}', row_text))
        has_date = bool(re.search(r'\d{1,2}[-/]\d{1,2}[-/]\d{2,4}', row_text))
        has_transaction_keyword = any(word in row_lower for word in 
            ['debit', 'credit', 'withdraw', 'deposit', 'transfer', 'upi', 'neft', 'rtgs', 'imps'])
        
        # Exclude header rows
        is_header = any(word in row_lower for word in ['date', 'description', 'amount', 'balance', 'particulars'])
        
        return (has_amount and (has_date or has_transaction_keyword)) and not is_header
    
    def generate_format_id(self, bank_name, page_count):
        """Generate format ID: e.g. HDF_FMT_3P from canonical bank + page count."""
        canonical = self.canonicalize_bank_name(bank_name)
        bank_code = self.BANK_CODE_MAP.get(canonical, "UNK")
        pages = int(page_count or 0)
        return f"{bank_code}_FMT_{pages}P"

    def validate_single_pdf(
        self,
        pdf_path: Path,
        user_id: str = "SYSTEM",
        goal_id: str = "GENERAL",
        original_filename: Optional[str] = None,
        bank_hint: Optional[str] = None,
    ) -> HygieneCheckResult:
        """Validate a single PDF for hygiene before processing (fast, cached)."""
        import time as _time
        t0 = _time.monotonic()
        pdf_path = Path(pdf_path)
        display_name = (original_filename or pdf_path.name or "statement.pdf").strip()

        cached = get_cached_hygiene(pdf_path)
        if cached is not None:
            # Re-apply display name / ids without re-scanning
            bank = cached.bank_name
            if bank_hint:
                hinted = self.canonicalize_bank_name(bank_hint)
                if hinted != "unknown":
                    bank = hinted
            return HygieneCheckResult(
                is_healthy=cached.is_healthy if bank == cached.bank_name else (len(cached.issues) == 0 and bank != "unknown"),
                file_name=display_name,
                page_count=cached.page_count,
                bank_name=bank,
                format_id=self.generate_format_id(bank, cached.page_count),
                transaction_count=cached.transaction_count,
                start_date=cached.start_date,
                end_date=cached.end_date,
                user_id=user_id,
                goal_id=goal_id,
                issues=[i for i in cached.issues if not (bank != "unknown" and "Bank name not detected" in i)],
                warnings=list(cached.warnings),
            )

        page_count = 0
        bank_name = "unknown"
        transaction_count = 0
        start_date = None
        end_date = None
        header_text = ""

        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                sample_indexes = list(range(min(2, page_count)))
                if page_count > 2:
                    sample_indexes.append(page_count - 1)
                sample_indexes = sorted(set(sample_indexes))

                dates = []
                txn_lines = []
                date_patterns = [
                    r'\b(\d{2})[-/](\d{2})[-/](\d{4})\b',
                    r'\b(\d{2})[-/](\d{2})[-/](\d{2})\b',
                    r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})\b',
                ]

                for i, idx in enumerate(sample_indexes):
                    page = pdf.pages[idx]
                    text = page.extract_text() or ""
                    if not text:
                        continue
                    if i == 0:
                        header_text = text

                    for pattern in date_patterns:
                        for match in re.findall(pattern, text, re.IGNORECASE):
                            try:
                                if len(match) != 3:
                                    continue
                                if match[1].isalpha():
                                    date_obj = datetime.strptime(
                                        f"{match[0]} {match[1]} {match[2]}", "%d %b %Y"
                                    )
                                else:
                                    day, month, year = match
                                    if len(year) == 2:
                                        year = "20" + year
                                    date_obj = datetime.strptime(f"{day}-{month}-{year}", "%d-%m-%Y")
                                dates.append(date_obj)
                            except Exception:
                                continue

                    for line in text.split("\n"):
                        if self._is_transaction_line(line):
                            txn_lines.append(line.strip())
                            if len(txn_lines) >= 30:
                                break
                    if len(txn_lines) >= 30:
                        break

                transaction_count = len(set(txn_lines))
                if dates:
                    dates = sorted(dates)
                    start_date = dates[0].strftime("%Y-%m-%d")
                    end_date = dates[-1].strftime("%Y-%m-%d")
        except Exception as e:
            logger.error(f"Fast hygiene scan failed for {pdf_path}: {e}")
            page_count = self.get_pdf_page_count(pdf_path)

        bank_name = self.detect_bank_name(
            pdf_path,
            original_filename=display_name,
            bank_hint=bank_hint,
            header_text=header_text,
        )
        format_id = self.generate_format_id(bank_name, page_count)

        issues: List[str] = []
        warnings: List[str] = []

        if page_count == 0:
            issues.append("Zero pages detected - possible file corruption")
        if transaction_count == 0:
            issues.append("Zero transactions detected - possible parsing error")
        if bank_name == "unknown":
            issues.append("Bank name not detected - manual review needed")
        if not start_date or not end_date:
            warnings.append("Date range not detected - possible format issue")
        if page_count > 50:
            warnings.append(f"Large file with {page_count} pages - processing may be slow")
        if 0 < transaction_count < 3:
            warnings.append(f"Low transaction count ({transaction_count}) - may be incomplete statement")

        is_healthy = len(issues) == 0
        duration_ms = int((_time.monotonic() - t0) * 1000)

        result = HygieneCheckResult(
            is_healthy=is_healthy,
            file_name=display_name,
            page_count=page_count,
            bank_name=bank_name,
            format_id=format_id,
            transaction_count=transaction_count,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id or "SYSTEM",
            goal_id=goal_id or "GENERAL",
            issues=issues,
            warnings=warnings,
        )
        # Attach duration for audit (not part of dataclass public API)
        try:
            result.check_duration_ms = duration_ms  # type: ignore[attr-defined]
        except Exception:
            pass
        cache_hygiene_result(pdf_path, result)
        return result

    def process_pdf(self, pdf_path, user_id="SYSTEM", goal_id="GENERAL", original_filename=None, bank_hint=None):
        """Process a single PDF and generate hygiene check metrics"""
        result = self.validate_single_pdf(
            Path(pdf_path),
            user_id=user_id,
            goal_id=goal_id,
            original_filename=original_filename,
            bank_hint=bank_hint,
        )
        return {
            "File Name": result.file_name,
            "No of Pages": result.page_count,
            "Bank Name": result.bank_name,
            "Format ID": result.format_id,
            "No of Transactions": result.transaction_count,
            "Start Date": result.start_date or "N/A",
            "End Date": result.end_date or "N/A",
            "User ID": result.user_id,
            "Goal ID": result.goal_id,
        }


    def log_hygiene_check_result(self, result: HygieneCheckResult):
        """Log hygiene check result in the requested format"""
        logger.info("=" * 80)
        logger.info("HYGIENE CHECK REPORT")
        logger.info("=" * 80)
        logger.info(f"File Name          : {result.file_name}")
        logger.info(f"No of Pages        : {result.page_count}")
        logger.info(f"Bank Name          : {result.bank_name}")
        logger.info(f"Format ID          : {result.format_id}")
        logger.info(f"No of Transactions : {result.transaction_count}")
        logger.info(f"Start Date         : {result.start_date}")
        logger.info(f"End Date           : {result.end_date}")
        logger.info(f"User ID            : {result.user_id}")
        logger.info(f"Goal ID            : {result.goal_id}")
        logger.info("=" * 80)
        
        # Validation status
        logger.info("HYGIENE CHECK STATUS:")
        if result.is_healthy:
            logger.info("✅ PDF is HEALTHY - No issues detected")
        else:
            logger.warning("⚠️ PDF has HYGIENE ISSUES - Will proceed with warnings")
        
        # Log issues (now as warnings, not errors)
        if result.issues:
            logger.warning("HYGIENE ISSUES (non-blocking):")
            for issue in result.issues:
                logger.warning(f"  ⚠️  {issue}")
        
        # Log warnings
        if result.warnings:
            logger.warning("ADDITIONAL WARNINGS:")
            for warning in result.warnings:
                logger.warning(f"  ⚠️  {warning}")
        
        logger.info("→ Proceeding with 3-level fallback parsing...")
        
        logger.info("")
        
        # Store in audit system once per job (bank parsers may re-call this)
        if self.audit_service and self.job_id:
            if self.job_id in _HYGIENE_LOGGED_JOBS:
                return
            try:
                self.audit_service.create_hygiene_report(
                    job_id=self.job_id,
                    format_id=result.format_id,
                    page_count=result.page_count,
                    transaction_count=result.transaction_count,
                    is_healthy=result.is_healthy,
                    warnings=result.warnings,
                    issues=result.issues,
                    start_date=result.start_date,
                    end_date=result.end_date,
                    check_duration_ms=getattr(result, "check_duration_ms", None),
                    file_name=result.file_name,
                    bank_name=result.bank_name,
                    user_id=result.user_id,
                    goal_id=result.goal_id,
                )

                self.audit_service.create_job_event(
                    job_id=self.job_id,
                    event_type="HYGIENE_CHECK",
                    event_name="HYGIENE_CHECK_COMPLETED",
                    event_category="VALIDATION",
                    description=f"Hygiene check completed: {'HEALTHY' if result.is_healthy else 'ISSUES_DETECTED'}",
                    status='SUCCESS' if result.is_healthy else 'WARNING',
                    metadata={
                        "is_healthy": result.is_healthy,
                        "page_count": result.page_count,
                        "transaction_count": result.transaction_count,
                        "bank_name": result.bank_name,
                        "format_id": result.format_id,
                        "issues_count": len(result.issues),
                        "warnings_count": len(result.warnings)
                    }
                )
                _HYGIENE_LOGGED_JOBS.add(self.job_id)
                if len(_HYGIENE_LOGGED_JOBS) > 128:
                    _HYGIENE_LOGGED_JOBS.clear()
                logger.info("Hygiene check stored in audit system")
            except Exception as e:
                logger.error(f"Failed to store hygiene check in audit system: {e}")

    
    def log_hygiene_check(self, metrics):
        """Log hygiene check metrics in a structured format"""
        logger.info("=" * 80)
        logger.info("HYGIENE CHECK REPORT")
        logger.info("=" * 80)
        logger.info(f"File Name          : {metrics['File Name']}")
        logger.info(f"No of Pages        : {metrics['No of Pages']}")
        logger.info(f"Bank Name          : {metrics['Bank Name']}")
        logger.info(f"Format ID          : {metrics['Format ID']}")
        logger.info(f"No of Transactions : {metrics['No of Transactions']}")
        logger.info(f"Start Date         : {metrics['Start Date']}")
        logger.info(f"End Date           : {metrics['End Date']}")
        logger.info(f"User ID            : {metrics['User ID']}")
        logger.info(f"Goal ID            : {metrics['Goal ID']}")
        logger.info("=" * 80)
        
        # Validation checks
        logger.info("VALIDATION STATUS:")
        if metrics['No of Pages'] == 0:
            logger.warning("WARNING: Zero pages detected - possible file corruption")
        if metrics['No of Transactions'] == 0:
            logger.warning("WARNING: Zero transactions detected - possible parsing error")
        if metrics['Bank Name'] == "unknown":
            logger.warning("WARNING: Bank name not detected - manual review needed")
        if metrics['Start Date'] == "N/A" or metrics['End Date'] == "N/A":
            logger.warning("WARNING: Date range not detected - possible format issue")
        logger.info("")
    
    def run_hygiene_check(self, user_id="SYSTEM", goal_id="GENERAL"):
        """Run hygiene check on all PDFs in directory (including subdirectories)"""
        pdf_files = list(self.pdf_directory.rglob("*.pdf"))
        
        if not pdf_files:
            logger.warning(f"No PDF files found in {self.pdf_directory}")
            return
        
        logger.info(f"Starting Hygiene Check for {len(pdf_files)} PDF files...")
        logger.info("")
        
        results = []
        for pdf_path in pdf_files:
            logger.info(f"Processing: {pdf_path.name}")
            metrics = self.process_pdf(pdf_path, user_id, goal_id)
            self.log_hygiene_check(metrics)
            results.append(metrics)
        
        # Summary
        logger.info("")
        logger.info("=" * 80)
        logger.info("HYGIENE CHECK SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Files Processed: {len(results)}")
        
        # Bank distribution
        bank_counts = {}
        for r in results:
            bank = r['Bank Name']
            bank_counts[bank] = bank_counts.get(bank, 0) + 1
        
        logger.info("Bank Distribution:")
        for bank, count in bank_counts.items():
            logger.info(f"  {bank}: {count}")
        
        # Issues summary
        zero_pages = sum(1 for r in results if r['No of Pages'] == 0)
        zero_txns = sum(1 for r in results if r['No of Transactions'] == 0)
        unknown_banks = sum(1 for r in results if r['Bank Name'] == "unknown")
        missing_dates = sum(1 for r in results if r['Start Date'] == "N/A" or r['End Date'] == "N/A")
        
        # Calculate pass/fail
        passed_files = sum(1 for r in results if 
                          r['No of Pages'] > 0 and 
                          r['No of Transactions'] > 0 and 
                          r['Bank Name'] != "unknown" and 
                          r['Start Date'] != "N/A" and 
                          r['End Date'] != "N/A")
        failed_files = len(results) - passed_files
        
        logger.info("")
        logger.info("ISSUES SUMMARY:")
        if zero_pages > 0:
            logger.warning(f"  Files with zero pages: {zero_pages}")
        if zero_txns > 0:
            logger.warning(f"  Files with zero transactions: {zero_txns}")
        if unknown_banks > 0:
            logger.warning(f"  Files with unknown bank: {unknown_banks}")
        if missing_dates > 0:
            logger.warning(f"  Files with missing dates: {missing_dates}")
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("HYGIENE CHECK CONCLUSION")
        logger.info("=" * 80)
        logger.info(f"Total Files Processed: {len(results)}")
        logger.info(f"Files PASSED: {passed_files} ({passed_files/len(results)*100:.1f}%)")
        logger.info(f"Files FAILED: {failed_files} ({failed_files/len(results)*100:.1f}%)")
        logger.info("")
        
        if failed_files == 0:
            logger.info("RESULT: All files passed hygiene checks - No issues detected")
        else:
            logger.info("RESULT: Some files failed hygiene checks - Review issues above")
            logger.info("")
            logger.info("FAILURE CRITERIA:")
            logger.info("  - Zero pages: Possible file corruption")
            logger.info("  - Zero transactions: Possible parsing error or empty statement")
            logger.info("  - Unknown bank: Manual review needed for bank identification")
            logger.info("  - Missing dates: Date format not recognized")
        
        logger.info("=" * 80)
        
        return results

if __name__ == "__main__":
    # Configuration - ask user for folder path
    print("=" * 80)
    print("BANK STATEMENT HYGIENE CHECK")
    print("=" * 80)
    
    pdf_directory = input("Enter the folder path containing PDF files: ").strip()
    
    # Remove quotes if user added them
    if pdf_directory.startswith('"') and pdf_directory.endswith('"'):
        pdf_directory = pdf_directory[1:-1]
    elif pdf_directory.startswith("'") and pdf_directory.endswith("'"):
        pdf_directory = pdf_directory[1:-1]
    
    # Validate path exists
    if not Path(pdf_directory).exists():
        print(f"ERROR: Path does not exist: {pdf_directory}")
        exit(1)
    
    # Optional: ask for user ID and goal ID
    user_id = input("Enter User ID (default: SYSTEM): ").strip() or "SYSTEM"
    goal_id = input("Enter Goal ID (default: GENERAL): ").strip() or "GENERAL"
    
    print(f"\nProcessing PDFs from: {pdf_directory}")
    print(f"User ID: {user_id}, Goal ID: {goal_id}")
    print("=" * 80)
    
    # Run hygiene check
    checker = HygieneCheck(pdf_directory)
    results = checker.run_hygiene_check(user_id, goal_id)
