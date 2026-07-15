"""Airco Insights - Unknown Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig, GenericProcessorError
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .aggregation_engine import UnknownAggregationEngine
from .ai_fallback import UnknownAIFallback
from .parser import UnknownParser
from .reconciliation import UnknownReconciliation
from .recurring_engine import UnknownRecurringEngine
from .rule_engine import UnknownRuleEngine
from .structure_validator import UnknownStructureValidator
from .transaction_validator import UnknownTransactionValidator

CONFIG = GenericBankConfig(
    bank_key="unknown",
    bank_name="Unknown",
    file_prefix="unknown",
    markers=[],
    support_aliases=["unknown", "unknown bank"],
)

logger = logging.getLogger(__name__)


class UnknownProcessorError(GenericProcessorError):
    pass


UnknownProcessingResult = BasePipelineResult


class UnknownProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "UNKNOWN"

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
        self.structure_validator = UnknownStructureValidator()
        self.parser = UnknownParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = UnknownTransactionValidator(strict_mode=False)
        self.reconciliation = UnknownReconciliation(strict_mode=False)
        self.rule_engine = UnknownRuleEngine()
        self.ai_fallback = UnknownAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = UnknownRecurringEngine()
        self.aggregation_engine = UnknownAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> UnknownProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
