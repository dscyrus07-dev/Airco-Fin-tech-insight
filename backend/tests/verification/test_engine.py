"""Synthetic tests for verification v1. No PDFs, no app services needed."""
import copy

from app.services.pipeline.reconciliation import compute_reconciliation, repair_transaction_sides  # existing code, used for the independence test
from app.services.verification import PrintedTotals, verify


def row(d, desc, debit=None, credit=None, bal=None):
    return {"date": d, "description": desc, "debit": debit, "credit": credit, "balance": bal}


def good_rows():
    # opening 1000.00
    return [
        row("2024-01-01", "SALARY", credit=500.0, bal=1500.0),
        row("2024-01-02", "UPI SHOP", debit=200.0, bal=1300.0),
        row("2024-01-03", "ATM", debit=300.0, bal=1000.0),
        row("2024-01-04", "INTEREST", credit=50.5, bal=1050.5),
    ]


OPEN, CLOSE = 1000.0, 1050.5


def test_good_statement_is_verified():
    r = verify(
        good_rows(),
        opening=OPEN,
        closing=CLOSE,
        printed=PrintedTotals(debit_count=2, credit_count=2, total_debits=500.0, total_credits=550.5),
        header_period=("01/01/2024", "31/01/2024"),
    )
    assert r.state == "VERIFIED"
    assert r.failures == []
    assert (r.raw_transaction_count, r.raw_debit_count, r.raw_credit_count) == (4, 2, 2)


def test_dropped_row_fails_even_though_repair_would_hide_it():
    rows = good_rows()
    del rows[1]  # parser lost the 200 debit
    r = verify(rows, opening=OPEN, closing=CLOSE)
    assert r.state == "FAILED"
    assert "balance_check" in r.failures
    assert "opening_closing_check" in r.failures

    # The repair makes the chain balance by construction. That is exactly why verify() runs before it.
    repaired, stats = repair_transaction_sides(rows, opening_balance=OPEN)
    after = verify(repaired, opening=OPEN, closing=CLOSE)
    assert stats["delta_repair"] >= 1
    assert after.check("balance_check").status == "pass"  # repaired data looks fine...
    assert r.check("balance_check").status == "fail"  # ...raw data does not

    # The existing reconciliation (what the pipeline runs after repair) is also fooled:
    # 3 rows instead of 4 transactions, yet it reports reconciled.
    existing = compute_reconciliation(repaired, expected_opening=OPEN)
    assert existing.is_reconciled is True
    assert len(repaired) == 3 and r.raw_transaction_count == 3

    # And the report can say so explicitly when repair stats are attached.
    r.repairs = dict(stats)
    assert r.repair_masks_balance_failure is True


def test_swapped_side_is_caught_on_raw_rows():
    rows = good_rows()
    rows[1]["debit"], rows[1]["credit"] = None, 200.0  # debit parsed as credit
    r = verify(rows, opening=OPEN, closing=CLOSE)
    assert r.state == "FAILED"
    assert r.raw_credit_count == 3 and r.raw_debit_count == 1


def test_printed_totals_mismatch_fails():
    r = verify(
        good_rows(),
        opening=OPEN,
        closing=CLOSE,
        printed=PrintedTotals(debit_count=3, credit_count=2, total_debits=500.0, total_credits=550.5),
    )
    assert r.state == "FAILED"
    assert "debit_count" in r.check("printed_totals_check").detail["differences"]


def test_printed_totals_absent_is_skip_not_pass():
    r = verify(good_rows(), opening=OPEN, closing=CLOSE, printed=None)
    assert r.check("printed_totals_check").status == "skip"


def test_duplicate_row_detected():
    rows = good_rows()
    rows.insert(2, copy.deepcopy(rows[1]))
    r = verify(rows, opening=OPEN, closing=CLOSE)
    assert r.check("duplicate_check").status == "fail"
    assert r.check("duplicate_check").detail["extra_rows"] == 1


def test_same_amount_same_day_but_different_balance_is_not_duplicate():
    rows = [
        row("2024-01-01", "UPI X", debit=100.0, bal=900.0),
        row("2024-01-01", "UPI X", debit=100.0, bal=800.0),
    ]
    r = verify(rows, opening=1000.0, closing=800.0)
    assert r.check("duplicate_check").status == "pass"
    assert r.state == "VERIFIED"


def test_schema_both_sides_and_bad_date():
    rows = good_rows()
    rows[0]["debit"] = 5.0  # both sides populated
    rows[2]["date"] = "not a date"
    r = verify(rows, opening=OPEN, closing=CLOSE)
    detail = r.check("schema_check").detail
    assert r.check("schema_check").status == "fail"
    assert detail["rows_with_both_or_no_amount"] == 1
    assert detail["unparseable_dates"] == 1


def test_header_period_outside_range_fails_check_and_gives_review_or_worse():
    r = verify(good_rows(), opening=OPEN, closing=CLOSE, header_period=("2024-01-02", "2024-01-31"))
    assert r.check("header_period_check").status == "fail"
    assert r.check("header_period_check").detail["rows_outside_period"] == 1
    assert r.state == "REVIEW"  # only a soft check failed


