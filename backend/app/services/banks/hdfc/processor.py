"""Airco Insights - HDFC Bank Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig, GenericProcessorError
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .aggregation_engine import HDFCAggregationEngine
from .ai_fallback import HDFCAIFallback
from .parser import HDFCParser
from .reconciliation import HDFCReconciliation
from .recurring_engine import HDFCRecurringEngine
from .rule_engine import HDFCRuleEngine
from .structure_validator import HDFCStructureValidator
from .transaction_validator import HDFCTransactionValidator

CONFIG = GenericBankConfig(
    bank_key="hdfc",
    bank_name="HDFC Bank",
    file_prefix="hdfc",
    markers=["hdfc bank", "account statement", "hdfc"],
    support_aliases=["hdfc", "hdfc bank", "housing development finance"],
)

logger = logging.getLogger(__name__)


class HDFCProcessorError(GenericProcessorError):
    pass


HDFCProcessingResult = BasePipelineResult


class HDFCProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "HDFC"

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
        self.structure_validator = HDFCStructureValidator()
        self.parser = HDFCParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = HDFCTransactionValidator(strict_mode=False)
        self.reconciliation = HDFCReconciliation(strict_mode=False)
        self.rule_engine = HDFCRuleEngine()
        self.ai_fallback = HDFCAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = HDFCRecurringEngine()
        self.aggregation_engine = HDFCAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> HDFCProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
