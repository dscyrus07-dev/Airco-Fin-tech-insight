"""Airco Insights - Paytm Bank Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig, GenericProcessorError
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .aggregation_engine import PaytmAggregationEngine
from .ai_fallback import PaytmAIFallback
from .parser import PaytmParser
from .reconciliation import PaytmReconciliation
from .recurring_engine import PaytmRecurringEngine
from .rule_engine import PaytmRuleEngine
from .structure_validator import PaytmStructureValidator
from .transaction_validator import PaytmTransactionValidator

CONFIG = GenericBankConfig(
    bank_key="paytm",
    bank_name="Paytm Bank",
    file_prefix="paytm",
    markers=["paytm payments bank", "account statement for:", "paytm"],
    support_aliases=["paytm", "paytm bank", "paytm payments bank"],
)

logger = logging.getLogger(__name__)


class PaytmProcessorError(GenericProcessorError):
    pass


PaytmProcessingResult = BasePipelineResult


class PaytmProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "PAYTM"

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
        self.structure_validator = PaytmStructureValidator()
        self.parser = PaytmParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = PaytmTransactionValidator(strict_mode=False)
        self.reconciliation = PaytmReconciliation(strict_mode=False)
        self.rule_engine = PaytmRuleEngine()
        self.ai_fallback = PaytmAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = PaytmRecurringEngine()
        self.aggregation_engine = PaytmAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> PaytmProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
