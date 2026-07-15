"""Airco Insights - ICICI Bank Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig, GenericProcessorError
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .aggregation_engine import ICICIAggregationEngine
from .ai_fallback import ICICIAIFallback
from .parser import ICICIParser
from .reconciliation import ICICIReconciliation
from .recurring_engine import ICICIRecurringEngine
from .rule_engine import ICICIRuleEngine
from .structure_validator import ICICIStructureValidator
from .transaction_validator import ICICITransactionValidator

CONFIG = GenericBankConfig(
    bank_key="icici",
    bank_name="ICICI Bank",
    file_prefix="icici",
    markers=["icici bank", "account statement", "icic"],
    support_aliases=["icici", "icici bank"],
)

logger = logging.getLogger(__name__)


class ICICIProcessorError(GenericProcessorError):
    pass


ICICIProcessingResult = BasePipelineResult


class ICICIProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "ICICI"

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
        self.structure_validator = ICICIStructureValidator()
        self.parser = ICICIParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = ICICITransactionValidator(strict_mode=False)
        self.reconciliation = ICICIReconciliation(strict_mode=False)
        self.rule_engine = ICICIRuleEngine()
        self.ai_fallback = ICICIAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = ICICIRecurringEngine()
        self.aggregation_engine = ICICIAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> ICICIProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
