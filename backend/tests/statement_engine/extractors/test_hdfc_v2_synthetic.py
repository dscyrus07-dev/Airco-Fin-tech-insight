"""Synthetic-fixture tests for the HDFC V2 extraction infrastructure. Pages are built from word coordinates in code;
no PDF or customer data is used."""
from decimal import Decimal

from app.services.statement_engine.extractors.hdfc.anchors import AnchorError, derive_anchors, classify_word
from app.services.statement_engine.extractors.hdfc.engine import extract_pages, NO_TABLE_HEADER, NO_ROWS
from app.services.statement_engine.extractors.hdfc.layout_spec import HDFC_LAYOUT_A as SPEC
from app.services.statement_engine.extractors.hdfc.normalize import parse_amount, parse_date, NormalizeError
from app.services.statement_engine.extractors.hdfc.rows import Page
from app.services.statement_engine.extractors.hdfc.summary import parse_summary
from app.services.statement_engine.extractors.hdfc.words import Word, group_lines

W = 638.0
RIGHT = {"withdrawal": 470.0, "deposit": 548.0, "balance": 627.0}


def w(text, x0, top, x1=None):
    return Word(text, x0, x1 if x1 is not None else x0 + 5.5 * len(text), top, top + 8)


def right(text, edge, top):
    return Word(text, edge - 5.5 * len(text), edge, top, top + 8)


def header(top=234.0):
    return [w("Date", 34, top), w("Narration", 68, top), w("Chq./Ref.No.", 295, top), w("ValueDt", 362, top),
            right("WithdrawalAmt.", RIGHT["withdrawal"], top), right("DepositAmt.", RIGHT["deposit"], top),
            right("ClosingBalance", RIGHT["balance"], top)]


def row(top, date, narr, ref, wd=None, dp=None, bal="0.00"):
    ws = [w(date, 34, top), w(narr, 68, top), w(ref, 295, top), w(date, 362, top)]
    if wd is not None:
        ws.append(right(wd, RIGHT["withdrawal"], top))
    if dp is not None:
        ws.append(right(dp, RIGHT["deposit"], top))
    ws.append(right(bal, RIGHT["balance"], top))
    return ws


def customer_block():
    return [w("AccountNo", 340, 150), w(":", 397, 150), w("50100012345678", 403, 150), w("RTGS/NEFTIFSC:", 340, 166),
            w("HDFC0001234", 403, 166)]


def period_line(top=216.0):
    return [w("StatementFrom", 34, top), w(":", 89, top), w("01/04/2022", 96, top), w("To", 158, top),
            w(":", 171, top), w("30/04/2022", 177, top)]


def summary(top, opening, drc, crc, debits, credits, closing):
    labels = [w("STATEMENT SUMMARY :-", 34, top)]
    names = ["OpeningBalance", "DrCount", "CrCount", "Debits", "Credits", "ClosingBal"]
    labels += [w(n, 34 + 80 * i, top + 14) for i, n in enumerate(names)]
    vals = [opening, str(drc), str(crc), debits, credits, closing]
    labels += [w(v, 34 + 80 * i, top + 28) for i, v in enumerate(vals)]
    return labels


def page1(rows, with_summary=None):
    ws = customer_block() + period_line() + header()
    for r in rows:
        ws += r
    if with_summary:
        ws += with_summary
    return Page(ws, W)


def good_rows():
    return [
        row(251, "01/04/22", "UPI-SHOP", "0001", wd="100.00", bal="900.00"),
        row(268, "02/04/22", "SALARY", "0002", dp="1,000.00", bal="1,900.00"),
        row(285, "03/04/22", "ATM CASH", "0003", wd="400.00", bal="1,500.00"),
    ]


def good_summary(top=400):
    return summary(top, "1,000.00", 2, 1, "500.00", "1,000.00", "1,500.00")


def test_group_lines_tolerates_small_cell_offsets_but_splits_wraps():
    lines = group_lines([w("a", 10, 100), w("b", 60, 104.5), w("c", 10, 117)])
    assert len(lines) == 2 and [x.text for x in lines[0]] == ["a", "b"]


def test_anchors_from_header_and_amount_classification():
    page = page1(good_rows())
    a = derive_anchors(page.words, SPEC, W)
    assert a.page_width == W
    assert classify_word(right("100.00", RIGHT["withdrawal"], 251), a, SPEC) == "withdrawal"
    assert classify_word(right("1,000.00", RIGHT["deposit"] + 1.5, 268), a, SPEC) == "deposit"
    assert classify_word(right("900.00", RIGHT["balance"], 251), a, SPEC) == "balance"