def test_reversed_order_statement_is_recognised():
    r = verify(list(reversed(good_rows())), opening=None, closing=CLOSE)
    bc = r.check("balance_check")
    assert bc.status == "pass"
    assert bc.detail["order_used"] == "reversed"


def test_no_balance_column_means_review_not_verified():
    rows = [row("2024-01-01", "A", debit=10.0), row("2024-01-02", "B", credit=5.0)]
    r = verify(rows, opening=None, closing=None)
    assert r.check("balance_check").status == "skip"
    assert r.state == "REVIEW"


def test_empty_rows():
    r = verify([], opening=None, closing=None)
    assert r.state == "REVIEW"
    assert r.raw_transaction_count == 0


def test_verify_does_not_mutate_input_and_records_repairs_without_changing_state():
    rows = good_rows()
    snapshot = copy.deepcopy(rows)
    r = verify(rows, opening=OPEN, closing=CLOSE, repair_stats={"swap": 3, "delta_repair": 2})
    assert rows == snapshot
    assert r.repairs == {"swap": 3, "delta_repair": 2}
    assert r.state == "VERIFIED"  # repairs are recorded, not scored, in v1


def test_float_noise_does_not_fail():
    rows = [
        row("2024-01-01", "A", credit=0.1, bal=0.1),
        row("2024-01-02", "B", credit=0.2, bal=0.3),
    ]
    r = verify(rows, opening=0.0, closing=0.3)
    assert r.check("balance_check").status == "pass"
    assert r.check("opening_closing_check").status == "pass"


def test_report_to_dict_shape():
    d = verify(good_rows(), opening=OPEN, closing=CLOSE).to_dict()
    assert d["version"] == "v1" and d["observe_only"] is True
    for k in ("raw_transaction_count", "raw_debit_count", "raw_credit_count", "repairs", "checks", "failures", "state"):
        assert k in d
    assert set(d["checks"]) == {
        "schema_check",
        "balance_check",
        "opening_closing_check",
        "printed_totals_check",
        "duplicate_check",
        "header_period_check",
    }


def test_reasons_for_dropped_row():
    rows = good_rows()
    del rows[1]
    r = verify(rows, opening=OPEN, closing=CLOSE)
    assert r.state == "FAILED" and r.failure_class == "ROWS_SUSPECT"
    assert "balance_chain_broken" in r.reasons and "opening_closing_mismatch" in r.reasons


def test_wrong_declared_closing_with_intact_chain_is_reference_mismatch_only():
    # The HDFC pattern found in the baseline: rows are perfect, the declared closing is the opening figure.
    r = verify(good_rows(), opening=OPEN, closing=OPEN)
    assert r.check("balance_check").status == "pass"
    assert r.state == "FAILED"
    assert r.failure_class == "REFERENCE_MISMATCH_ONLY"
    assert "declared_closing_differs_from_last_row_balance" in r.reasons
    d = r.check("opening_closing_check").detail
    assert d["declared_opening_matches_chain"] is True
    assert d["declared_closing_matches_last_row"] is False
    assert d["last_row_balance"] == CLOSE


def test_verified_has_no_reasons_but_may_have_notes():
    r = verify(good_rows(), opening=OPEN, closing=CLOSE)
    assert r.state == "VERIFIED" and r.reasons == [] and r.failure_class is None
    assert "printed_totals_unavailable" in r.notes and "header_period_unavailable" in r.notes


def test_no_running_balance_reason_and_class():
    rows = [row("2024-01-01", "A", debit=10.0), row("2024-01-02", "B", credit=5.0)]
    r = verify(rows, opening=None, closing=None)
    assert r.state == "REVIEW"
    assert r.reasons == ["no_running_balance"]
    assert r.failure_class == "INSUFFICIENT_EVIDENCE"


def test_empty_descriptions_only_is_data_quality():
    rows = good_rows()
    for x in rows:
        x["description"] = ""
    r = verify(rows, opening=OPEN, closing=CLOSE)
    assert r.state == "REVIEW" and r.failure_class == "DATA_QUALITY"
    assert r.reasons == ["schema_empty_descriptions"]


def test_missing_check_is_never_a_failure_by_itself():
    r = verify(good_rows(), opening=None, closing=None)  # no opening/closing, no printed, no period
    assert r.check("opening_closing_check").status == "skip"
    assert r.failures == []
    assert r.state == "VERIFIED"  # balance chain passed; skips are notes, not failures
    assert "opening_or_closing_unavailable" in r.notes


def test_printed_mismatch_reason_names_the_figure():
    r = verify(
        good_rows(),
        opening=OPEN,
        closing=CLOSE,
        printed=PrintedTotals(debit_count=2, credit_count=2, total_debits=999.0, total_credits=550.5),
    )
    assert "printed_total_debits_mismatch" in r.reasons
    assert r.failure_class == "REFERENCE_MISMATCH_ONLY"
