from app.services.pipeline.reporting.lite_metrics import build_lite_report_model


def _rows(with_balance):
    base = [
        {"date": "2024-01-02", "description": "A", "debit": 100.0, "credit": None},
        {"date": "2024-01-15", "description": "B", "debit": None, "credit": 250.0},
        {"date": "2024-02-03", "description": "C", "debit": 40.0, "credit": None},
    ]
    for i, r in enumerate(base):
        r["balance"] = (1000.0 + i) if with_balance else None
    return base


def test_no_balances_are_not_fabricated_as_zero():
    model = build_lite_report_model(_rows(False), {})
    assert all(r["balance_present"] is False for r in model["transactions"])
    monthly = model["monthly_analysis"]
    for key in ("Avg Balance", "Min Balance", "Max Balance", "Average EOD Balance", "Balance on Last Day"):
        assert all(v == "" for v in monthly[key].values()), key
    assert model["account_info"]["currentBalance"] == ""


def test_present_balances_unchanged():
    model = build_lite_report_model(_rows(True), {})
    assert all(r["balance_present"] for r in model["transactions"])
    assert any(v not in ("", 0.0) for v in model["monthly_analysis"]["Avg Balance"].values())
    assert model["account_info"]["currentBalance"] != ""


def test_genuine_zero_balance_counts_as_present():
    rows = _rows(True)
    rows[1]["balance"] = 0.0
    model = build_lite_report_model(rows, {})
    assert model["transactions"][1]["balance_present"] is True
