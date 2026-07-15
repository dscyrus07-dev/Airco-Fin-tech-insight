"""
Airco Insights - Unknown Bank Transaction Validator
"""

import logging
from typing import Dict, List, Tuple

from .._shared.generic_bank import GenericTransactionValidator, GenericValidationError

logger = logging.getLogger(__name__)


class UnknownTransactionValidator(GenericTransactionValidator):
    pass


# Re-export for compatibility
UnknownValidationError = GenericValidationError
