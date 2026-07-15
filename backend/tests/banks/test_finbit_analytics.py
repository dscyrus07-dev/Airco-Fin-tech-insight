import pytest

from app.services.banks._shared.finbit_analytics import (
    FINBIT_ROWS,
    build_finbit_analytics,
    compute_finbit_monthly,
)


def make_txn(
    date,
    description,
    debit=0,
    credit=0,
    balance=0,
    category="Others Debit",
    confidence=0.91,
    channel="",
    entity="",
    matched_rule="",
    matched_token="",
    recurring="No",
):
    return {
        "date": date,
        "description": description,
        "debit": debit,
        "credit": credit,
        "balance": balance,
        "category": category,
        "confidence": confidence,
        "channel": channel,
        "entity": entity,
        "matched_rule": matched_rule,
        "matched_token": matched_token,
        "recurring": recurring,
    }


@pytest.fixture
def finbit_transactions():
    return [
        make_txn("2025-06-01", "Opening salary credit", credit=50000, balance=150000, category="Salary", entity="ACME CORP"),
        make_txn("2025-06-02", "Business receipt", credit=20000, balance=170000, category="Business Income", entity="CLIENT A"),
        make_txn("2025-06-03", "Cash deposit", credit=10000, balance=180000, category="Cash Deposit"),
        make_txn("2025-06-04", "Cheque deposit", credit=8000, balance=188000, category="Cheque Deposit"),
        make_txn("2025-06-05", "Cash withdrawal", debit=4000, balance=184000, category="Cash Withdrawal"),
        make_txn("2025-06-06", "Cheque issued", debit=3000, balance=181000, category="Cheque Issues"),
        make_txn("2025-06-07", "Loan EMI debit", debit=7000, balance=174000, category="Loan Payment / EMI", entity="HDB FINANCE"),
        make_txn("2025-06-08", "Loan disbursal", credit=25000, balance=199000, category="Loan Disbursal", entity="HDB FINANCE"),
        make_txn("2025-06-09", "Self withdrawal", debit=6000, balance=193000, category="Self Withdrawal", entity="SELF"),
        make_txn("2025-06-10", "Self deposit", credit=6000, balance=199000, category="Self Deposit", entity="SELF"),
        make_txn("2025-06-11", "ECS debit", debit=1800, balance=197200, category="ECS / NACH", matched_rule="pattern_match", matched_token="ECS"),
        make_txn("2025-06-12", "Inward bounce", debit=500, balance=196700, category="Inward Bounce"),
        make_txn("2025-06-13", "Outward bounce", debit=700, balance=196000, category="Outward Bounce"),
        make_txn("2025-06-14", "Credit card payment", debit=2000, balance=194000, category="Credit Card Payment"),
        make_txn("2025-06-15", "Penalty charge", debit=500, balance=193500, category="Bank Charges"),
        make_txn("2025-06-16", "General transfer", credit=9000, balance=202500, category="Transfer", channel="UPI", entity="CUSTOMER"),
        make_txn("2025-07-01", "Next month salary", credit=52000, balance=254500, category="Salary", entity="ACME CORP"),
        make_txn("2025-07-02", "Next month debit", debit=12000, balance=242500, category="Transfer Out", entity="SELF"),
    ]


def test_compute_finbit_monthly_returns_ordered_metrics(finbit_transactions):
    month_keys, monthly_metrics = compute_finbit_monthly(finbit_transactions, opening_balance=100000)

    assert month_keys == ["Jun-25", "Jul-25"]
    assert list(monthly_metrics["Jun-25"].keys()) == [row[0] for row in FINBIT_ROWS]


def test_finbit_metrics_and_metadata(finbit_transactions):
    analytics = build_finbit_analytics(finbit_transactions, opening_balance=100000)

    june = analytics["monthly_metrics"]["Jun-25"]
    june_meta = analytics["monthly_metadata"]["Jun-25"]

    assert june["salary"] == 50000
    assert june["cashDeposit"] == 10000
    assert june["nonCashCredit"] == 118000
    assert june["nonCashDebit"] == 21500
    assert june["loanRepayment"] == 7000
    assert june["loanCredit"] == 25000
    assert june["internalDebitTransactions"] == 6000
    assert june["internalCreditTransactions"] == 6000
    assert june["nonSalaryCredit"] == 78000
    assert june["income"] == 70000

    assert june_meta["salaryCreditCount"] == 1
    assert june_meta["loanRepaymentCount"] == 1
    assert june_meta["loanCreditCount"] == 1
    assert june_meta["internalDebitCount"] == 1
    assert june_meta["internalCreditCount"] == 1
    assert june_meta["ecsNachCount"] == 1

    groups = analytics["transaction_groups"]
    assert len(groups["salaryCreditsTransactions"]) == 2
    assert len(groups["loanTransactions"]) == 2
    assert len(groups["bounceTransactions"]) == 2
    assert len(groups["internalTransferTransactions"]) == 2

    profile = analytics["financial_profile"]
    assert profile["salary_detected"] is True
    assert profile["loan_detected"] is True
    assert profile["bounce_count"] == 2
