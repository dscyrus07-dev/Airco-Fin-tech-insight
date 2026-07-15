"""Airco Insights - Indian Bank Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig
from .aggregation_engine import IndianBankAggregationEngine
from .ai_fallback import IndianBankAIFallback
from .parser import IndianBankParser
from .reconciliation import IndianBankReconciliation
from .recurring_engine import IndianBankRecurringEngine
from .rule_engine import IndianBankRuleEngine
from .structure_validator import INDIAN_BANK_CONFIG, IndianBankStructureValidator
from .transaction_validator import IndianBankTransactionValidator

logger = logging.getLogger(__name__)

CONFIG = INDIAN_BANK_CONFIG


class IndianBankProcessorError(Exception):
    pass


IndianBankProcessingResult = BasePipelineResult


class IndianBankProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "INDIAN_BANK"

    def __init__(
        self,
        strict_mode: bool = True,
        enable_ai: bool = False,
        api_key: Optional[str] = None,
        audit_service=None,
        job_id: Optional[str] = None,
    ):
        super().__init__(
            strict_mode=strict_mode,
            enable_ai=enable_ai,
            api_key=api_key,
            audit_service=audit_service,
            job_id=job_id,
        )
        self.pdf_validator = PDFIntegrityValidator()
        self.structure_validator = IndianBankStructureValidator()
        self.parser = IndianBankParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = IndianBankTransactionValidator(strict_mode=False)
        self.reconciliation = IndianBankReconciliation(strict_mode=False)
        self.rule_engine = IndianBankRuleEngine()
        self.ai_fallback = IndianBankAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = IndianBankRecurringEngine()
        self.aggregation_engine = IndianBankAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> IndianBankProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
