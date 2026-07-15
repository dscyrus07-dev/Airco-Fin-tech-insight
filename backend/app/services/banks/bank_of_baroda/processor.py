"""Airco Insights - Bank of Baroda Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig, GenericProcessorError
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .aggregation_engine import BankOfBarodaAggregationEngine
from .ai_fallback import BankOfBarodaAIFallback
from .parser import BankOfBarodaParser
from .reconciliation import BankOfBarodaReconciliation
from .recurring_engine import BankOfBarodaRecurringEngine
from .rule_engine import BankOfBarodaRuleEngine
from .structure_validator import BankOfBarodaStructureValidator
from .transaction_validator import BankOfBarodaTransactionValidator

CONFIG = GenericBankConfig(
    bank_key="bank_of_baroda",
    bank_name="Bank of Baroda",
    file_prefix="bank_of_baroda",
    markers=["bank of baroda", "baroda", "bob"],
    support_aliases=["bank of baroda", "bankofbaroda", "bob", "baroda"],
)

logger = logging.getLogger(__name__)


class BankOfBarodaProcessorError(GenericProcessorError):
    pass


BankOfBarodaProcessingResult = BasePipelineResult


class BankOfBarodaProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "BANK_OF_BARODA"

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
        self.structure_validator = BankOfBarodaStructureValidator()
        self.parser = BankOfBarodaParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = BankOfBarodaTransactionValidator(strict_mode=False)
        self.reconciliation = BankOfBarodaReconciliation(strict_mode=False)
        self.rule_engine = BankOfBarodaRuleEngine()
        self.ai_fallback = BankOfBarodaAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = BankOfBarodaRecurringEngine()
        self.aggregation_engine = BankOfBarodaAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> BankOfBarodaProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
