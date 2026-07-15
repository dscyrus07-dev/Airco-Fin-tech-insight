"""Airco Insights - Karnataka Bank Processor Module."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .._shared.base_processor import BaseBankProcessor, BasePipelineResult
from .._shared.generic_bank import GenericBankConfig, GenericProcessorError
from app.services.core.data_integrity_guard import DataIntegrityGuard
from app.services.core.pdf_integrity_validator import PDFIntegrityValidator

from .aggregation_engine import KarnatakaAggregationEngine
from .ai_fallback import KarnatakaAIFallback
from .parser import KarnatakaParser
from .reconciliation import KarnatakaReconciliation
from .recurring_engine import KarnatakaRecurringEngine
from .rule_engine import KarnatakaRuleEngine
from .structure_validator import KarnatakaStructureValidator
from .transaction_validator import KarnatakaTransactionValidator

CONFIG = GenericBankConfig(
    bank_key="karnataka",
    bank_name="Karnataka Bank",
    file_prefix="karnataka",
    markers=["karnataka bank", "statement for a/c", "karb"],
    support_aliases=["karnataka", "karnataka bank"],
)

logger = logging.getLogger(__name__)


class KarnatakaProcessorError(GenericProcessorError):
    pass


KarnatakaProcessingResult = BasePipelineResult


class KarnatakaProcessor(BaseBankProcessor):
    CONFIG = CONFIG
    BANK_LABEL = "KARNATAKA"

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
        self.structure_validator = KarnatakaStructureValidator()
        self.parser = KarnatakaParser(audit_service=audit_service, job_id=job_id)
        self.transaction_validator = KarnatakaTransactionValidator(strict_mode=False)
        self.reconciliation = KarnatakaReconciliation(strict_mode=False)
        self.rule_engine = KarnatakaRuleEngine()
        self.ai_fallback = KarnatakaAIFallback(api_key=api_key) if (enable_ai and api_key) else None
        self.recurring_engine = KarnatakaRecurringEngine()
        self.aggregation_engine = KarnatakaAggregationEngine()
        self.integrity_guard = DataIntegrityGuard(strict_mode=strict_mode)

    def process(
        self,
        file_path: str,
        user_info: Dict[str, Any],
        output_dir: Optional[str] = None,
    ) -> KarnatakaProcessingResult:
        return self._run_pipeline(file_path, user_info, output_dir)
