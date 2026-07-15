"""Airco Insights - State Bank of India Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig, GenericProcessorError
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .aggregation_engine import SBIAggregationEngine
from .ai_fallback import SBIAIFallback
from .parser import SBIParser
from .reconciliation import SBIReconciliation
from .recurring_engine import SBIRecurringEngine
from .rule_engine import SBIRuleEngine
from .structure_validator import SBIStructureValidator
from .transaction_validator import SBITransactionValidator

CONFIG = GenericBankConfig(
    bank_key="sbi",
    bank_name="State Bank of India",
    file_prefix="sbi",
    markers=["state bank of india", "account statement", "sbin"],
    support_aliases=["sbi", "state bank of india", "state bank"],
)

logger = logging.getLogger(__name__)


class SBIProcessorError(GenericProcessorError):
    pass


SBIProcessingResult = BasePipelineResult


class SBIProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "SBI"

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
        self.structure_validator = SBIStructureValidator()
        self.parser = SBIParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = SBITransactionValidator(strict_mode=False)
        self.reconciliation = SBIReconciliation(strict_mode=False)
        self.rule_engine = SBIRuleEngine()
        self.ai_fallback = SBIAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = SBIRecurringEngine()
        self.aggregation_engine = SBIAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> SBIProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
