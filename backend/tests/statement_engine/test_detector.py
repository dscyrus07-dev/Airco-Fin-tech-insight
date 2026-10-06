"""Synthetic tests for the bank detector. Text in, DetectionResult out: no PDFs needed."""
from app.services.statement_engine import (
    Confidence,
    EvidenceKind,
    default_registry,
    detect_bank,
)


def page(*lines):
    return "\n".join(lines)


TABLE = "Date Narration Withdrawal Deposit Balance"


def filler(n, text="01/04/2021 UPI/123456/PAYMENT TO MERCHANT 100.00 5000.00"):
    return [text] * n


def test_labelled_ifsc_plus_header_name_is_very_high():
    r = detect_bank([page("HDFC BANK LIMITED", "Statement of account", "IFSC Code : HDFC0001234", TABLE, *filler(30))])
    assert r.bank_id == "hdfc"
    assert r.confidence == Confidence.VERY_HIGH
    assert r.supported and r.processor_key == "hdfc"
    kinds = {e.kind for e in r.evidence}
    assert EvidenceKind.IFSC_LABELLED in kinds and EvidenceKind.HEADER_NAME in kinds


def test_other_banks_in_transaction_rows_do_not_count():
    body = [
        "NEFT-HDFC0001111-RAHUL-HDFC BANK 500.00",
        "UPI/rahul@okhdfcbank/ICICI BANK/pay 100.00",
        "IMPS-ICIC0002222-SBI-STATE BANK OF INDIA 20.00",
    ] * 15
    r = detect_bank([page("Axis Bank Limited", "Account Statement", "Customer ID 12345", TABLE, *filler(25), *body)])
    assert r.bank_id == "axis"
    assert r.confidence in (Confidence.MEDIUM, Confidence.HIGH, Confidence.VERY_HIGH)
    assert r.runner_up_score <= 8, "names in the body are at most weak evidence, far below the header's"


def test_state_bank_of_india_is_not_read_as_bank_of_india():
    r = detect_bank([page("State Bank of India", "Account Statement", "IFSC: SBIN0004321", TABLE, *filler(30))])
    assert r.bank_id == "sbi"
    assert r.runner_up_id != "bank_of_india"


def test_union_bank_of_india_is_not_bank_of_india():
    r = detect_bank([page("Union Bank of India", "Statement", "IFSC Code: UBIN0530000", TABLE, *filler(30))])
    assert r.bank_id == "union"


def test_bank_of_india_still_detected_on_its_own():
    r = detect_bank([page("Bank of India", "Detailed Statement", "IFSC: BKID0000123", TABLE, *filler(30))])
    assert r.bank_id == "bank_of_india"
    assert r.confidence == Confidence.VERY_HIGH


def test_reserve_bank_of_india_alone_is_unknown():
    r = detect_bank([page("Statement", "As per Reserve Bank of India guidelines", TABLE, *filler(30))])
    assert r.bank_id is None
    assert r.confidence == Confidence.UNKNOWN


def test_two_banks_in_the_header_is_not_auto_routable():
    r = detect_bank([page("Union Bank of India", "State Bank of India", TABLE, *filler(30))])
    assert not r.confidence.auto_routable
    assert r.confidence in (Confidence.UNKNOWN, Confidence.LOW)


def test_filename_alone_never_creates_confidence():
    r = detect_bank([page("Account statement", TABLE, *filler(30))], filename="HDFC_Jan_2026.pdf")
    assert r.bank_id is None and r.confidence == Confidence.UNKNOWN
    assert any(e.kind == EvidenceKind.FILENAME and e.bank_id == "hdfc" for e in r.supporting)


def test_user_hint_is_recorded_not_obeyed():
    r = detect_bank(
        [page("Axis Bank Limited", "IFSC: UTIB0000123", TABLE, *filler(30))],
        user_hint="HDFC Bank",
    )
    assert r.bank_id == "axis", "the document wins over the hint"
    assert r.hint_conflict is True
    assert any(e.kind == EvidenceKind.USER_HINT and e.bank_id == "hdfc" for e in r.supporting)


def test_agreeing_hint_is_no_conflict():
    r = detect_bank([page("Axis Bank Limited", "IFSC: UTIB0000123")], user_hint="axis", metadata_bank="Axis Bank")
    assert r.bank_id == "axis" and r.hint_conflict is False


