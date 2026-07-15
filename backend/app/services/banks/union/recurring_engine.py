"""Phase 4: union recurring wraps shared pipeline.recurring."""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.pipeline.recurring.engine import (
    RecurringPattern,
    SharedRecurringEngine,
)

logger = logging.getLogger(__name__)


class UnionRecurringEngine:
    """Phase 4: delegates to SharedRecurringEngine."""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._engine = SharedRecurringEngine()

    def detect(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return self._engine.detect(transactions)
