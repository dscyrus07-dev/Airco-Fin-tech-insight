import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.banks.axis.parser import AxisParser
from app.services.banks.axis.reconciliation import AxisReconciliation


SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples" / "New Bank Samples Results" / "Axis"


@pytest.mark.parametrize(
    "pdf_name, expected_count, expected_date, expected_date_count",
    [
        (
            "9150100489_1712733393035.pdf",
            49,
            "10-03-2024",
            5,
        ),
        (
            "Account_stmt_XX4549_21022026_282_29_1772258477250.pdf",
            413,
            "01-10-2025",
            12,
        ),
    ],
)
def test_axis_parser_prefers_reconciled_complete_parse(pdf_name, expected_count, expected_date, expected_date_count):
    pdf_path = SAMPLES_DIR / pdf_name
    parser = AxisParser()

    result = parser.parse(str(pdf_path))

    assert result.parse_method == "text"
    assert result.total_count == expected_count

    date_counts = Counter(txn.date for txn in result.transactions)
    assert date_counts[expected_date] == expected_date_count

    reconciliation = AxisReconciliation(strict_mode=False).reconcile(
        [txn.to_dict() for txn in result.transactions],
        expected_opening=result.opening_balance,
        expected_closing=result.closing_balance,
    )
    assert reconciliation.is_reconciled is True
    assert reconciliation.mismatches == []
