"""HDFC layout registration and glued-header splitting (separate from any V2 extraction work)."""
from app.services.statement_engine.layouts import _split_glued, detect_layout

HDFC_ID = "hdfc_date_narration_ref_valuedt_withdrawal_deposit_closing"

HEADERS = [
    "Date Narration Chq./Ref.No. ValueDt WithdrawalAmt. DepositAmt. ClosingBalance",            # compacted (99%)
    "Date Narration Chq./Ref.No. Value Dt Withdrawal Amt. Deposit Amt. Closing Balance",        # spaced
    "Date Narration Chq. / Ref No. Value Date Withdrawal Amount Deposit Amount Closing Balance*",
]


def test_glued_tokens_split_into_header_words():
    assert _split_glued("withdrawalamt") == ("withdrawal",)
    assert _split_glued("closingbalance") == ("balance",)
    assert _split_glued("valuedt") == ("value",)
    assert _split_glued("narration") == ("narration",)


def test_unrelated_words_are_not_split():
    assert _split_glued("hello") == ()
    assert _split_glued("statement") == ()


def test_hdfc_headers_resolve_to_hdfc_layout_for_hdfc():
    for h in HEADERS:
        r = detect_layout(["HDFC BANK\n" + h + "\n01/04/22 ABC 0000 01/04/22 10.00 1,000.00"], "hdfc")
        assert r.layout_id == HDFC_ID, h
        assert r.parser_family == "legacy:hdfc"
        assert r.confidence.value == "HIGH"


def test_other_banks_keep_generic_layout():
    r = detect_layout([HEADERS[0]], "axis")
    assert r.layout_id == "date_narration_withdrawal_deposit_balance"


def test_unidentified_bank_still_recognises_layout_from_header():
    # layout is recognised from the table header; a bank-specific layout only yields to an explicitly different bank
    assert detect_layout([HEADERS[0]], None).layout_id == HDFC_ID


def test_existing_generic_headers_unchanged():
    assert detect_layout(["Date Description Debit Credit Balance"], "sbi").layout_id == "date_description_debit_credit_balance"
    assert detect_layout(["Date Particulars Debit Credit Balance"], None).layout_id == "date_particulars_debit_credit_balance"
