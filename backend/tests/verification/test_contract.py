"""Frozen contract of the verification block (v1). The API response, the UI (2D) and MyPaisaa consumers read these keys.

Changing a key, a check name or a state value is a breaking change: bump `version`, update this test on purpose,
and tell the consumers. Adding a NEW optional key is allowed only by adding it here too.
"""
from app.services.verification import verify

EXPECTED_KEYS = {
    "checks", "failure_class", "failures", "notes", "observe_only", "raw_credit_count", "raw_debit_count",
    "raw_total_credits", "raw_total_debits", "raw_transaction_count", "reasons", "repair_masks_balance_failure",
    "repairs", "state", "validated_transaction_count", "version",
}
EXPECTED_CHECKS = {
    "balance_check", "duplicate_check", "header_period_check", "opening_closing_check",
    "printed_totals_check", "schema_check",
}
STATES = {"VERIFIED", "REVIEW", "FAILED"}


def _rows():
    return [
        {"date": "2024-01-01", "description": "SALARY", "debit": None, "credit": 500.0, "balance": 1500.0},
        {"date": "2024-01-02", "description": "UPI", "debit": 200.0, "credit": None, "balance": 1300.0},
    ]


def test_block_keys_are_frozen():
    d = verify(_rows(), opening=1000.0, closing=1300.0).to_dict()
    assert set(d) == EXPECTED_KEYS
    assert d["version"] == "v1" and d["observe_only"] is True


def test_check_names_and_shape_are_frozen():
    d = verify(_rows(), opening=1000.0, closing=1300.0).to_dict()
    assert set(d["checks"]) == EXPECTED_CHECKS
    for c in d["checks"].values():
        assert {"name", "status", "detail"} <= set(c)
        assert c["status"] in {"pass", "fail", "skip"}


def test_state_values_are_frozen():
    good = verify(_rows(), opening=1000.0, closing=1300.0).to_dict()
    bad = verify(_rows(), opening=1000.0, closing=999.0).to_dict()
    assert good["state"] in STATES and bad["state"] in STATES
    assert good["state"] == "VERIFIED" and bad["state"] == "FAILED"


def test_a_skipped_check_is_never_reported_as_pass():
    d = verify(_rows(), opening=None, closing=None).to_dict()
    assert d["checks"]["opening_closing_check"]["status"] == "skip"
    assert d["checks"]["printed_totals_check"]["status"] == "skip"
