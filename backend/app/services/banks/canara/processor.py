"""Airco Insights - Canara Bank Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig, GenericProcessorError
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .aggregation_engine import CanaraAggregationEngine
from .ai_fallback import CanaraAIFallback
from .parser import CanaraParser
from .reconciliation import CanaraReconciliation
from .recurring_engine import CanaraRecurringEngine
from .rule_engine import CanaraRuleEngine
from .structure_validator import CanaraStructureValidator
from .transaction_validator import CanaraTransactionValidator

CONFIG = GenericBankConfig(
    bank_key="canara",
    bank_name="Canara Bank",
    file_prefix="canara",
    markers=["canara bank", "current & saving account statement", "cnrb"],
    support_aliases=["canara", "canara bank"],
)

logger = logging.getLogger(__name__)


class CanaraProcessorError(GenericProcessorError):
    pass


CanaraProcessingResult = BasePipelineResult


class CanaraProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "CANARA"

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
        self.structure_validator = CanaraStructureValidator()
        self.parser = CanaraParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = CanaraTransactionValidator(strict_mode=False)
        self.reconciliation = CanaraReconciliation(strict_mode=False)
        self.rule_engine = CanaraRuleEngine()
        self.ai_fallback = CanaraAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = CanaraRecurringEngine()
        self.aggregation_engine = CanaraAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> CanaraProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