def test_bare_token_alone_is_low_and_not_routable():
    r = detect_bank([page("HDFC", TABLE, *filler(30))])
    assert not r.confidence.auto_routable
    assert r.confidence in (Confidence.LOW, Confidence.UNKNOWN)


def test_known_but_unsupported_bank_is_detected_and_flagged():
    r = detect_bank([page("YES BANK LIMITED", "Statement", "IFSC Code: YESB0000001", TABLE, *filler(30))])
    assert r.bank_id == "yes"
    assert r.supported is False and r.processor_key is None


def test_running_header_across_pages_counts():
    pages = [page("Statement of account", TABLE, *filler(30)) for _ in range(3)]
    pages = ["Karnataka Bank Limited\n" + p for p in pages]
    r = detect_bank(pages)
    assert r.bank_id == "karnataka"
    assert any(e.kind == EvidenceKind.RUNNING_HEADER for e in r.evidence)


def test_domain_in_the_issuer_block_is_evidence():
    r = detect_bank([page("Statement of account", "Visit www.icicibank.com for more", TABLE, *filler(30))])
    kinds = {e.kind for e in r.evidence}
    assert EvidenceKind.DOMAIN in kinds


def test_empty_input_is_unknown():
    assert detect_bank([]).confidence == Confidence.UNKNOWN
    assert detect_bank([""]).bank_id is None


def test_result_is_json_ready():
    import json

    r = detect_bank([page("HDFC BANK LIMITED", "IFSC Code : HDFC0001234")])
    json.dumps(r.to_dict())


def test_registry_is_consistent():
    reg = default_registry()
    assert reg.validate() == []
    assert len(reg.banks) >= 40


def test_supported_banks_match_real_processors():
    try:
        from app.services.pipeline_orchestrator import _PROCESSOR_IMPORTS
    except Exception:  # heavy import not available in this environment
        import pytest

        pytest.skip("orchestrator not importable here")
    reg = default_registry()
    for b in reg.banks.values():
        if b.processor_key:
            assert b.processor_key in _PROCESSOR_IMPORTS, f"{b.id}: processor_key {b.processor_key!r} has no processor"
    keys_in_registry = {b.processor_key for b in reg.banks.values() if b.processor_key}
    for k in _PROCESSOR_IMPORTS:
        if k != "unknown":
            assert k in keys_in_registry, f"processor {k!r} has no registry entry"


def test_bank_names_after_the_table_starts_are_never_the_issuer():
    # third-party e-statement with no issuer header: the only bank text is a counterparty IFSC in a wrapped row
    p = page(
        "Account Number: 131901509397",
        "Transaction date : From 26/05/2023 To 26/11/2023",
        "Date Description Amount Type",
        "31-10-2023 MMT/IMPS/330407362289/NA DR",
        "579036115/Bharadwaz/HDFC0003 50500.00",
        "788",
    )
    r = detect_bank([p])
    assert r.bank_id is None and r.confidence == Confidence.UNKNOWN


def test_ifsc_in_a_narration_is_not_labelled_issuer_evidence():
    p = page("Account Statement", TABLE, "01/04/2021 NEFT IFSC: HDFC0001234 Rahul 100.00 5000.00", *filler(5))
    r = detect_bank([p])
    assert r.bank_id is None


def test_bank_name_without_a_transaction_table_is_not_a_statement():
    payslip = page("AXIS BANK LTD", "PAYSLIP FOR THE MONTH OF NOVEMBER 2024", "BASIC 12,379.00 PROFESSION TAX 200.00")
    r = detect_bank([payslip])
    assert r.looks_like_statement is False
    assert not r.confidence.auto_routable and r.confidence in (Confidence.LOW, Confidence.UNKNOWN)


def test_counterparty_name_wrapped_to_top_of_different_pages_is_not_a_running_header():
    first = page("Account Statement", TABLE, *filler(10))
    later = [page(f"Ref {i}000 paid to YES BANK vendor {i}", *filler(10)) for i in (2, 3)]
    r = detect_bank([first, *later])
    assert not r.confidence.auto_routable, "20 points of running-header evidence alone must stay below MEDIUM"