def test_anchors_shift_with_page_width():
    shifted = [Word(x.text, x.x0 - 43, x.x1 - 43, x.top, x.bottom) for x in page1(good_rows()).words]
    a = derive_anchors(shifted, SPEC, 595.0)
    assert classify_word(Word("100.00", 470 - 43 - 33, 470 - 43, 251, 259), a, SPEC) == "withdrawal"


def test_header_missing_raises():
    try:
        derive_anchors([w("nothing", 10, 10)], SPEC, W)
    except AnchorError:
        return
    raise AssertionError("expected AnchorError")


def test_clean_statement_verified():
    out = extract_pages([page1(good_rows(), good_summary())])
    assert out.failure is None and len(out.rows) == 3
    assert out.checks.verdict == "VERIFIED", out.checks
    t = out.rows[0].txn
    assert (t.date, t.debit, t.credit, t.balance) == ("2022-04-01", Decimal("100.00"), None, Decimal("900.00"))
    assert out.rows[1].txn.credit == Decimal("1000.00")
    assert out.account_number == "50100012345678" and out.ifsc == "HDFC0001234"
    assert out.period == ("01/04/2022", "30/04/2022")


def test_multiline_narration_and_wrapped_reference():
    rows = good_rows()
    rows[0] += [w("MORE-TEXT", 68, 259.5), w("5678", 295, 259.5)]
    out = extract_pages([page1(rows, good_summary())])
    assert out.rows[0].txn.description == "UPI-SHOP MORE-TEXT"
    assert out.rows[0].txn.ref_no == "00015678"
    assert len(out.rows) == 3


def test_amount_cells_slightly_lower_than_row_still_one_row():
    rows = good_rows()
    rows[0] = [x if x.text != "100.00" else Word("100.00", x.x0, x.x1, x.top + 5, x.bottom + 5) for x in rows[0]]
    out = extract_pages([page1(rows, good_summary())])
    assert len(out.rows) == 3 and out.rows[0].txn.debit == Decimal("100.00")


def test_page_break_continuation_without_header():
    p2 = Page(customer_block() + period_line(200.0) + row(240, "04/04/22", "BILL", "0004", wd="50.00", bal="1,450.00")
              + good_summary(400), W)
    summ = summary(400, "1,000.00", 3, 1, "550.00", "1,000.00", "1,450.00")
    p2 = Page(customer_block() + period_line(200.0) + row(240, "04/04/22", "BILL", "0004", wd="50.00", bal="1,450.00") + summ, W)
    out = extract_pages([page1(good_rows()), p2])
    assert len(out.rows) == 4 and out.rows[3].page == 2
    assert out.checks.verdict == "VERIFIED", out.checks


def test_summary_split_across_page_break():
    labels = [x for x in good_summary(700) if x.top < 730]
    nums = [x for x in good_summary(700) if x.top >= 730]
    nums = [Word(x.text, x.x0, x.x1, 240 + (x.top - 728), x.bottom) for x in nums]
    p1 = page1(good_rows(), [x for x in labels])
    p2 = Page(customer_block() + period_line(200.0) + nums, W)
    out = extract_pages([p1, p2])
    assert out.summary is not None and out.summary.dr_count == 2 and out.summary.closing == Decimal("1,500.00".replace(",", ""))
    assert out.checks.verdict == "VERIFIED", out.checks


def test_negative_withdrawal_is_credit_reversal_and_totals_reconcile():
    rows = [
        row(251, "01/04/22", "PAY", "1", wd="100.00", bal="900.00"),
        row(268, "02/04/22", "REV", "2", wd="-100.00", bal="1,000.00"),
    ]
    s = summary(400, "1,000.00", 2, 0, "0.00", "0.00", "1,000.00")   # bank counts the reversal in Dr and nets the sum
    out = extract_pages([page1(rows, s)])
    r = out.rows[1]
    assert r.reversal and r.printed_side == "withdrawal" and r.txn.credit == Decimal("100.00") and r.txn.debit is None
    assert out.checks.results["totals"].detail["outcome"] == "RECONCILED_VIA_REVERSALS"
    assert out.checks.verdict in ("VERIFIED", "REVIEW")


def test_chain_break_amount_error_fails():
    rows = good_rows()
    rows[2] = row(285, "03/04/22", "ATM CASH", "0003", wd="400.00", bal="1,400.00")
    out = extract_pages([page1(rows, good_summary())])
    assert out.checks.verdict == "FAILED" and out.checks.results["chain"].status == "fail"


def test_side_flip_detected():
    rows = good_rows()
    rows[1] = row(268, "02/04/22", "SALARY", "0002", wd="1,000.00", bal="1,900.00")
    out = extract_pages([page1(rows, good_summary())])
    assert out.checks.verdict == "FAILED"
    assert out.checks.results["side"].status == "fail"


