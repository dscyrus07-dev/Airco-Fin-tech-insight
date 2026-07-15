"""Shared Formula Excel Engine (Phase 5).

All banks emit the shared 9-sheet Lite workbook via pipeline.reporting.
Bank modules keep thin wrappers for processor wiring / bank_name defaults.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from app.services.pipeline.reporting.lite_excel_generator import LiteExcelGenerator

logger = logging.getLogger(__name__)


class FormulaExcelEngineBase:
    """Base class for bank formula Excel engines (Lite-only)."""

    def __init__(self, bank_name: str, report_generator_module: Optional[str] = None):
        self.bank_name = bank_name
        self.report_generator_module = report_generator_module
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._lite = LiteExcelGenerator()

    def generate(
        self,
        transactions: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        output_path: str,
    ) -> str:
        meta = dict(metadata or {})
        meta.setdefault("bank_name", self.bank_name)
        meta.setdefault("bankName", self.bank_name)
        if meta.get("name") and not meta.get("accountName"):
            meta["accountName"] = meta.get("name")
        if meta.get("account_no") and not meta.get("account_number"):
            meta["account_number"] = meta.get("account_no")

        self.logger.info(
            "FormulaExcelEngine: generating Lite %s report for %d transactions",
            self.bank_name,
            len(transactions or []),
        )

        parent_dir = os.path.dirname(output_path)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)

        return self._lite.generate(transactions or [], meta, output_path)


FormulaExcelEngine = FormulaExcelEngineBase
