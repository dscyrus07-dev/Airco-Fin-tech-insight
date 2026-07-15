"""
Airco Insights — PDF Integrity Validator
=========================================
Validates PDF file integrity before processing.
Checks file structure, encryption, corruption, and extractability.

Validation Steps:
1. File exists and readable
2. Valid PDF header
3. Not encrypted/password protected
4. Text extractable (not scanned)
5. Minimum text content present
6. No corruption markers

Design: Fail fast on any integrity issue.
"""

import logging
import os
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class PDFIntegrityError(Exception):
    """Base exception for PDF integrity failures."""
    def __init__(self, message: str, error_code: str, details: dict = None):
        self.error_code = error_code
        self.details = details or {}
        super().__init__(message)


@dataclass
class PDFIntegrityResult:
    """Result of PDF integrity validation."""
    is_valid: bool
    total_pages: int
    text_content: str
    first_page_text: str
    text_length: int
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "total_pages": self.total_pages,
            "text_length": self.text_length,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


class PDFIntegrityValidator:
    """
    Validates PDF file integrity before any bank-specific processing.
    """
    
    # Minimum text length to consider PDF valid (catches near-empty PDFs)
    MIN_TEXT_LENGTH = 100
    
    # PDF header magic bytes
    PDF_MAGIC = b'%PDF-'
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def validate(self, file_path: str) -> PDFIntegrityResult:
        """
        Validate PDF file integrity.
        
        Args:
            file_path: Absolute path to PDF file
            
        Returns:
            PDFIntegrityResult with validation status and extracted text
            
        Raises:
            PDFIntegrityError: If PDF fails any integrity check
        """
        self.logger.info("Validating PDF integrity: %s", file_path)
        
        # Step 1: File existence
        if not os.path.isfile(file_path):
            raise PDFIntegrityError(
                f"File not found: {file_path}",
                error_code="FILE_NOT_FOUND",
                details={"path": file_path}
            )
        
        # Step 2: File size check
        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise PDFIntegrityError(
                "PDF file is empty (0 bytes)",
                error_code="EMPTY_FILE",
                details={"size": 0}
            )
        
        if file_size > 50 * 1024 * 1024:  # 50MB limit
            raise PDFIntegrityError(
                "PDF file exceeds maximum size limit (50MB)",
                error_code="FILE_TOO_LARGE",
                details={"size": file_size, "max_size": 50 * 1024 * 1024}
            )
        
        # Step 3: PDF magic bytes check
        with open(file_path, 'rb') as f:
            header = f.read(8)
            if not header.startswith(self.PDF_MAGIC):
                raise PDFIntegrityError(
                    "File is not a valid PDF (invalid header)",
                    error_code="INVALID_PDF_HEADER",
                    details={"header": header[:20].hex()}
                )
        
        # Step 4: Extract text using pdfplumber
        try:
            import pdfplumber
        except ImportError:
            raise PDFIntegrityError(
                "pdfplumber library not installed",
                error_code="MISSING_DEPENDENCY",
                details={"dependency": "pdfplumber"}
            )
        
        text_pages = []
        first_page_text = ""
        total_pages = 0
        
        try:
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                
                if total_pages == 0:
                    raise PDFIntegrityError(
                        "PDF has no pages",
                        error_code="NO_PAGES",
                        details={"page_count": 0}
                    )
                
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    text_pages.append(page_text)
                    
                    if i == 0:
                        first_page_text = page_text
                        
        except pdfplumber.pdfminer.pdfparser.PDFSyntaxError as e:
            raise PDFIntegrityError(
                f"PDF is corrupted: {str(e)}",
                error_code="CORRUPTED_PDF",
                details={"error": str(e)}
            )
        except Exception as e:
            if "password" in str(e).lower() or "encrypted" in str(e).lower():
                raise PDFIntegrityError(
                    "PDF is password protected/encrypted",
                    error_code="ENCRYPTED_PDF",
                    details={"error": str(e)}
                )
            raise PDFIntegrityError(
                f"Failed to read PDF: {str(e)}",
                error_code="READ_ERROR",
                details={"error": str(e)}
            )
        
        # Combine all text
        full_text = "\n".join(text_pages)
        text_length = len(full_text.strip())
        
        # Step 5: Minimum text content check
        if text_length < self.MIN_TEXT_LENGTH:
            has_extractable_words = False
            try:
                with pdfplumber.open(file_path) as pdf:
                    pages_to_check = min(3, len(pdf.pages))
                    for page in pdf.pages[:pages_to_check]:
                        if page.extract_words():
                            has_extractable_words = True
                            break
            except Exception as word_check_error:
                self.logger.debug(
                    "Word-based extractability check failed for %s: %s",
                    file_path,
                    word_check_error,
                )

            if not has_extractable_words:
                raise PDFIntegrityError(
                    f"PDF has insufficient text content ({text_length} chars). "
                    "This may be a scanned document or image-based PDF.",
                    error_code="INSUFFICIENT_TEXT",
                    details={"text_length": text_length, "min_required": self.MIN_TEXT_LENGTH}
                )

            self.logger.warning(
                "PDF text extraction is below threshold (%d < %d), but words are extractable; allowing processing to continue.",
                text_length,
                self.MIN_TEXT_LENGTH,
            )
        
        self.logger.info(
            "PDF integrity validated: pages=%d, text_length=%d",
            total_pages, text_length
        )
        
        return PDFIntegrityResult(
            is_valid=True,
            total_pages=total_pages,
            text_content=full_text,
            first_page_text=first_page_text,
            text_length=text_length,
        )