def test_totals_mismatch_fails():
    s = summary(400, "1,000.00", 2, 1, "999.00", "1,000.00", "1,500.00")
    out = extract_pages([page1(good_rows(), s)])
    assert out.checks.verdict == "FAILED" and out.checks.results["totals"].status == "fail"


def test_no_summary_is_review():
    out = extract_pages([page1(good_rows())])
    assert out.checks.verdict == "REVIEW"


def test_reference_mismatch_fails():
    s = summary(400, "1,001.00", 2, 1, "500.00", "1,000.00", "1,500.00")
    out = extract_pages([page1(good_rows(), s)])
    assert out.checks.verdict == "FAILED"


def test_non_monotonic_dates_review():
    rows = good_rows()
    rows[1] = row(268, "01/03/22", "SALARY", "0002", dp="1,000.00", bal="1,900.00")
    out = extract_pages([page1(rows, good_summary())])
    assert out.checks.verdict == "REVIEW"


def test_period_one_day_outside_is_informational_more_is_warning():
    rows = good_rows()
    rows[2] = row(285, "01/05/22", "ATM CASH", "0003", wd="400.00", bal="1,500.00")   # 1 day after To
    assert extract_pages([page1(rows, good_summary())]).checks.verdict == "VERIFIED"
    rows[2] = row(285, "05/05/22", "ATM CASH", "0003", wd="400.00", bal="1,500.00")
    assert extract_pages([page1(rows, good_summary())]).checks.verdict == "REVIEW"
    rows[2] = row(285, "20/03/22", "ATM CASH", "0003", wd="400.00", bal="1,500.00")   # before From (bidirectional)
    assert extract_pages([page1(rows, good_summary())]).checks.results["period"].status == "warn"


def test_invalid_date_is_schema_failure():
    rows = good_rows()
    rows[0] = row(251, "31/02/22", "X", "1", wd="100.00", bal="900.00")
    out = extract_pages([page1(rows, good_summary())])
    assert out.checks.verdict == "FAILED"


def test_row_with_both_amounts_is_schema_failure():
    rows = good_rows()
    rows[0] = row(251, "01/04/22", "X", "1", wd="100.00", dp="100.00", bal="900.00")
    assert extract_pages([page1(rows, good_summary())]).checks.verdict == "FAILED"


def test_footer_words_left_of_date_column_ignored():
    p = page1(good_rows(), good_summary())
    p.words.append(w("HDFCBANKLIMITED", 28, 790))
    assert len(extract_pages([p]).rows) == 3


def test_no_header_and_no_rows_failures():
    assert extract_pages([Page([w("hello", 10, 10)], W)]).failure == NO_TABLE_HEADER
    assert extract_pages([page1([])]).failure == NO_ROWS


def test_empty_statement_with_zero_summary_succeeds():
    s = summary(300, "500.00", 0, 0, "0.00", "0.00", "500.00")
    out = extract_pages([page1([], s)])
    assert out.failure is None and out.rows == []


def test_parse_summary_indian_grouping_and_suffix():
    lines = group_lines(summary(10, "3,240.05", 91, 59, "3,01,417.0", "3,01,643.0", "225.05Cr"))
    s = parse_summary(lines)
    assert s.debits == Decimal("301417.0") and s.credits == Decimal("301643.0") and s.closing == Decimal("225.05")


def test_parse_amount_and_date():
    assert parse_amount("1,234.50") == Decimal("1234.50") and parse_amount("-20,000.00") == Decimal("-20000.00")
    assert parse_amount("  ") is None
    assert parse_date("01/04/22", "%d/%m/%y") == "2022-04-01"
    try:
        parse_date("30/02/22", "%d/%m/%y")
    except NormalizeError:
        return
    raise AssertionError("expected NormalizeError")


def test_second_statement_after_summary_is_review_not_silent_verified():
    p2 = Page(customer_block() + period_line(200.0) + row(240, "05/04/22", "NEXT", "0009", wd="10.00", bal="990.00"), W)
    out = extract_pages([page1(good_rows(), good_summary()), p2])
    assert out.checks.verdict == "REVIEW" and any(x.startswith("additional_statement_after_summary") for x in out.warnings)
    assert len(out.rows) == 3   # only the first statement is extracted


def test_password_errors_map_to_locked():
    from app.services.statement_engine.extraction.pdf_extractor import _is_password_error

    class PDFPasswordIncorrect(Exception):
        pass

    class PdfminerException(Exception):
        pass

    assert _is_password_error(PdfminerException(PDFPasswordIncorrect()))
    assert not _is_password_error(ValueError("bad xref"))