def test_house_number_address_does_not_end_the_header_block():
    # Axis: an address line "2-91/81 G8 TRANQUIL TOWERS" looked like a date; the IFSC below it must still count
    p = page(
        "INDIA CAP FIN",
        "2-91/81 G8 TRANQUIL TOWERS",
        "1-4-15 GANDHI NAGAR",
        "TELANGANA-INDIA IFSC Code :UTIB0001458",
        TABLE,
        *filler(5),
    )
    r = detect_bank([p])
    assert r.bank_id == "axis" and any(e.kind == EvidenceKind.IFSC_LABELLED for e in r.evidence)


def test_period_line_does_not_end_the_header_block():
    p = page("Account Statement", "01 Aug 2025 - 31 Aug 2025", "Branch Hyderabad", "MICR 500485049 IFSC Code KKBK0007494", TABLE, *filler(5))
    assert detect_bank([p]).bank_id == "kotak"


def test_page_timestamp_header_is_a_running_header_not_a_transaction():
    pages = [
        page(f"29-11-2022 14:41:48 BANK OF INDIA, GACHIBOWLI Page {i}", "Account Number :563610110000338", TABLE, *filler(5))
        for i in (1, 2, 3)
    ]
    r = detect_bank(pages)
    assert r.bank_id == "bank_of_india"


def test_text_layer_without_spaces_still_matches_long_names():
    p = page("Page1of12", "KotakMahindraBank", "CRN No. 464793880", TABLE, *filler(5))
    assert detect_bank([p]).bank_id == "kotak"


# ---- Slice 2B final validation: template wording regressions (found by reviewing old-detector-only matches) ----

def _pages(*lines):
    return ["\n".join(lines)]


def test_axis_template_wording_identifies_axis():
    r = detect_bank(_pages(
        "P RAVIKANTH .", "Joint Holder :- -", "Customer No :888762662",
        "Statement of Axis Account No :919010074289512 for the period (From : 25-04-2022 To : 24-10-2022)",
        "Tran Date Chq No Particulars Debit Credit Balance Init. Br",
        "01-05-2022 UPI/P2A/214601801069/NAME/Kotak 2000.00 2512.56 1446",
        "02-05-2022 UPI/P2A/214601801070/NAME/Kotak 100.00 2412.56 1446",
        "03-05-2022 UPI/P2A/214601801071/NAME/Kotak 100.00 2312.56 1446"))
    assert r.bank_id == "axis" and r.confidence.value in ("MEDIUM", "HIGH", "VERY_HIGH")


def test_kotak_spaceless_disclaimer_identifies_kotak():
    r = detect_bank(_pages(
        "DateAsOn 30-Jun-22", "CRN No. 464793880", "HomeBranch Hyderabad",
        "AnydiscrepancyinthestatementshouldbebroughttothenoticeofKotakMahindraBankLtd.withinonemonthfromdateofstatement",
        "Date Narration Chq/RefNo Withdrawal(Dr)/Deposit(Cr) Balance",
        "01-Jun-22 UPI/xx/1 100.00(Dr) 900.00(Cr)", "02-Jun-22 UPI/xx/2 100.00(Dr) 800.00(Cr)", "03-Jun-22 UPI/xx/3 100.00(Dr) 700.00(Cr)"))
    assert r.bank_id == "kotak" and r.confidence.value != "UNKNOWN"


def test_counterparty_mention_of_axis_wording_in_transactions_is_not_evidence():
    r = detect_bank(_pages(
        "Account Number: 123", "Date Description Amount Type",
        "06-11-2023 NEFT Statement of Axis Account No 5 DR 100.00",
        "07-11-2023 UPI/1/x DR 10.00", "08-11-2023 UPI/2/x DR 10.00"))
    assert r.bank_id != "axis"


def test_axis_older_domain_is_axis_evidence():
    r = detect_bank(_pages(
        "01/01/2022 to 31/01/2022", "M B VENUGOPAL", "Customer ID: XXXXX9790", "Axis Bank statement of account",
        "Visit www.axisbank.co.in",
        "Tran Date Chq No Particulars Debit Credit Balance",
        "01-01-2022 UPI/1/x 10.00 100.00", "02-01-2022 UPI/2/x 10.00 90.00", "03-01-2022 UPI/3/x 10.00 80.00"))
    assert r.bank_id == "axis" and r.confidence.value != "UNKNOWN"
