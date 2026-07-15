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
    BANK_CODE_MAP = {
        'hdfc': 'HDF',
        'hdfc bank': 'HDF',
        'axis': 'AXI',
        'axis bank': 'AXI',
        'icici': 'ICI',
        'icici bank': 'ICI',
        'bank of india': 'BOI',
        'bankofindia': 'BOI',
        'boi': 'BOI',
        'bkid': 'BOI',
        'indian bank': 'IDB',
        'indian': 'IDB',
        'idib': 'IDB',
        'sbi': 'SBI',
        'state bank': 'SBI',
        'state bank of india': 'SBI',
        'kotak': 'KOT',
        'kotak bank': 'KOT',
        'idfc': 'IDF',
        'idfc bank': 'IDF',
        'idfc first': 'IDF',
        'idfc first bank': 'IDF',
        'canara': 'CAN',
        'canara bank': 'CAN',
        'union': 'UNI',
        'union bank': 'UNI',
        'union bank of india': 'UNI',
        'bank of baroda': 'BOB',
        'bankofbaroda': 'BOB',
        'bob': 'BOB',
        'karnataka bank': 'KAR',
        'karnataka': 'KAR',
        'paytm': 'PAY',
        'paytm bank': 'PAY',
        'paytm payments bank': 'PAY',
        'unknown': 'UNK',
        'unknown bank': 'UNK',
    }

    BANK_TEXT_PATTERNS = [
        ('bank of baroda', [(r'\bbank of baroda\b', 8), (r'\bbob\b', 4)]),
        ('union', [(r'\bunion bank of india\b', 8), (r'\bunion bank\b', 6), (r'\bunion\b', 3)]),
        ('hdfc', [(r'\bhdfc bank limited\b', 9), (r'\bhdfc bank\b', 8), (r'\bhdfc\b', 5)]),
        ('axis', [(r'\baxis bank limited\b', 9), (r'\baxis bank\b', 8), (r'\baxis\b', 5)]),
        ('icici', [(r'\bicici bank limited\b', 9), (r'\bicici bank\b', 8), (r'\bicici\b', 5)]),
        ('bank of india', [(r'\bbank of india\b', 9), (r'\bboi\b', 6), (r'\bbkid[0-9a-z]{7}\b', 8)]),
        ('indian bank', [(r'\bindian bank\b', 9), (r'\bidib0[0-9a-z]{6}\b', 8), (r'\baccount statement\b', 3)]),
        ('sbi', [(r'\bstate bank of india\b', 9), (r'\bsbi\b', 6)]),
        ('kotak', [(r'\bkotak mahindra bank\b', 9), (r'\bkotak bank\b', 8), (r'\bkotak\b', 5)]),
        ('idfc', [(r'\bidfc first bank\b', 9), (r'\bidfc first\b', 8), (r'\bidfc\b', 5)]),
        ('canara', [(r'\bcanara bank\b', 9), (r'\bcanara\b', 5)]),
        ('karnataka bank', [(r'\bkarnataka bank\b', 9), (r'\bkarnataka\b', 5)]),
        ('paytm', [(r'\bpaytm payments bank\b', 9), (r'\bpaytm bank\b', 8), (r'\bpaytm\b', 5)]),
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

    def _score_bank_candidates(self, text: str) -> Dict[str, int]:
        """Score likely bank matches using explicit bank phrases only."""
        scores: Dict[str, int] = {}
        if not text:
            return scores

        for bank_name, patterns in self.BANK_TEXT_PATTERNS:
            score = 0
            for pattern, weight in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    score += weight
            if score > 0:
                scores[bank_name] = score

        return scores
    
    def get_pdf_page_count(self, pdf_path):
        """Extract number of pages from PDF"""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PdfReader(file)
                return len(pdf_reader.pages)
        except Exception as e:
            logger.error(f"Error reading page count for {pdf_path}: {e}")
            return 0
    
    def detect_bank_name(self, pdf_path):
        """Detect bank name using strong filename hints first, then explicit header phrases."""
        filename = pdf_path.name.lower()

        # If the source filename already contains a clear bank hint, trust it.
        filename_scores = self._score_bank_candidates(filename)
        if filename_scores:
            return max(filename_scores.items(), key=lambda item: item[1])[0]

        # Fallback to the PDF header text. Only use explicit bank phrases,
        # not numeric substrings, so we do not mislabel one bank as another.
        try:
            with pdfplumber.open(pdf_path) as pdf:
                first_page = pdf.pages[0]
                text = first_page.extract_text() or ""
                text = text.lower()

                text_scores = self._score_bank_candidates(text)
                if text_scores:
                    return max(text_scores.items(), key=lambda item: item[1])[0]
        except Exception as e:
            logger.error(f"Error reading PDF content for bank detection: {e}")
        
        return "unknown"
    
    def extract_transactions_and_dates(self, pdf_path):
        """Extract transactions and date range from PDF"""
        transactions = []
        dates = []
        
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        # Try to extract dates (common Indian bank statement date formats)
                        # DD-MM-YYYY, DD/MM/YYYY, DD/MM/YY, etc.
                        date_patterns = [
                            r'\b(\d{2})[-/](\d{2})[-/](\d{4})\b',
                            r'\b(\d{2})[-/](\d{2})[-/](\d{2})\b',
                            r'\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{4})\b',
                            r'\b(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})\b'
                        ]
                        
                        for pattern in date_patterns:
                            matches = re.findall(pattern, text, re.IGNORECASE)
                            for match in matches:
                                try:
                                    if len(match) == 3:
                                        if match[1].isalpha():
                                            # Format: DD Mon YYYY
                                            date_str = f"{match[0]} {match[1]} {match[2]}"
                                            date_obj = datetime.strptime(date_str, '%d %b %Y')
                                        else:
                                            # Format: DD-MM-YYYY or DD/MM/YYYY
                                            day, month, year = match
                                            if len(year) == 2:
                                                year = '20' + year
                                            date_obj = datetime.strptime(f"{day}-{month}-{year}", '%d-%m-%Y')
                                        dates.append(date_obj)
                                except:
                                    continue
                        
                        # Try to extract tables first (more reliable for bank statements)
                        tables = page.extract_tables()
                        if tables:
                            for table in tables:
                                for row in table:
                                    if row:
                                        row_text = ' '.join([str(cell) if cell else '' for cell in row])
                                        # Count rows that look like transactions
                                        if self._is_transaction_row(row_text):
                                            transactions.append(row_text)
                        
                        # Fallback: Count transaction lines from text
                        lines = text.split('\n')
                        for line in lines:
                            # More flexible transaction patterns
                            if self._is_transaction_line(line):
                                transactions.append(line.strip())
        
        except Exception as e:
            logger.error(f"Error extracting transactions from {pdf_path}: {e}")
        
        # Remove duplicate transactions
        transactions = list(set(transactions))
        
        # Get date range
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
        """Generate a format ID based on bank and page count"""
        normalized_bank = (bank_name or "unknown").strip().lower()
        bank_code = self.BANK_CODE_MAP.get(normalized_bank, normalized_bank[:3].upper() if normalized_bank else "UNK")
        return f"{bank_code}_FMT_{page_count}P"
    
    def validate_single_pdf(self, pdf_path: Path, user_id: str = "SYSTEM", goal_id: str = "GENERAL") -> HygieneCheckResult:
        """Validate a single PDF for hygiene before processing"""
        filename = pdf_path.name
        page_count = self.get_pdf_page_count(pdf_path)
        bank_name = self.detect_bank_name(pdf_path)
        transaction_count, start_date, end_date = self.extract_transactions_and_dates(pdf_path)
        format_id = self.generate_format_id(bank_name, page_count)
        
        # Validation checks
        issues = []
        warnings = []
        
        # Critical issues that make PDF unhealthy
        if page_count == 0:
            issues.append("Zero pages detected - possible file corruption")
        
        if transaction_count == 0:
            issues.append("Zero transactions detected - possible parsing error")
        
        if bank_name == "unknown":
            issues.append("Bank name not detected - manual review needed")
        
        # Warnings that don't block processing but should be noted
        if start_date == "N/A" or end_date == "N/A":
            warnings.append("Date range not detected - possible format issue")
        
        if page_count > 50:
            warnings.append(f"Large file with {page_count} pages - processing may be slow")
        
        if transaction_count < 3:
            warnings.append(f"Low transaction count ({transaction_count}) - may be incomplete statement")
        
        # Determine if PDF is healthy
        is_healthy = len(issues) == 0
        
        return HygieneCheckResult(
            is_healthy=is_healthy,
            file_name=filename,
            page_count=page_count,
            bank_name=bank_name,
            format_id=format_id,
            transaction_count=transaction_count,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
            goal_id=goal_id,
            issues=issues,
            warnings=warnings
        )
    
    def process_pdf(self, pdf_path, user_id="SYSTEM", goal_id="GENERAL"):
        """Process a single PDF and
         generate hygiene check metrics"""
        filename = pdf_path.name
        page_count = self.get_pdf_page_count(pdf_path)
        bank_name = self.detect_bank_name(pdf_path)
        transaction_count, start_date, end_date = self.extract_transactions_and_dates(pdf_path)
        format_id = self.generate_format_id(bank_name, page_count)
        
        hygiene_metrics = {
            "File Name": filename,
            "No of Pages": page_count,
            "Bank Name": bank_name,
            "Format ID": format_id,
            "No of Transactions": transaction_count,
            "Start Date": start_date or "N/A",
            "End Date": end_date or "N/A",
            "User ID": user_id,
            "Goal ID": goal_id
        }
        
        return hygiene_metrics
    
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
        
        # Store in audit system if audit_service is available
        if self.audit_service and self.job_id:
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
                    file_name=result.file_name,
                    bank_name=result.bank_name,
                    user_id=result.user_id,
                    goal_id=result.goal_id,
                )
                
                # Create job event for hygiene check
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
