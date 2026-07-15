"""
Airco Insights — Shared Recurring Engine (Phase 4)
=======================================
Detects recurring transactions (subscriptions, EMIs, salary).

Detection Methods:
1. Same merchant + similar amount + regular interval
2. Known recurring patterns (Netflix, EMI, etc.)
3. Salary detection (monthly credit, similar amount)

Output:
- is_recurring: bool
- recurring_type: "subscription" | "emi" | "salary" | "utility" | None
- recurring_frequency: "monthly" | "weekly" | "quarterly" | None
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RecurringPattern:
    """Detected recurring pattern."""
    merchant_key: str
    transaction_count: int
    avg_amount: float
    frequency: str  # monthly, weekly, quarterly
    recurring_type: str  # subscription, emi, salary, utility


class SharedRecurringEngine:
    """
    Recurring transaction detection for banks (parity with HDFC-grade engines).
    """
    
    # Known subscription merchants
    SUBSCRIPTION_MERCHANTS = {
        "netflix", "hotstar", "prime", "spotify", "apple", "youtube",
        "gaana", "wynk", "jiosaavn", "zee5", "sonyliv", "discovery",
        "linkedin", "microsoft", "google", "adobe", "dropbox",
    }
    
    # Known EMI patterns
    EMI_PATTERNS = [
        r"EMI.*\d+/\d+",
        r"LOAN.*EMI",
        r".*EMI.*DEBIT",
        r"BAJAJ\s*FIN",
        r"HOME\s*LOAN",
        r"CAR\s*LOAN",
    ]
    
    # Utility bill patterns
    UTILITY_PATTERNS = [
        r"ELECTRICITY", r"POWER", r"GAS", r"WATER", r"BROADBAND",
        r"MOBILE.*RECHARGE", r"DTH", r"INSURANCE.*PREMIUM",
    ]
    
    # Salary patterns
    SALARY_PATTERNS = [
        r"SALARY", r"SAL\s*CR", r"PAYROLL", r"WAGES",
    ]
    
    # Frequency thresholds (days)
    WEEKLY_RANGE = (5, 9)
    MONTHLY_RANGE = (25, 35)
    QUARTERLY_RANGE = (85, 95)
    
    # Amount tolerance for matching (percentage)
    AMOUNT_TOLERANCE = 0.05  # 5%
    
    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns."""
        self._emi_compiled = [re.compile(p, re.IGNORECASE) for p in self.EMI_PATTERNS]
        self._utility_compiled = [re.compile(p, re.IGNORECASE) for p in self.UTILITY_PATTERNS]
        self._salary_compiled = [re.compile(p, re.IGNORECASE) for p in self.SALARY_PATTERNS]
    
    def detect(
        self,
        transactions: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect recurring transactions.
        
        Args:
            transactions: List of classified transactions
            
        Returns:
            Transactions with recurring flags added
        """
        self.logger.info("Detecting recurring patterns in %d transactions", len(transactions))
        
        # Group by merchant key
        merchant_groups = self._group_by_merchant(transactions)
        
        # Detect patterns
        recurring_patterns = self._detect_patterns(merchant_groups)
        
        # Apply flags to transactions
        result = []
        for txn in transactions:
            txn_copy = dict(txn)
            merchant_key = self._get_merchant_key(txn)
            
            # Check known patterns first
            pattern_match = self._check_known_patterns(txn)
            if pattern_match:
                txn_copy["is_recurring"] = True
                txn_copy["recurring_type"] = pattern_match[0]
                txn_copy["recurring_frequency"] = pattern_match[1]
            elif merchant_key in recurring_patterns:
                pattern = recurring_patterns[merchant_key]
                txn_copy["is_recurring"] = True
                txn_copy["recurring_type"] = pattern.recurring_type
                txn_copy["recurring_frequency"] = pattern.frequency
            else:
                txn_copy["is_recurring"] = False
                txn_copy["recurring_type"] = None
                txn_copy["recurring_frequency"] = None
            
            result.append(txn_copy)
        
        recurring_count = sum(1 for t in result if t.get("is_recurring"))
        self.logger.info("Detected %d recurring transactions", recurring_count)
        
        return result
    
    def _group_by_merchant(
        self,
        transactions: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group transactions by normalized merchant key."""
        groups = defaultdict(list)
        
        for txn in transactions:
            key = self._get_merchant_key(txn)
            if key:
                groups[key].append(txn)
        
        return dict(groups)
    
    def _get_merchant_key(self, txn: Dict[str, Any]) -> str:
        """Extract normalized merchant key from transaction."""
        desc = (txn.get("description") or "").upper()
        
        # Remove common prefixes
        for prefix in ["UPI-", "NEFT-", "IMPS-", "POS "]:
            if desc.startswith(prefix):
                desc = desc[len(prefix):]
        
        # Extract first meaningful word
        words = re.findall(r'[A-Z]+', desc)
        if words:
            # Use first 2 significant words
            key_words = [w for w in words[:3] if len(w) > 2]
            return "_".join(key_words[:2]).lower()
        
        return ""
    
    def _detect_patterns(
        self,
        merchant_groups: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, RecurringPattern]:
        """Detect recurring patterns in grouped transactions."""
        patterns = {}
        
        for merchant_key, txns in merchant_groups.items():
            if len(txns) < 2:
                continue
            
            # Sort by date
            sorted_txns = sorted(txns, key=lambda t: t.get("date", ""))
            
            # Calculate intervals
            intervals = self._calculate_intervals(sorted_txns)
            
            if not intervals:
                continue
            
            # Check for recurring frequency
            avg_interval = sum(intervals) / len(intervals)
            frequency = self._determine_frequency(avg_interval)
            
            if not frequency:
                continue
            
            # Calculate average amount
            amounts = [t.get("debit") or t.get("credit") or 0 for t in txns]
            avg_amount = sum(amounts) / len(amounts)
            
            # Check amount consistency
            if not self._check_amount_consistency(amounts, avg_amount):
                continue
            
            # Determine recurring type
            recurring_type = self._determine_type(merchant_key, txns)
            
            patterns[merchant_key] = RecurringPattern(
                merchant_key=merchant_key,
                transaction_count=len(txns),
                avg_amount=avg_amount,
                frequency=frequency,
                recurring_type=recurring_type,
            )
        
        return patterns
    
    def _calculate_intervals(
        self,
        sorted_txns: List[Dict[str, Any]]
    ) -> List[int]:
        """Calculate day intervals between transactions."""
        intervals = []
        
        for i in range(1, len(sorted_txns)):
            try:
                prev_date = datetime.strptime(sorted_txns[i-1]["date"], "%Y-%m-%d")
                curr_date = datetime.strptime(sorted_txns[i]["date"], "%Y-%m-%d")
                delta = (curr_date - prev_date).days
                if delta > 0:
                    intervals.append(delta)
            except (ValueError, KeyError):
                continue
        
        return intervals
    
    def _determine_frequency(self, avg_interval: float) -> Optional[str]:
        """Determine recurring frequency from average interval."""
        if self.WEEKLY_RANGE[0] <= avg_interval <= self.WEEKLY_RANGE[1]:
            return "weekly"
        elif self.MONTHLY_RANGE[0] <= avg_interval <= self.MONTHLY_RANGE[1]:
            return "monthly"
        elif self.QUARTERLY_RANGE[0] <= avg_interval <= self.QUARTERLY_RANGE[1]:
            return "quarterly"
        return None
    
    def _check_amount_consistency(
        self,
        amounts: List[float],
        avg_amount: float
    ) -> bool:
        """Check if amounts are consistent (within tolerance)."""
        if avg_amount == 0:
            return False
        
        for amount in amounts:
            diff_pct = abs(amount - avg_amount) / avg_amount
            if diff_pct > self.AMOUNT_TOLERANCE:
                return False
        
        return True
    
    def _determine_type(
        self,
        merchant_key: str,
        txns: List[Dict[str, Any]]
    ) -> str:
        """Determine recurring type."""
        # Check for subscription
        if merchant_key in self.SUBSCRIPTION_MERCHANTS:
            return "subscription"
        
        # Check descriptions
        sample_desc = txns[0].get("description", "").upper()
        
        for pattern in self._emi_compiled:
            if pattern.search(sample_desc):
                return "emi"
        
        for pattern in self._utility_compiled:
            if pattern.search(sample_desc):
                return "utility"
        
        for pattern in self._salary_compiled:
            if pattern.search(sample_desc):
                return "salary"
        
        return "recurring"
    
    def _check_known_patterns(
        self,
        txn: Dict[str, Any]
    ) -> Optional[Tuple[str, str]]:
        """Check for known recurring patterns."""
        desc = (txn.get("description") or "").upper()
        
        # EMI check
        for pattern in self._emi_compiled:
            if pattern.search(desc):
                return ("emi", "monthly")
        
        # Salary check (credit only)
        if txn.get("credit"):
            for pattern in self._salary_compiled:
                if pattern.search(desc):
                    return ("salary", "monthly")
        
        # Subscription check
        desc_lower = desc.lower()
        for merchant in self.SUBSCRIPTION_MERCHANTS:
            if merchant in desc_lower:
                return ("subscription", "monthly")
        
        # Utility check
        for pattern in self._utility_compiled:
            if pattern.search(desc):
                return ("utility", "monthly")
        
        return None
