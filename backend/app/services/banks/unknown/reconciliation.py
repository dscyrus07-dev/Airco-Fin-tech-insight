"""
Airco Insights - Unknown Bank Reconciliation
"""

import logging
from typing import Dict, List

from .._shared.generic_bank import GenericReconciliation, GenericReconciliationError

logger = logging.getLogger(__name__)


class UnknownReconciliation(GenericReconciliation):
    pass


# Re-export for compatibility
UnknownReconciliationError = GenericReconciliationError
