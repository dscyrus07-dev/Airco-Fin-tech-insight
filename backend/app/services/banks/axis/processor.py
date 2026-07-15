"""Airco Insights - Axis Bank Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig, GenericProcessorError
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .aggregation_engine import AxisAggregationEngine
from .ai_fallback import AxisAIFallback
from .parser import AxisParser
from .reconciliation import AxisReconciliation
from .recurring_engine import AxisRecurringEngine
from .rule_engine import AxisRuleEngine
from .structure_validator import AxisStructureValidator
from .transaction_validator import AxisTransactionValidator

CONFIG = GenericBankConfig(
    bank_key="axis",
    bank_name="Axis Bank",
    file_prefix="axis",
    markers=["axis bank", "account statement", "utib"],
    support_aliases=["axis", "axis bank"],
)

logger = logging.getLogger(__name__)


class AxisProcessorError(GenericProcessorError):
    pass


AxisProcessingResult = BasePipelineResult


class AxisProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "AXIS"

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
        self.structure_validator = AxisStructureValidator()
        self.parser = AxisParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = AxisTransactionValidator(strict_mode=False)
        self.reconciliation = AxisReconciliation(strict_mode=False)
        self.rule_engine = AxisRuleEngine()
        self.ai_fallback = AxisAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = AxisRecurringEngine()
        self.aggregation_engine = AxisAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> AxisProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
