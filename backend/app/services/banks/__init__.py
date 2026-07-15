"""
Airco Insights — Bank-Specific Processing Modules
=================================================
Each bank has its own dedicated processing module with:
- Structure validator
- Parser
- Transaction validator
- Balance reconciliation
- Rule engine
- AI fallback
- Recurring engine
- Aggregation engine
- Excel generator

No generic fallbacks. Each bank is a self-contained, accuracy-first processor.
"""

from .hdfc import HDFCProcessor
from .axis import AxisProcessor
from .icici import ICICIProcessor
from .indian_bank import IndianBankProcessor
from .kotak import KotakProcessor
from .canara import CanaraProcessor
from .idfc import IDFCProcessor
from .karnataka import KarnatakaProcessor
from .paytm import PaytmProcessor
from .union import UnionProcessor
from .bank_of_baroda import BankOfBarodaProcessor
from .bank_of_india import BankOfIndiaProcessor
from .sbi import SBIProcessor
from .unknown import UnknownProcessor

__all__ = [
    "HDFCProcessor",
    "AxisProcessor",
    "ICICIProcessor",
    "IndianBankProcessor",
    "KotakProcessor",
    "CanaraProcessor",
    "IDFCProcessor",
    "KarnatakaProcessor",
    "PaytmProcessor",
    "UnionProcessor",
    "BankOfBarodaProcessor",
    "BankOfIndiaProcessor",
    "SBIProcessor",
    "UnknownProcessor",
]
