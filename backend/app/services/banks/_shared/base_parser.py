"""
Airco Insights — Base Bank Parser (Unified Interface)
=====================================================
Implements 3-level parsing strategy for all bank parsers:
1. Hardcoded coordinates (fastest, most accurate)
2. Dynamic column detection (adaptive fallback)
3. Unknown format queue (manual review)

All bank parsers inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import logging

from .hygiene_check import HygieneCheck, HygieneCheckResult

logger = logging.getLogger(__name__)


@dataclass
class ParseAttempt:
    """Record of a parsing attempt."""
    parser_name: str
    transactions_count: int
    confidence: float
    method: str
    error: Optional[str] = None


@dataclass
class BankParserResult:
    """Result from bank parser with full attempt history."""
    transactions: List[Dict[str, Any]] = field(default_factory=list)
    attempts: List[ParseAttempt] = field(default_factory=list)
    final_method: Optional[str] = None
    requires_update: bool = False
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "transactions": self.transactions,
            "total_count": len(self.transactions),
            "final_method": self.final_method,
            "requires_update": self.requires_update,
            "attempts": [a.__dict__ for a in self.attempts],
            "error": self.error_message,
            "error_code": self.error_code,
            "warnings": self.warnings,
        }


class BaseBankParser(ABC):
    """
    Unified interface for all bank parsers.
    Implements the 3-level fallback strategy.
    """
    
    BANK_NAME: str = ""
    SUPPORTED_FORMATS: List[str] = field(default_factory=lambda: ["v1", "v2"])
    
    def __init__(self, audit_service=None, job_id=None):
        self.result = BankParserResult()
        self.logger = logging.getLogger(f"{__name__}.{self.BANK_NAME}")
        self.audit_service = audit_service
        self.job_id = job_id
        # Initialize hygiene checker for single PDF validation
        self.hygiene_checker = HygieneCheck(pdf_directory=Path.cwd(), audit_service=audit_service, job_id=job_id)  # Will be overridden per file
    
    def parse(self, file_path: str) -> BankParserResult:
        """
        3-level parsing strategy with hygiene check:
        1. PDF hygiene validation (pre-processing gate)
        2. Hardcoded coordinates (fastest, most accurate)
        3. Dynamic column detection (adaptive)
        4. Unknown format (requires manual review)
        """
        self.logger.info(f"Starting 3-level parse for {self.BANK_NAME}: {file_path}")
        
        # HYGIENE CHECK: Validate PDF before processing (non-blocking)
        hygiene_result = self._validate_pdf_hygiene(file_path)
        if not hygiene_result.is_healthy:
            self.logger.warning(f"⚠️ PDF hygiene check warnings: {', '.join(hygiene_result.issues)}")
            self.logger.warning("Proceeding with parsing despite hygiene warnings...")
            # Add hygiene issues to warnings for tracking
            self.result.warnings = hygiene_result.issues
        else:
            self.logger.info(f"✅ PDF hygiene check passed: {hygiene_result.transaction_count} transactions detected")
        
        # Log any warnings from hygiene check
        if hygiene_result.warnings:
            for warning in hygiene_result.warnings:
                self.logger.warning(f"Hygiene Warning: {warning}")
        
        # LEVEL 1: Try hardcoded parser
        level1_result = self._try_hardcoded(file_path)
        if level1_result and getattr(level1_result, 'total_count', 0) > 0:
            self.result.transactions = getattr(level1_result, 'transactions', [])
            self.result.final_method = "hardcoded"
            self.result.attempts.append(ParseAttempt(
                parser_name=f"{self.BANK_NAME}Hardcoded",
                transactions_count=level1_result.total_count,
                confidence=95.0,
                method="hardcoded"
            ))
            self._record_metrics("hardcoded", True, level1_result.total_count)
            self.logger.info(f"Level 1 (hardcoded) succeeded: {level1_result.total_count} transactions")
            return self.result
        
        self.result.attempts.append(ParseAttempt(
            parser_name=f"{self.BANK_NAME}Hardcoded",
            transactions_count=0,
            confidence=0.0,
            method="hardcoded",
            error="No transactions extracted" if not level1_result else "Hardcoded parser returned 0 transactions"
        ))
        self._record_metrics("hardcoded", False, 0)
        self.logger.warning(f"Level 1 (hardcoded) failed for {self.BANK_NAME}")
        
        # LEVEL 2: Try dynamic column detection
        try:
            level2_result = self._try_dynamic(file_path)
            if level2_result and getattr(level2_result, 'total_count', 0) > 0:
                self.result.transactions = getattr(level2_result, 'transactions', [])
                self.result.final_method = "dynamic"
                self.result.attempts.append(ParseAttempt(
                    parser_name=f"{self.BANK_NAME}Dynamic",
                    transactions_count=level2_result.total_count,
                    confidence=85.0,
                    method="dynamic"
                ))
                self._record_metrics("dynamic", True, level2_result.total_count)
                self._log_format_change(file_path, level2_result)
                self.logger.info(f"Level 2 (dynamic) succeeded: {level2_result.total_count} transactions")
                return self.result
        except Exception as e:
            self.logger.warning(f"Level 2 (dynamic) failed: {str(e)}")
        
        self.result.attempts.append(ParseAttempt(
            parser_name=f"{self.BANK_NAME}Dynamic",
            transactions_count=0,
            confidence=0.0,
            method="dynamic",
            error="Dynamic detection failed"
        ))
        self._record_metrics("dynamic", False, 0)
        
        # LEVEL 3: Unknown format - log for review
        self.result.final_method = "unsupported"
        self.result.requires_update = True
        self.result.error_message = f"Unable to parse {self.BANK_NAME} statement. Format not recognized."
        self.result.error_code = "UNSUPPORTED_FORMAT"
        self._queue_for_manual_review(file_path)
        self._record_metrics("unsupported", False, 0)
        self.logger.error(f"Level 3: {self.BANK_NAME} statement format not supported")
        
        return self.result
    
    def _try_hardcoded(self, file_path: str):
        """
        Default hardcoded parser adapter.
        Delegates to a legacy `_parse_existing_hardcoded()` method when present.
        """
        legacy_parser = getattr(self, "_parse_existing_hardcoded", None)
        if callable(legacy_parser):
            return legacy_parser(file_path)
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement `_try_hardcoded()` or `_parse_existing_hardcoded()`"
        )
    
    def _try_dynamic(self, file_path: str):
        """
        Shared dynamic column detection.
        Returns DynamicParseResult or None if failed.
        """
        from .dynamic_column_detector import DynamicColumnDetector, DynamicParseResult
        
        detector = DynamicColumnDetector()
        result = detector.parse(file_path, bank_hint=self.BANK_NAME)
        
        if result and result.transactions:
            # Convert DynamicParseResult to bank-specific format
            return DynamicParseResult(
                transactions=result.transactions,
                total_count=len(result.transactions),
                headers_detected=result.headers_detected,
                parse_method="dynamic"
            )
        return None
    
    def _log_format_change(self, file_path: str, result):
        """
        Log when dynamic parser succeeds but hardcoded fails.
        This indicates bank changed layout.
        """
        self.logger.warning(
            f"Format change detected for {self.BANK_NAME}. "
            f"Hardcoded failed, dynamic succeeded with {result.total_count} transactions. "
            f"Consider updating hardcoded coordinates."
        )
        self._store_format_metrics(file_path, result)
    
    def _queue_for_manual_review(self, file_path: str):
        """Add to unsupported format queue for manual review."""
        try:
            from .unsupported_format_queue import UnsupportedFormatQueue
            
            queue = UnsupportedFormatQueue()
            queue.add({
                "bank": self.BANK_NAME,
                "file": file_path,
                "timestamp": datetime.now().isoformat(),
                "attempts": [a.__dict__ for a in self.result.attempts]
            })
            
            # Store in audit system if available
            if self.audit_service and self.job_id:
                try:
                    self.audit_service.create_unsupported_format_queue(
                        job_id=self.job_id,
                        bank_name=self.BANK_NAME,
                        file_path=file_path,
                        attempts=[a.__dict__ for a in self.result.attempts],
                        error_message=self.result.error_message,
                        error_code=self.result.error_code
                    )
                    
                    # Create job event for unsupported format
                    self.audit_service.create_job_event(
                        job_id=self.job_id,
                        event_type="UNSUPPORTED_FORMAT",
                        event_name="UNSUPPORTED_FORMAT_DETECTED",
                        event_category="PROCESSING",
                        description=f"Unsupported format detected for {self.BANK_NAME}: queued for manual review",
                        status='FAILED',
                        metadata={
                            "bank_name": self.BANK_NAME,
                            "file_path": file_path,
                            "error_code": self.result.error_code,
                            "attempts_count": len(self.result.attempts)
                        }
                    )
                except Exception as e:
                    self.logger.error(f"Failed to store unsupported format in audit system: {e}")
        except Exception as e:
            self.logger.error(f"Failed to queue for manual review: {e}")
    
    def _store_format_metrics(self, file_path: str, result):
        """Store metrics for format learning."""
        try:
            from .parser_metrics import ParserMetrics
            
            metrics = ParserMetrics()
            metrics.record_format_change(
                bank=self.BANK_NAME,
                file_path=file_path,
                dynamic_success=True,
                transaction_count=result.total_count
            )
        except Exception as e:
            self.logger.error(f"Failed to store format metrics: {e}")
    
    def _validate_pdf_hygiene(self, file_path: str, user_id: str = "SYSTEM", goal_id: str = "GENERAL") -> HygieneCheckResult:
        """Validate PDF hygiene before processing (uses cache when already scanned)."""
        pdf_path = Path(file_path)

        temp_checker = HygieneCheck(
            pdf_directory=pdf_path.parent,
            audit_service=self.audit_service,
            job_id=self.job_id,
        )

        bank_hint = getattr(self, "BANK_NAME", None) or getattr(self, "bank_name", None)
        result = temp_checker.validate_single_pdf(
            pdf_path,
            user_id=user_id,
            goal_id=goal_id,
            bank_hint=bank_hint,
        )
        temp_checker.log_hygiene_check_result(result)


        # Publish live progress for UI (non-fatal)
        try:
            from ...job_progress import hygiene_result_to_progress, publish_job_progress_sync
            if self.job_id:
                publish_job_progress_sync(
                    self.job_id,
                    stage="hygiene_complete",
                    message=(
                        "Hygiene check passed"
                        if result.is_healthy
                        else "Hygiene check completed with warnings"
                    ),
                    hygiene=hygiene_result_to_progress(result),
                )
        except Exception:
            pass
        
        return result

    
    def _record_metrics(self, method: str, success: bool, transaction_count: int):
        """Record parsing metrics."""
        try:
            from .parser_metrics import ParserMetrics
            
            metrics = ParserMetrics()
            metrics.record_attempt(
                bank=self.BANK_NAME,
                method=method,
                success=success,
                transaction_count=transaction_count
            )
            
            # Store in audit system if available
            if self.audit_service and self.job_id:
                try:
                    self.audit_service.create_parser_metric(
                        job_id=self.job_id,
                        parser_type=method,
                        parser_name=f"{self.BANK_NAME}_{method}",
                        bank_name=self.BANK_NAME,
                        execution_time_ms=0,
                        transactions_extracted=transaction_count,
                        confidence_score=95.0 if success else 0.0,
                        status='SUCCESS' if success else 'FAILED',
                    )
                    
                    # Create job event for parser attempt
                    self.audit_service.create_job_event(
                        job_id=self.job_id,
                        event_type="PARSER",
                        event_name=f"PARSER_{method.upper()}_{'SUCCESS' if success else 'FAILED'}",
                        event_category="PROCESSING",
                        description=f"Parser {method} {'succeeded' if success else 'failed'}: {transaction_count} transactions",
                        status='SUCCESS' if success else 'FAILED',
                        metadata={
                            "parser_type": self.BANK_NAME,
                            "method": method,
                            "transaction_count": transaction_count,
                            "confidence": 95.0 if success else 0.0
                        }
                    )
                except Exception as e:
                    self.logger.error(f"Failed to store parser metrics in audit system: {e}")
        except Exception as e:
            self.logger.error(f"Failed to record metrics: {e}")
    
    def parse_date(self, date_str: str) -> Optional[str]:
        """Best-effort default date parser. Returns ISO format YYYY-MM-DD."""
        if not date_str:
            return None
        text = str(date_str).strip()
        if not text:
            return None

        normalized = text.replace(".", "/").replace("-", "/")
        for fmt in ("%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
            try:
                return datetime.strptime(normalized, fmt).date().isoformat()
            except ValueError:
                continue
        return None
    
    def parse_amount(self, amount_str: str) -> Optional[float]:
        """Best-effort default amount parser. Returns float."""
        if amount_str is None:
            return None

        if isinstance(amount_str, (int, float)):
            return float(amount_str)

        text = str(amount_str).strip()
        if not text:
            return None

        negative = False
        upper_text = text.upper()
        if upper_text.endswith("DR"):
            negative = True
            text = text[:-2].strip()
        elif upper_text.endswith("CR"):
            text = text[:-2].strip()

        text = text.replace(",", "").replace("₹", "").replace(" ", "")
        if text.startswith("(") and text.endswith(")"):
            negative = True
            text = text[1:-1]

        try:
            value = float(text)
            return -value if negative else value
        except ValueError:
            return None
