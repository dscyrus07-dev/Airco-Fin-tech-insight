"""Airco Insights - IDFC Bank Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig, GenericProcessorError
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .aggregation_engine import IDFCAggregationEngine
from .ai_fallback import IDFCAIFallback
from .parser import IDFCParser
from .reconciliation import IDFCReconciliation
from .recurring_engine import IDFCRecurringEngine
from .rule_engine import IDFCRuleEngine
from .structure_validator import IDFCStructureValidator
from .transaction_validator import IDFCTransactionValidator

CONFIG = GenericBankConfig(
    bank_key="idfc",
    bank_name="IDFC Bank",
    file_prefix="idfc",
    markers=["idfc first bank", "idfc bank", "statement of account", "idfb"],
    support_aliases=["idfc", "idfc bank", "idfc first", "idfc first bank"],
)

logger = logging.getLogger(__name__)


class IDFCProcessorError(GenericProcessorError):
    pass


IDFCProcessingResult = BasePipelineResult


class IDFCProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "IDFC"

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
        self.structure_validator = IDFCStructureValidator()
        self.parser = IDFCParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = IDFCTransactionValidator(strict_mode=False)
        self.reconciliation = IDFCReconciliation(strict_mode=False)
        self.rule_engine = IDFCRuleEngine()
        self.ai_fallback = IDFCAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = IDFCRecurringEngine()
        self.aggregation_engine = IDFCAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> IDFCProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
