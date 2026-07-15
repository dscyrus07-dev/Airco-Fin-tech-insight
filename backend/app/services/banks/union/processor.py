"""Airco Insights - Union Bank of India Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig, GenericProcessorError
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .aggregation_engine import UnionAggregationEngine
from .ai_fallback import UnionAIFallback
from .parser import UnionParser
from .reconciliation import UnionReconciliation
from .recurring_engine import UnionRecurringEngine
from .rule_engine import UnionRuleEngine
from .structure_validator import UnionStructureValidator
from .transaction_validator import UnionTransactionValidator

CONFIG = GenericBankConfig(
    bank_key="union",
    bank_name="Union Bank of India",
    file_prefix="union",
    markers=["union bank of india", "statement of account", "ubin"],
    support_aliases=["union", "union bank", "union bank of india", "ubi"],
)

logger = logging.getLogger(__name__)


class UnionProcessorError(GenericProcessorError):
    pass


UnionProcessingResult = BasePipelineResult


class UnionProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "UNION"

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
        self.structure_validator = UnionStructureValidator()
        self.parser = UnionParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = UnionTransactionValidator(strict_mode=False)
        self.reconciliation = UnionReconciliation(strict_mode=False)
        self.rule_engine = UnionRuleEngine()
        self.ai_fallback = UnionAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = UnionRecurringEngine()
        self.aggregation_engine = UnionAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> UnionProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
