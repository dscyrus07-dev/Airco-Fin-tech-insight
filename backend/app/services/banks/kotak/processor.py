"""Airco Insights - Kotak Mahindra Bank Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig, GenericProcessorError
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .aggregation_engine import KotakAggregationEngine
from .ai_fallback import KotakAIFallback
from .parser import KotakParser
from .reconciliation import KotakReconciliation
from .recurring_engine import KotakRecurringEngine
from .rule_engine import KotakRuleEngine
from .structure_validator import KotakStructureValidator
from .transaction_validator import KotakTransactionValidator

CONFIG = GenericBankConfig(
    bank_key="kotak",
    bank_name="Kotak Mahindra Bank",
    file_prefix="kotak",
    markers=["kotak mahindra bank", "kotak bank", "statement of account"],
    support_aliases=["kotak", "kotak mahindra", "kotak mahindra bank"],
)

logger = logging.getLogger(__name__)


class KotakProcessorError(GenericProcessorError):
    pass


KotakProcessingResult = BasePipelineResult


class KotakProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "KOTAK"

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
        self.structure_validator = KotakStructureValidator()
        self.parser = KotakParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = KotakTransactionValidator(strict_mode=False)
        self.reconciliation = KotakReconciliation(strict_mode=False)
        self.rule_engine = KotakRuleEngine()
        self.ai_fallback = KotakAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = KotakRecurringEngine()
        self.aggregation_engine = KotakAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> KotakProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
