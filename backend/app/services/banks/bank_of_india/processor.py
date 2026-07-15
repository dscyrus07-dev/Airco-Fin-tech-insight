"""Airco Insights - Bank of India Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig
from .aggregation_engine import BankOfIndiaAggregationEngine
from .ai_fallback import BankOfIndiaAIFallback
from .parser import BankOfIndiaParser
from .reconciliation import BankOfIndiaReconciliation
from .recurring_engine import BankOfIndiaRecurringEngine
from .rule_engine import BankOfIndiaRuleEngine
from .structure_validator import BANK_OF_INDIA_CONFIG, BankOfIndiaStructureValidator
from .transaction_validator import BankOfIndiaTransactionValidator

logger = logging.getLogger(__name__)

CONFIG = BANK_OF_INDIA_CONFIG


class BankOfIndiaProcessorError(Exception):
    pass


BankOfIndiaProcessingResult = BasePipelineResult


class BankOfIndiaProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "BANK_OF_INDIA"

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
        self.structure_validator = BankOfIndiaStructureValidator()
        self.parser = BankOfIndiaParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = BankOfIndiaTransactionValidator(strict_mode=False)
        self.reconciliation = BankOfIndiaReconciliation(strict_mode=False)
        self.rule_engine = BankOfIndiaRuleEngine()
        self.ai_fallback = BankOfIndiaAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = BankOfIndiaRecurringEngine()
        self.aggregation_engine = BankOfIndiaAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> BankOfIndiaProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
