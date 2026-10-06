"""Loader tests on a synthetic old_result document (no customer data)."""
import json
from decimal import Decimal as D

import pytest

from app.services.migration import ContractError, Diff, compare_results, load_extraction_result


def doc(**over):
    d = {
        "schema": "airco.old_result/1", "engine": "old", "bank_key": "hdfc", "stage": "RAW", "status": "OK", "error": None,
        "printed": {"debit_count": None, "credit_count": None, "total_debits": None, "total_credits": None},
        "verification": {"state": "FAILED"},
        "derived": {"closing_from_last_row": "1150.00", "balance_chain_breaks": 0},
        "normalized": {
            "metadata": {"bank_name": "HDFC Bank", "bank_key": "hdfc", "account_number": "1234", "account_holder": "",
                         "account_type": "", "opening_balance": "1000.00", "closing_balance": "1000.00",
                         "statement_from": "01/01/2025", "statement_to": "31/01/2025"},
            "transactions": [
                {"date": "2025-01-02", "description": "UPI X", "debit": "100.0", "credit": None, "balance": "900.0", "ref_no": "r1", "value_date": "2025-01-02"},
                {"date": "2025-01-05", "description": "SALARY", "debit": None, "credit": "250.0", "balance": "1150.0", "ref_no": "", "value_date": None},
            ],
        },
    }
    d.update(over)
    return d


def test_loads_rows_exactly_as_decimals():
    r = load_extraction_result(doc())
    assert r.engine == "old" and r.stage == "RAW" and len(r.transactions) == 2
    assert r.transactions[0].debit == D("100.0") and r.transactions[0].credit is None
    assert r.transactions[1].credit == D("250.0") and r.transactions[1].balance == D("1150.0")
    assert r.verification_status == "FAILED"


def test_flags_unreliable_metadata_closing_without_changing_it():
    r = load_extraction_result(doc())
    assert r.metadata.closing_balance == D("1000.00")          # faithful to the old output
    assert any("closing_balance" in w for w in r.warnings)     # but flagged


def test_self_comparison_is_exact_match():
    a, b = load_extraction_result(doc()), load_extraction_result(doc())
    assert compare_results("x", "hdfc", a, b).overall == Diff.EXACT_MATCH


def test_failed_capture_becomes_failure_result(tmp_path):
    p = tmp_path / "o.json"
    p.write_text(json.dumps(doc(status="STRUCTURE_INVALID", error={"code": "HDFCStructureError", "message": "not hdfc"})))
    r = load_extraction_result(p)
    assert r.failure and "HDFCStructureError" in r.failure and r.transactions == []
    assert compare_results("x", "hdfc", r, load_extraction_result(doc())).overall == Diff.PARSER_FAILURE


def test_rejects_wrong_schema_or_stage():
    with pytest.raises(ContractError):
        load_extraction_result(doc(schema="other/1"))
    with pytest.raises(ContractError):
        load_extraction_result(doc(stage="REPAIRED"))
