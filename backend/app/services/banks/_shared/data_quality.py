from __future__ import annotations

from enum import Enum


class DataQuality(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


def compute_data_quality(
    recon_passed: bool,
    corrections: int,
    total: int,
    mismatches: int,
) -> tuple:
    """Returns (DataQuality, status_str, warnings_list)"""
    warnings = []
    if not recon_passed and total > 0:
        pct = (mismatches / total) * 100
        if pct >= 2.0:
            warnings.append(
                f"Balance mismatch in {mismatches}/{total} transactions ({pct:.1f}%) — verify with bank"
            )
            return DataQuality.LOW, "failed_major", warnings
        else:
            warnings.append(
                f"Minor discrepancy in {mismatches} transactions"
            )
            return DataQuality.MEDIUM, "failed_minor", warnings
    if corrections > 0:
        warnings.append(
            f"{corrections} transaction(s) auto-corrected"
        )
    return DataQuality.HIGH, "passed", warnings
