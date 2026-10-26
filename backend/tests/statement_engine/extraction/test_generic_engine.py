"""Proof that the extraction engine is configuration-driven: three synthetic layouts that differ from HDFC (column
set and order, date formats, header repetition, summary shape, period format) run through the SAME engine code, plus
HDFC through the registry. Pages are built from word coordinates; no PDFs, no customer data."""
import re
from pathlib import Path
from decimal import Decimal

from app.services.statement_engine.extraction import registry as registry_mod
from app.services.statement_engine.extraction.engine import extract_pages
from app.services.statement_engine.extraction.layout_spec import LayoutSpec
from app.services.statement_engine.extraction.normalize import parse_amount
from app.services.statement_engine.extraction.registry import LayoutRegistry
from app.services.statement_engine.extraction.rows import Page
from app.services.statement_engine.extraction.words import Word
from app.services.statement_engine.extractors.hdfc.layout_spec import HDFC_LAYOUT_A
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY

W = 600.0


def w(text, x0, top):
    return Word(text, x0, x0 + 5.5 * len(text), top, top + 8)


def rt(text, edge, top):
    return Word(text, edge - 5.5 * len(text), edge, top, top + 8)


# ---------------------------------------------------------------- three alternative layouts
ALPHA = LayoutSpec(   # Date | Particulars | Debit | Credit | Balance ; no reference column; header on every page
    layout_id="alpha", bank_key="alpha", bank_name="Alpha Bank",
    columns={"date": (("txn", "date"),), "narration": (("particulars",),), "debit": (("debit",),), "credit": (("credit",),), "balance": (("balance",),)},
    text_columns=("date", "narration"), debit_column="debit", credit_column="credit", balance_column="balance",
    date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"), date_format="%d-%m-%Y", amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"Period:(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"), period_date_format="%d-%m-%Y",
    summary_marker="ACCOUNTSUMMARY", summary_label_text="totaldebitstotalcreditsclosingbalance",
    summary_fields=("debits", "credits", "closing"), header_repeats=True, account_label="accountnumber")
BETA = LayoutSpec(    # Date | Details | Chq No | Credit | Debit | Balance ; credit left of debit; summary prints only opening/closing
    layout_id="beta", bank_key="beta", bank_name="Beta Bank",
    columns={"date": (("date",),), "narration": (("details",),), "ref": (("chq", "no"),), "credit": (("credit",),), "debit": (("debit",),), "balance": (("balance",),)},
    text_columns=("date", "narration", "ref"), debit_column="debit", credit_column="credit", balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"), date_format="%d/%m/%Y", amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"Statementperiod:(\d{2}/\d{2}/\d{4})-(\d{2}/\d{2}/\d{4})"), period_date_format="%d/%m/%Y",
    summary_marker="SUMMARY", summary_label_text="openingclosing", summary_fields=("opening", "closing"), account_label="acno")
GAMMA = LayoutSpec(   # Date | Description | Ref | Value Date | Money Out | Money In | Balance ; 3-letter month dates ; no summary block
    layout_id="gamma", bank_key="gamma", bank_name="Gamma Bank",
    columns={"date": (("date",),), "narration": (("description",),), "ref": (("ref",),), "value_date": (("value", "date"),),
             "out": (("money", "out"),), "in": (("money", "in"),), "balance": (("balance",),)},
    text_columns=("date", "narration", "ref", "value_date"), debit_column="out", credit_column="in", balance_column="balance",
    date_re=re.compile(r"^\d{2}-[A-Za-z]{3}-\d{2}$"), date_format="%d-%b-%y", amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"From(\d{2}-[A-Za-z]{3}-\d{4})To(\d{2}-[A-Za-z]{3}-\d{4})"), period_date_format="%d-%b-%Y",
    summary_marker="NOSUMMARYMARKER", summary_label_text="x", secondary_date_column="value_date", account_label="account")

GEO = {   # x0 of text columns, right edge of money columns, per layout
    "alpha": dict(text={"date": 30, "narration": 120}, money={"debit": 400, "credit": 470, "balance": 560},
                  titles={"date": ["Txn", "Date"], "narration": ["Particulars"], "debit": ["Debit"], "credit": ["Credit"], "balance": ["Balance"]}),
    "beta": dict(text={"date": 25, "narration": 100, "ref": 260}, money={"credit": 380, "debit": 450, "balance": 540},
                 titles={"date": ["Date"], "narration": ["Details"], "ref": ["Chq", "No"], "credit": ["Credit"], "debit": ["Debit"], "balance": ["Balance"]}),
    "gamma": dict(text={"date": 20, "narration": 90, "ref": 240, "value_date": 300}, money={"out": 410, "in": 480, "balance": 570},
                  titles={"date": ["Date"], "narration": ["Description"], "ref": ["Ref"], "value_date": ["Value", "Date"], "out": ["Money", "Out"], "in": ["Money", "In"], "balance": ["Balance"]}),
}


def header(spec, top=200.0):
    g = GEO[spec.layout_id]
    out = []
    for col, toks in g["titles"].items():
        if col in g["text"]:
            x = g["text"][col]
            for t in toks:
                out.append(w(t, x, top)); x += 5.5 * len(t) + 4
        else:
            edge = g["money"][col]
            x = edge - sum(5.5 * len(t) + 4 for t in toks) + 4
            for t in toks:
                out.append(w(t, x, top)); x += 5.5 * len(t) + 4
    return out


def row(spec, top, date, narr, debit=None, credit=None, balance="0.00", ref="", vdate=None):
    g = GEO[spec.layout_id]
    ws = [w(date, g["text"]["date"], top), w(narr, g["text"]["narration"], top)]
    if "ref" in g["text"]:
        ws.append(w(ref or "R1", g["text"]["ref"], top))
    if "value_date" in g["text"]:
        ws.append(w(vdate or date, g["text"]["value_date"], top))
    if debit is not None:
        ws.append(rt(debit, g["money"][spec.debit_column], top))
    if credit is not None:
        ws.append(rt(credit, g["money"][spec.credit_column], top))
    ws.append(rt(balance, g["money"][spec.balance_column], top))
    return ws


def page(spec, rows, period_words=None, summary_words=None, with_header=True, extra=None):
    ws = list(extra or []) + list(period_words or [])
    if with_header:
        ws += header(spec)
    for r in rows:
        ws += r
    ws += summary_words or []
    return Page(ws, W)


# ---- alpha
def alpha_rows():
    return [row(ALPHA, 220, "01-04-2022", "SHOP", debit="100.00", balance="900.00"),
            row(ALPHA, 237, "02-04-2022", "SALARY", credit="1,000.00", balance="1,900.00")]


ALPHA_PERIOD = [w("Period:", 30, 170), w("01-04-2022", 80, 170), w("to", 150, 170), w("30-04-2022", 165, 170)]


def alpha_summary(top=400, debits="100.00", credits="1,000.00", closing="1,900.00"):
    return [w("Account Summary", 30, top), w("Total", 30, top + 14), w("Debits", 70, top + 14), w("Total", 120, top + 14), w("Credits", 160, top + 14),
            w("Closing", 220, top + 14), w("Balance", 270, top + 14), w(debits, 30, top + 28), w(credits, 120, top + 28), w(closing, 220, top + 28)]


def test_alpha_header_every_page_and_threecolumn_summary():
    p1 = page(ALPHA, alpha_rows(), ALPHA_PERIOD)
    p2 = page(ALPHA, [row(ALPHA, 220, "03-04-2022", "BILL", debit="50.00", balance="1,850.00")], ALPHA_PERIOD, alpha_summary(300, "150.00", "1,000.00", "1,850.00"))
    out = extract_pages([p1, p2], ALPHA)
    assert out.failure is None and len(out.rows) == 3 and out.rows[2].page == 2
    assert out.rows[1].txn.credit == Decimal("1000.00") and out.rows[0].txn.date == "2022-04-01"
    assert out.summary.debits == Decimal("150.00") and out.summary.dr_count is None
    assert out.checks.verdict == "VERIFIED", out.checks.reasons


def test_alpha_mismatching_summary_fails_and_chain_break_fails():
    p = page(ALPHA, alpha_rows(), ALPHA_PERIOD, alpha_summary(closing="1,901.00"))
    assert extract_pages([p], ALPHA).checks.verdict == "FAILED"
    rows = alpha_rows(); rows[1] = row(ALPHA, 237, "02-04-2022", "SALARY", credit="1,000.00", balance="1,950.00")
    assert extract_pages([page(ALPHA, rows, ALPHA_PERIOD, alpha_summary())], ALPHA).checks.results["chain"].status == "fail"


def test_alpha_account_number_and_no_ref_column():
    extra = [w("Account", 30, 150), w("Number", 80, 150), w("1234567890", 130, 150)]
    out = extract_pages([page(ALPHA, alpha_rows(), ALPHA_PERIOD, alpha_summary(), extra=extra)], ALPHA)
    assert out.account_number == "1234567890" and out.rows[0].txn.ref_no == ""


# ---- beta
BETA_PERIOD = [w("Statement", 25, 170), w("period:", 80, 170), w("01/04/2022", 130, 170), w("-", 200, 170), w("30/04/2022", 215, 170)]


def beta_rows():
    return [row(BETA, 220, "01/04/2022", "SHOP", debit="100.00", balance="900.00", ref="C1"),
            row(BETA, 237, "02/04/2022", "SALARY", credit="1,000.00", balance="1,900.00", ref="C2")]


def beta_summary(opening="1,000.00", closing="1,900.00"):
    return [w("Summary", 25, 400), w("Opening", 25, 414), w("Closing", 100, 414), w(opening, 25, 428), w(closing, 100, 428)]


def test_beta_credit_column_left_of_debit_and_partial_summary():
    out = extract_pages([page(BETA, beta_rows(), BETA_PERIOD, beta_summary())], BETA)
    assert out.failure is None and out.rows[0].txn.debit == Decimal("100.00") and out.rows[1].txn.credit == Decimal("1000.00")
    assert out.rows[0].txn.ref_no == "C1"
    assert out.checks.results["reference"].status == "pass" and out.checks.results["totals"].status == "skipped"
    assert out.checks.verdict == "VERIFIED", out.checks.reasons


def test_beta_header_only_on_first_page_continuation_works():
    p2 = page(BETA, [row(BETA, 220, "03/04/2022", "BILL", debit="50.00", balance="1,850.00", ref="C3")], BETA_PERIOD, beta_summary(closing="1,850.00"), with_header=False)
    out = extract_pages([page(BETA, beta_rows(), BETA_PERIOD), p2], BETA)
    assert len(out.rows) == 3 and out.checks.verdict == "VERIFIED", out.checks.reasons


def test_beta_reversal_uses_spec_debit_column():
    rows = [row(BETA, 220, "01/04/2022", "PAY", debit="100.00", balance="900.00"), row(BETA, 237, "02/04/2022", "REV", debit="-100.00", balance="1,000.00")]
    out = extract_pages([page(BETA, rows, BETA_PERIOD, beta_summary(closing="1,000.00"))], BETA)
    assert out.rows[1].reversal and out.rows[1].printed_side == "debit" and out.rows[1].txn.credit == Decimal("100.00")


# ---- gamma
GAMMA_PERIOD = [w("From", 20, 170), w("01-Apr-2022", 60, 170), w("To", 140, 170), w("30-Apr-2022", 170, 170)]


def test_gamma_value_date_month_names_no_summary_is_review():
    rows = [row(GAMMA, 220, "01-Apr-22", "SHOP", debit="100.00", balance="900.00", vdate="02-Apr-22"),
            row(GAMMA, 237, "03-Apr-22", "SALARY", credit="1,000.00", balance="1,900.00")]
    out = extract_pages([page(GAMMA, rows, GAMMA_PERIOD)], GAMMA)
    assert out.failure is None and out.rows[0].txn.value_date == "2022-04-02" and out.rows[0].txn.date == "2022-04-01"
    assert out.checks.verdict == "REVIEW"


# ---------------------------------------------------------------- registry and detection
def test_detect_layout_picks_the_matching_spec_and_rejects_others():
    reg = LayoutRegistry([HDFC_LAYOUT_A, ALPHA, BETA, GAMMA])
    assert [s.layout_id for s in reg.detect([page(ALPHA, alpha_rows(), ALPHA_PERIOD)])] == ["alpha"]
    assert [s.layout_id for s in reg.detect([page(BETA, beta_rows(), BETA_PERIOD)])] == ["beta"]
    assert [s.layout_id for s in reg.detect([page(GAMMA, [], GAMMA_PERIOD)])] == ["gamma"]
    assert reg.detect([Page([w("nothing", 10, 10)], W)]) == []
    assert [s.bank_key for s in reg.for_bank("beta")] == ["beta"]


def test_registry_rejects_duplicate_and_invalid_specs():
    reg = LayoutRegistry([ALPHA])
    for bad in (lambda: reg.register(ALPHA),):
        try:
            bad()
        except ValueError:
            continue
        raise AssertionError("duplicate accepted")
    broken = LayoutSpec(**{**ALPHA.__dict__, "layout_id": "broken", "text_columns": ("date",)})
    try:
        LayoutRegistry([broken])
    except ValueError:
        pass
    else:
        raise AssertionError("invalid spec accepted")


def test_default_registry_has_hdfc_layout_a():
    assert DEFAULT_REGISTRY.get(HDFC_LAYOUT_A.layout_id) is HDFC_LAYOUT_A and DEFAULT_REGISTRY.for_bank("hdfc")
    assert DEFAULT_REGISTRY.for_bank("sbi")


# ---------------------------------------------------------------- the engine contains no bank-specific code
def test_engine_package_has_no_bank_specific_strings():
    pkg = Path(registry_mod.__file__).parent
    banks = re.compile(r"hdfc|sbi\b|axis|kotak|icici|withdrawal|deposit|valuedt|chqrefno|ifsc", re.I)
    offenders = {f.name: banks.findall(f.read_text()) for f in pkg.rglob("*.py") if banks.search(f.read_text())}
    # ifsc is an optional spec field (ifsc_re); any other hit is a generalisation leak
    offenders = {k: [x for x in v if x.lower() != "ifsc"] for k, v in offenders.items()}
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, offenders


# ---------------------------------------------------------------- DELTA: value date before narration, wrapped date cell,
# footer end marker, no summary block, printed opening balance ("Balance as on ...")
DELTA = LayoutSpec(
    layout_id="delta", bank_key="delta", bank_name="Delta Bank",
    columns={"date": (("txndate",), ("txn", "date")), "value_date": (("value",),), "narration": (("description",),), "debit": (("debit",),),
             "credit": (("credit",),), "balance": (("balance",),)},
    text_columns=("date", "value_date", "narration"), debit_column="debit", credit_column="credit", balance_column="balance",
    date_re=re.compile(r"^\d{1,2} [A-Za-z]{3}(?: \d{4})?$"), date_tail_re=re.compile(r"^\d{4}$"), date_format="%d %b %Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    period_re=re.compile(r"Statementfrom(\d{1,2}[A-Za-z]{3}\d{4})to(\d{1,2}[A-Za-z]{3}\d{4})"), period_date_format="%d%b%Y",
    summary_marker="", summary_label_text="", summary_expected=False, end_markers=("COMPUTERGENERATEDSTATEMENT",),
    secondary_date_column="value_date", header_repeats=True,
    opening_balance_re=re.compile(r"Balanceason\d{1,2}[A-Za-z]{3}\d{4}:(-?[\d,]+\.\d{2})"), account_label="accountnumber")
GEO["delta"] = dict(text={"date": 40, "value_date": 95, "narration": 145}, money={"debit": 414, "credit": 478, "balance": 557},
                    titles={"date": ["Txn", "Date"], "value_date": ["Value"], "narration": ["Description"], "debit": ["Debit"], "credit": ["Credit"], "balance": ["Balance"]})
DELTA_TOP = [w("Account", 36, 60), w("Number", 80, 60), w(":", 130, 60), w("12345678901", 140, 60),
             w("Balance", 36, 80), w("as", 80, 80), w("on", 100, 80), w("1", 120, 80), w("Jan", 130, 80), w("2023", 150, 80), w(":", 180, 80), w("1,000.00", 190, 80),
             w("Statement", 36, 100), w("from", 90, 100), w("1", 120, 100), w("Jan", 130, 100), w("2023", 150, 100), w("to", 180, 100), w("31", 200, 100), w("Jan", 215, 100), w("2023", 240, 100)]


def drow(top, date, vdate, narr, debit=None, credit=None, balance="0.00", wrapped=False):
    g = GEO["delta"]
    if wrapped:   # right-aligned date cell wrapped onto two lines: "10 Jan" / "2023"
        d, y = date.rsplit(" ", 1)
        ws = [rt(d, 87, top), rt(vdate.rsplit(" ", 1)[0], 140, top), w(narr, 145, top)]
        ws += [rt(y, 87, top + 9), rt(vdate.rsplit(" ", 1)[1], 140, top + 9)]
    else:
        ws = [rt(date, 87, top), rt(vdate, 140, top), w(narr, 145, top)]
    if debit is not None:
        ws.append(rt(debit, 414, top))
    if credit is not None:
        ws.append(rt(credit, 478, top))
    ws.append(rt(balance, 557, top))
    return ws


def delta_header(top=200.0):
    return header(DELTA, top) + [w("Date", 95, top + 10)]   # second header line ("Value" / "Date")


def delta_page(rows, with_header=True, extra=None):
    ws = list(extra or [])
    if with_header:
        ws += delta_header()
    for r in rows:
        ws += r
    return Page(ws, 595.0)


def test_delta_wrapped_dates_value_before_narration_footer_and_opening():
    rows = [drow(230, "5 Jan 2023", "5 Jan 2023", "SHOP", debit="100.00", balance="900.00"),
            drow(250, "10 Jan 2023", "10 Jan 2023", "SALARY", credit="1,000.00", balance="1,900.00", wrapped=True)]
    footer = [w("Please do not share your PIN", 36, 400), w("This is a computer generated statement", 36, 420)]
    out = extract_pages([delta_page(rows, extra=DELTA_TOP + footer)], DELTA)
    assert out.failure is None and len(out.rows) == 2
    assert out.rows[1].txn.date == "2023-01-10" and out.rows[1].txn.value_date == "2023-01-10"
    assert out.rows[0].txn.description == "SHOP" and out.account_number == "12345678901"
    assert out.summary.opening == Decimal("1000.00") and out.checks.results["reference"].status == "pass"
    assert out.checks.verdict == "VERIFIED", out.checks.reasons
    assert "footer" not in out.rows[1].txn.description.lower()


def test_delta_second_header_line_is_not_a_continuation_of_previous_row():
    p1 = delta_page([drow(230, "5 Jan 2023", "5 Jan 2023", "SHOP", debit="100.00", balance="900.00")], extra=DELTA_TOP)
    p2 = delta_page([drow(230, "6 Jan 2023", "6 Jan 2023", "BILL", debit="50.00", balance="850.00")])
    out = extract_pages([p1, p2], DELTA)
    assert len(out.rows) == 2 and out.rows[0].txn.description == "SHOP" and out.rows[0].txn.ref_no == ""


def test_delta_statement_after_footer_page_is_review():
    p1 = delta_page([drow(230, "5 Jan 2023", "5 Jan 2023", "SHOP", debit="100.00", balance="900.00")], extra=DELTA_TOP)
    foot = Page([w("This is a computer generated statement", 36, 100)], 595.0)
    p3 = delta_page([drow(230, "9 Mar 2023", "9 Mar 2023", "OTHER", debit="5.00", balance="5.00")])
    out = extract_pages([p1, foot, p3], DELTA)
    assert len(out.rows) == 1 and out.checks.verdict == "REVIEW" and any(x.startswith("additional_statement") for x in out.warnings)


def test_summary_not_expected_still_cannot_verify_without_an_independent_anchor():
    # Superseded assertion (was: summary-less layouts reach VERIFIED). A balance chain whose opening is derived from
    # row 0 cannot prove row 0, so without a printed opening/closing the result is capped at REVIEW.
    rows = [drow(230, "5 Jan 2023", "5 Jan 2023", "SHOP", debit="100.00", balance="900.00")]
    out = extract_pages([delta_page(rows, extra=DELTA_TOP[:3] + DELTA_TOP[3:] if False else DELTA_TOP[:4] + DELTA_TOP[14:])], DELTA)
    assert out.summary is None and out.checks.verdict == "REVIEW", out.checks.reasons
    assert any("independent opening/closing anchor" in r for r in out.checks.reasons)


# ---------------------------------------------------------------- ECHO: printed closing-balance line inside the table, page-number
# lines, rows not date-sorted, isolated side flips treated as review, wider period tolerance, strict header gate
from dataclasses import replace

ECHO = replace(ALPHA, layout_id="echo", bank_key="echo", summary_marker="", summary_label_text="", summary_expected=False,
               end_markers=("ENDOFSTATEMENT",), closing_balance_re=re.compile(r"^ClosingBalance(-?[\d,]+\.\d{2})$"),
               ignore_line_res=(re.compile(r"^page\d+$", re.I),), dates_monotonic_expected=False, period_tolerance_days=3,
               side_flip_policy="review")
GEO["echo"] = GEO["alpha"]


def echo_page(rows, closing=None, extra=()):
    ws = list(ALPHA_PERIOD) + header(ALPHA)
    for r in rows:
        ws += r
    if closing:
        ws += [w("Closing", 120, 330), w("Balance", 170, 330), rt(closing, 560, 330)]
    ws += [w("page", 500, 800), w("1", 535, 800), w("END OF STATEMENT", 30, 360)] if closing else [w("page", 500, 800), w("1", 535, 800)]
    return Page(ws + list(extra), W)


def test_echo_closing_line_and_page_numbers_do_not_pollute_rows():
    out = extract_pages([echo_page(alpha_rows(), closing="1,900.00")], ECHO)
    assert len(out.rows) == 2 and "page" not in out.rows[1].txn.description.lower() and "Closing" not in out.rows[1].txn.description
    assert out.summary.closing == Decimal("1900.00") and out.checks.results["reference"].status == "pass"
    assert out.checks.verdict == "VERIFIED", out.checks.reasons
    assert extract_pages([echo_page(alpha_rows(), closing="1,901.00")], ECHO).checks.verdict == "FAILED"


def test_echo_side_flip_policy_review_and_unsorted_dates_and_period_tolerance():
    rows = [row(ALPHA, 220, "05-04-2022", "A", debit="100.00", balance="900.00"),
            row(ALPHA, 237, "02-04-2022", "B", debit="50.00", balance="950.00")]   # printed debit but balance rose
    out = extract_pages([echo_page(rows)], ECHO)
    assert out.checks.results["side"].status == "warn" and out.checks.verdict == "REVIEW"
    assert extract_pages([echo_page(rows)], replace(ECHO, side_flip_policy="fail")).checks.verdict == "FAILED"
    ok = [row(ALPHA, 220, "05-04-2022", "A", debit="100.00", balance="900.00"), row(ALPHA, 237, "02-04-2022", "B", credit="50.00", balance="950.00")]
    assert extract_pages([echo_page(ok)], ECHO).checks.results["dates"].status == "info"
    assert extract_pages([echo_page(ok)], replace(ECHO, dates_monotonic_expected=True)).checks.results["dates"].status == "warn"
    late = [row(ALPHA, 220, "02-05-2022", "A", debit="100.00", balance="900.00")]   # 2 days after To (30-04-2022)
    assert extract_pages([echo_page(late)], ECHO).checks.results["period"].status == "info"
    assert extract_pages([echo_page(late)], replace(ECHO, period_tolerance_days=1)).checks.results["period"].status == "warn"


def test_header_with_an_unknown_extra_column_is_refused():
    page_ = echo_page(alpha_rows())
    page_.words.append(w("Mode", 250, 200))   # extra title between known columns => a different layout
    assert extract_pages([page_], ECHO).failure == "NO_TABLE_HEADER"


# ---------------------------------------------------------------- FOXTROT: transaction-total line, page-top continuation,
# balances printed without a leading zero, stray words right of the money columns
FOXTROT = replace(ECHO, layout_id="foxtrot", bank_key="foxtrot", amount_re=re.compile(r"^-?[\d,]*\.\d{2}$"),
                  totals_line_re=re.compile(r"^TRANSACTIONTOTAL(-?[\d,]*\.\d{2})(-?[\d,]*\.\d{2})$"), continuation_start="top",
                  side_flip_policy="fail")
GEO["foxtrot"] = GEO["alpha"]


def fox_page(rows, totals=("100.00", "1,000.00")):
    ws = list(ALPHA_PERIOD) + header(ALPHA)
    for r in rows:
        ws += r
    ws += [w("TRANSACTION TOTAL", 30, 330), rt(totals[0], 400, 330), rt(totals[1], 470, 330),
           w("Closing", 120, 345), w("Balance", 170, 345), rt("1,900.00", 560, 345), w("END OF STATEMENT", 30, 380)]
    return Page(ws, W)


def test_foxtrot_totals_line_zero_balance_without_leading_zero_and_stray_trailing_word():
    rows = [row(FOXTROT, 220, "01-04-2022", "SHOP", debit="100.00", balance="900.00"),
            row(FOXTROT, 237, "02-04-2022", "REFUND", debit="900.00", balance=".00") + [w("514", 585, 237)],
            row(FOXTROT, 254, "03-04-2022", "SALARY", credit="1,000.00", balance="1,000.00")]
    out = extract_pages([fox_page(rows, totals=("1,000.00", "1,000.00"))], FOXTROT)
    assert [r.txn.balance for r in out.rows] == [Decimal("900.00"), Decimal("0.00"), Decimal("1000.00")]
    assert out.rows[1].txn.debit == Decimal("900.00")
    assert out.summary.debits == Decimal("1000.00") and out.summary.credits == Decimal("1000.00")
    assert out.checks.results["totals"].status == "pass"
    bad = extract_pages([fox_page(rows, totals=("999.00", "1,000.00"))], FOXTROT)
    assert bad.checks.results["totals"].status == "fail"


# ---------------------------------------------------------------- GOLF: summary printed ABOVE the table, overdraft balances in brackets
GOLF = replace(ALPHA, layout_id="golf", bank_key="golf", summary_position="before",
               amount_re=re.compile(r"^(?:-?[\d,]*\.\d{2}|\(-?[\d,]*\.\d{2}\))$"),
               summary_label_text="totaldebitstotalcreditsclosingbalance")
GEO["golf"] = GEO["alpha"]


def test_golf_summary_above_table_and_bracketed_negative_balances():
    rows = [row(GOLF, 220, "01-04-2022", "SHOP", debit="1,100.00", balance="(100.00)"),
            row(GOLF, 237, "02-04-2022", "SALARY", credit="1,000.00", balance="900.00")]
    summ = alpha_summary(top=90, debits="1,100.00", credits="1,000.00", closing="900.00")
    out = extract_pages([page(GOLF, rows, period_words=ALPHA_PERIOD, summary_words=summ)], GOLF)
    assert [r.txn.balance for r in out.rows] == [Decimal("-100.00"), Decimal("900.00")]
    assert out.summary is not None and out.summary.closing == Decimal("900.00") and out.summary.debits == Decimal("1100.00")
    assert out.checks.results["totals"].status == "pass"


# ---------------------------------------------------------------- HOTEL: cover page before the table, dated OPENING BALANCE row, +/- decorated
# amounts, "(Cr)" balance suffix, date fused with narration, "^SUMMARY" end marker
HOTEL = replace(ALPHA, layout_id="hotel", bank_key="hotel", sign_is_decoration=True, opening_row_marker="OPENINGBALANCE",
                amount_re=re.compile(r"^[+-]?[\d,]+\.\d{2}(?:\(Cr\))?$"), summary_marker="", summary_label_text="", summary_expected=False,
                end_markers=("^SUMMARY",), closing_balance_re=re.compile(r"^ClosingBalance([\d,]+\.\d{2})\(Cr\)$"))
GEO["hotel"] = GEO["alpha"]


def test_hotel_cover_page_opening_row_signed_amounts_suffix_fused_date_and_summary_marker():
    cover = Page([w("Portfolio", 30, 100), w("overview", 100, 100)], W)
    ws = list(ALPHA_PERIOD) + header(HOTEL)
    ws += [w("01-04-2022", 30, 220), w("OPENING", 120, 220), w("BALANCE", 180, 220), rt("1,000.00(Cr)", 560, 220)]
    ws += [Word("02-04-2022 SHOP", 30, 30 + 5.5 * 15, 237, 245), rt("-100.00", 400, 237), rt("900.00(Cr)", 560, 237)]
    ws += [w("03-04-2022", 30, 254), w("PAY", 120, 254), rt("+50.00", 470, 254), rt("950.00(Cr)", 560, 254)]
    ws += [w("SUMMARY", 30, 300), w("Closing", 30, 315), w("Balance", 90, 315), rt("950.00(Cr)", 560, 315)]
    out = extract_pages([cover, Page(ws, W)], HOTEL)
    assert [r.txn.date for r in out.rows] == ["2022-04-02", "2022-04-03"]
    assert out.rows[0].txn.debit == Decimal("100.00") and out.rows[1].txn.credit == Decimal("50.00")
    assert not any(r.reversal for r in out.rows)
    assert out.summary.opening == Decimal("1000.00") and out.summary.closing == Decimal("950.00")
    assert out.checks.results["chain"].status == "pass" and out.checks.results["reference"].status == "pass", out.checks.reasons
    dr = parse_amount("100.00(Dr)", suffix_sign=True)
    assert dr == Decimal("-100.00") and parse_amount("(100.00)") == Decimal("-100.00")


def test_band_left_pad_lets_narration_data_start_left_of_a_centred_title():
    from app.services.statement_engine.extraction.anchors import derive_anchors
    base = derive_anchors(header(ALPHA) + [w("01-04-2022", 30, 220)], ALPHA, W)
    padded = derive_anchors(header(ALPHA) + [w("01-04-2022", 30, 220)], replace(ALPHA, band_left_pad={"narration": 40.0}), W)
    assert padded.text_lefts["narration"] == base.text_lefts["narration"] - 36.0   # default pad is 4


# ---------------------------------------------------------------- INDIA: per-page footer, separate Cr/Dr balance word, dated CLOSING row,
# date fused directly with the next cell, band_left_pad via spec
INDIA = replace(ALPHA, layout_id="india", bank_key="india", amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?(?:Cr|Dr))?$"),
                summary_marker="", summary_label_text="", summary_expected=False, merge_drcr_suffix=True,
                opening_row_marker="OPENINGBALANCE", closing_row_marker="CLOSINGBALANCE", page_footer_markers=("NOTE:INCASE",))
GEO["india"] = GEO["alpha"]


def test_india_footer_cr_suffix_word_closing_row_and_fused_date():
    ws1 = list(ALPHA_PERIOD) + header(INDIA)
    ws1 += [w("01-04-2022", 30, 220), w("OPENING", 120, 220), w("BALANCE", 180, 220), rt("1,000.00", 545, 220), w("Cr", 548, 220)]
    ws1 += [Word("02-04-2022SHOP", 30, 30 + 5.5 * 14, 237, 245), rt("100.00", 400, 237), rt("900.00", 545, 237), w("Cr", 548, 237)]
    ws1 += [w("Note: In case you find", 30, 700), w("computer generated 03-04-2022 text", 30, 712)]      # footer: must not become rows
    ws2 = list(ALPHA_PERIOD) + header(INDIA)
    ws2 += [w("03-04-2022", 30, 220), w("PAY", 120, 220), rt("50.00", 470, 220), rt("950.00", 545, 220), w("Cr", 548, 220)]
    ws2 += [w("04-04-2022", 30, 237), w("CLOSING", 120, 237), w("BALANCE", 180, 237), rt("950.00", 545, 237), w("Cr", 548, 237)]
    out = extract_pages([Page(ws1, W), Page(ws2, W)], INDIA)
    assert [r.txn.date for r in out.rows] == ["2022-04-02", "2022-04-03"], [r.txn.date for r in out.rows]
    assert out.rows[0].txn.balance == Decimal("900.00") and out.rows[1].txn.credit == Decimal("50.00")
    assert out.summary.opening == Decimal("1000.00") and out.summary.closing == Decimal("950.00")
    assert out.checks.results["reference"].status == "pass" and out.checks.results["chain"].status == "pass", out.checks.reasons


# ---------------------------------------------------------------- JULIET: ONE amount column ending in (Dr)/(Cr), newest row first, zero-as-empty pair
JULIET = replace(ALPHA, layout_id="juliet", bank_key="juliet", single_amount_column="amount", debit_column="amount_dr", credit_column="amount_cr",
                 columns={"date": (("txn", "date"),), "narration": (("particulars",),), "amount": (("amount",),), "balance": (("balance",),)},
                 amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?\((?:Cr|Dr)\))?$"), row_order="reverse",
                 summary_marker="", summary_label_text="", summary_expected=False)
GEO["juliet"] = dict(text={"date": 30, "narration": 120}, money={"amount": 400, "balance": 560},
                     titles={"date": ["Txn", "Date"], "narration": ["Particulars"], "amount": ["Amount"], "balance": ["Balance"]})


def test_juliet_single_signed_amount_column_and_reverse_order():
    def jrow(top, date, narr, amt, bal):
        return [w(date, 30, top), w(narr, 120, top), rt(amt, 400, top), rt(bal, 560, top)]
    ws = list(ALPHA_PERIOD) + header(JULIET)
    ws += jrow(220, "02-04-2022", "SALARY", "1,000.00 (Cr)", "1,900.00 (Cr)")       # newest first
    ws += jrow(237, "01-04-2022", "SHOP", "100.00 (Dr)", "900.00 (Cr)")
    out = extract_pages([Page(ws, W)], JULIET)
    assert [r.txn.date for r in out.rows] == ["2022-04-01", "2022-04-02"]
    assert out.rows[0].txn.debit == Decimal("100.00") and out.rows[1].txn.credit == Decimal("1000.00")
    assert out.checks.results["chain"].status == "pass", out.checks.reasons


# ---------------------------------------------------------------- KILO: single amount column, Dr/Cr marker prints in
# a separate column between amount and balance (side_marker_column scans the text band that absorbs it)
KILO = replace(ALPHA, layout_id="kilo", bank_key="kilo", single_amount_column="amount", side_marker_column="narration",
               debit_column="amount_dr", credit_column="amount_cr",
               columns={"date": (("date",),), "narration": (("remarks",),),
                        "amount": (("amount",),), "balance": (("balance",),)},
               amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
               summary_marker="", summary_label_text="", summary_expected=False)
GEO["kilo"] = dict(text={"date": 30, "narration": 120}, money={"amount": 300, "balance": 400},
                   titles={"date": ["Date"], "amount": ["Amount"], "balance": ["Balance"], "narration": ["Remarks"]})


def test_kilo_side_marker_column_supplies_dr_cr_for_a_bare_amount():
    def krow(top, date, amt, marker, bal, narr="UPI"):
        ws = [w(date, 30, top), rt(amt, 300, top), rt(bal, 400, top), w(narr, 430, top)]
        if marker:
            ws.append(w(marker, 330, top))
        return ws
    ws = list(ALPHA_PERIOD) + header(KILO)
    ws += krow(220, "01-04-2022", "100.00", "Cr", "1,100.00")
    ws += krow(237, "02-04-2022", "50.00", "Dr", "1,050.00")
    ws += krow(254, "03-04-2022", "10.00", "", "1,060.00")          # no marker: row must be rejected, not guessed
    out = extract_pages([Page(ws, W)], KILO)
    assert len(out.rows) == 2 and out.schema_errors, out.schema_errors
    assert out.rows[0].txn.credit == Decimal("100.00") and out.rows[1].txn.debit == Decimal("50.00")
    assert out.checks.results["chain"].status == "pass", out.checks.reasons


def test_continuation_amounts_fill_a_dated_rows_empty_money_cells():
    spec = replace(ALPHA, continuation_amounts=True)
    ws = list(ALPHA_PERIOD) + header(ALPHA)
    ws += [w("01-04-2022", 30, 220), w("SALARY", 120, 220)]                                   # date + narration only
    ws += [w("BY TRANSFER", 120, 237), rt("1,000.00", 470, 237), rt("1,900.00", 560, 237)]    # money on wrap line
    ws += [w("02-04-2022", 30, 254), w("SHOP", 120, 254), rt("100.00", 400, 254), rt("1,800.00", 560, 254)]
    out = extract_pages([Page(ws, W)], spec)
    assert len(out.rows) == 2, out.schema_errors
    assert out.rows[0].txn.credit == Decimal("1000.00") and out.rows[1].txn.debit == Decimal("100.00")
    assert out.checks.results["chain"].status == "pass", out.checks.reasons


def test_open_row_survives_carried_forward_and_fills_on_next_page():
    # HSBC-style: a page ends on a date+narration line whose money sits past the break, then
    # "Balance Carried Forward" + legal footer; page 2 opens with "Balance Brought Forward" and
    # the open row's amount/balance line. The open row must not strand (missing balance) and the
    # footer must never land in its narration.
    spec = replace(ALPHA, continuation_amounts=True, undated_rows_inherit_date=True,
                   carry_forward_re=re.compile(r"(?i)balance(?:brought|carried)forward"),
                   closing_balance_re=re.compile(r"(?i)balancecarriedforward([\d,]+\.\d{2})"))
    p1 = [w("Period:", 30, 170), w("01-04-2022", 80, 170), w("to", 150, 170), w("30-04-2022", 165, 170)] + header(ALPHA)
    p1 += [w("01-04-2022", 30, 220), w("SHOP", 120, 220), rt("100.00", 400, 220), rt("900.00", 560, 220)]
    p1 += [w("02-04-2022", 30, 237), w("UPI-TRANSFER", 120, 237)]                              # open row: no money yet
    p1 += [w("Balance", 120, 254), w("Carried", 170, 254), w("Forward", 225, 254), rt("1,700.00", 560, 254)]
    p1 += [w("The", 30, 271), w("Hongkong", 60, 271), w("Banking", 130, 271), w("Corporation", 195, 271)]
    p2 = [w("Period:", 30, 170), w("01-04-2022", 80, 170), w("to", 150, 170), w("30-04-2022", 165, 170)] + header(ALPHA)
    p2 += [w("Balance", 120, 220), w("Brought", 170, 220), w("Forward", 220, 220), rt("1,700.00", 560, 220)]
    p2 += [rt("800.00", 470, 237), rt("1,700.00", 560, 237)]                                   # open row's money line
    p2 += [w("03-04-2022", 30, 254), w("RENT", 120, 254), rt("200.00", 400, 254), rt("1,500.00", 560, 254)]
    p2 += alpha_summary(400, "300.00", "800.00", "1,500.00")
    out = extract_pages([Page(p1, W), Page(p2, W)], spec)
    assert len(out.rows) == 3, out.schema_errors
    assert out.rows[1].txn.credit == Decimal("800.00") and out.rows[1].txn.balance == Decimal("1700.00")
    assert out.rows[1].txn.date == "2022-04-02" and out.rows[1].txn.description == "UPI-TRANSFER"
    assert all("Hongkong" not in r.txn.description for r in out.rows)
    assert out.checks.results["chain"].status == "pass", out.checks.reasons


def test_brought_forward_line_does_not_truncate_the_page():
    # a page-TOP "Balance Brought Forward" that also matches closing_balance_re must seed a
    # checkpoint and keep scanning — never break and lose the rows below it.
    spec = replace(ALPHA, continuation_amounts=True, undated_rows_inherit_date=True,
                   carry_forward_re=re.compile(r"(?i)balance(?:brought|carried)forward"),
                   closing_balance_re=re.compile(r"(?i)balance(?:brought|carried)forward([\d,]+\.\d{2})"))
    p1 = ALPHA_PERIOD + header(ALPHA)
    p1 += [w("01-04-2022", 30, 220), w("SHOP", 120, 220), rt("100.00", 400, 220), rt("900.00", 560, 220)]
    p2 = ALPHA_PERIOD + header(ALPHA)
    p2 += [w("Balance", 120, 220), w("Brought", 170, 220), w("Forward", 220, 220), rt("900.00", 560, 220)]
    p2 += [w("02-04-2022", 30, 237), w("SALARY", 120, 237), rt("1,000.00", 470, 237), rt("1,900.00", 560, 237)]
    p2 += alpha_summary(400, "100.00", "1,000.00", "1,900.00")
    out = extract_pages([Page(p1, W), Page(p2, W)], spec)
    assert len(out.rows) == 2, out.schema_errors
    assert out.rows[1].txn.credit == Decimal("1000.00") and out.rows[1].txn.balance == Decimal("1900.00")
    assert out.checks.results["chain"].status == "pass", out.checks.reasons


LIMA = replace(ALPHA, layout_id="lima", bank_key="lima", left_aligned_amounts=True,
               columns={"date": (("date",),), "narration": (("particulars",),),
                        "debit": (("withdrawals",),), "credit": (("deposits",),), "balance": (("balance",),)})
GEO["lima"] = dict(text={"date": 10, "narration": 79}, money={"debit": 442, "credit": 491, "balance": 560},
                   titles={"date": ["Date"], "narration": ["Particulars"], "debit": ["Withdrawals"], "credit": ["Deposits"], "balance": ["Balance"]})


def test_left_aligned_amounts_assign_money_by_the_column_left_edge():
    # CSB-style statements print money left-aligned under its (wider) column title, so right-edge banding misses it
    ws = list(ALPHA_PERIOD) + header(LIMA)
    ws += [w("01-04-2022", 10, 220), w("DEBIT UPI", 79, 220), w("50.00", 381.5, 220), w("100.00", 521.5, 220)]
    ws += [w("02-04-2022", 10, 237), w("CREDIT UPI", 79, 237), w("70.00", 447.0, 237), w("170.00", 521.5, 237)]
    out = extract_pages([Page(ws, W)], LIMA)
    assert len(out.rows) == 2, out.schema_errors
    assert out.rows[0].txn.debit == Decimal("50.00") and out.rows[1].txn.credit == Decimal("70.00")
    assert out.checks.results["chain"].status == "pass", out.checks.reasons
    same_words_no_flag = extract_pages([Page(ws, W)], replace(LIMA, left_aligned_amounts=False))
    assert len(same_words_no_flag.rows) < 2


def test_amount_sign_gap_collapses_space_between_sign_and_digits():
    spec = replace(ALPHA, amount_sign_gap=True, amount_re=re.compile(r"^[+-]?[\d,]+\.\d{2}$"))
    from app.services.statement_engine.extraction.engine import _prepare_amounts
    words = [Word("-  4,928.58", 545, 578, 100, 108), w("+", 380, 100), w("1,000.00", 390, 100)]
    got = [x.text for x in _prepare_amounts(words, spec)]
    assert got == ["-4,928.58", "+", "1,000.00"]


def test_zero_amount_is_empty_pairs_the_side_with_the_value():
    spec = replace(ALPHA, zero_amount_is_empty=True)
    from app.services.statement_engine.extraction.rows import RawRow
    rows = [RawRow(page=1, top=1, date="01-04-2022", narration_lines=["X"], amounts={"debit": "5.0", "credit": "0.0", "balance": "95.00"})]
    from app.services.statement_engine.extraction.normalize import normalize_rows
    out, errs = normalize_rows(rows, spec)
    assert not errs and out[0].txn.debit == Decimal("5.0") and out[0].txn.credit is None


def test_currency_prefix_and_standalone_sign_word_form_one_signed_amount():
    spec = replace(JULIET, amount_prefix="Rs.|₹", merge_sign_prefix=True, amount_re=re.compile(r"^[+-]?[\d,]+\.\d{2}$"))
    from app.services.statement_engine.extraction.engine import _prepare_amounts
    words = [w("+", 380, 100), w("Rs.2,318.00", 390, 100), Word("- ₹300.00", 380, 440, 120, 128), w("₹702.00", 500, 120)]
    got = [x.text for x in _prepare_amounts(words, spec)]
    assert got == ["+2,318.00", "-300.00", "702.00"]


def test_date_prefix_split_never_cuts_inside_a_longer_date():
    from app.services.statement_engine.extraction.engine import _split_merged_dates
    spec = replace(ALPHA, date_re=re.compile(r"^\d{2}/\d{2}/\d{2}$"), date_format="%d/%m/%y")
    assert [x.text for x in _split_merged_dates([w("01/04/2023", 30, 100)], spec)] == ["01/04/2023"]
    assert [x.text for x in _split_merged_dates([w("01/04/23DEBIT", 30, 100)], spec)] == ["01/04/23", "DEBIT"]


# ---------------------------------------------------------------- merge_statements (several statements in one PDF)
def _two_statements(second_rows, second_extra=None, second_header=True):
    shop = drow(230, "5 Jan 2023", "5 Jan 2023", "SHOP", debit="100.00", balance="900.00")
    p1 = delta_page([shop], extra=DELTA_TOP)
    foot = Page([w("This is a computer generated statement", 36, 100)], 595.0)
    p3 = delta_page(second_rows, with_header=second_header, extra=second_extra)
    return [p1, foot, p3]


def _bill(balance="850.00"):
    return drow(230, "6 Jan 2023", "6 Jan 2023", "BILL", debit="50.00", balance=balance)


def test_merge_statements_contiguous_second_statement_is_merged_and_verified():
    spec = replace(DELTA, merge_statements=True)
    out = extract_pages(_two_statements([_bill()]), spec)
    assert [r.txn.description for r in out.rows] == ["SHOP", "BILL"]
    assert not any(x.startswith("additional_statement") for x in out.warnings)
    assert out.checks.results["chain"].status == "pass", out.checks.reasons


def test_merge_statements_overlapping_tail_is_deduplicated():
    spec = replace(DELTA, merge_statements=True)
    shop = drow(230, "5 Jan 2023", "5 Jan 2023", "SHOP", debit="100.00", balance="900.00")
    bill = drow(250, "6 Jan 2023", "6 Jan 2023", "BILL", debit="50.00", balance="850.00")
    out = extract_pages(_two_statements([shop, bill]), spec)
    assert [r.txn.description for r in out.rows] == ["SHOP", "BILL"]
    assert any("overlap_rows=1" in n for n in out.notes)


def test_merge_statements_gap_stays_review_and_returns_first_statement_only():
    spec = replace(DELTA, merge_statements=True)
    out = extract_pages(_two_statements([_bill(balance="5.00")]), spec)
    assert len(out.rows) == 1 and out.checks.verdict == "REVIEW"
    assert any(x.startswith("additional_statement") for x in out.warnings)


def test_merge_statements_empty_following_statement_leaves_first_verified():
    spec = replace(DELTA, merge_statements=True)
    out = extract_pages(_two_statements([]), spec)
    assert len(out.rows) == 1 and not any(x.startswith("additional_statement") for x in out.warnings)
    assert out.checks.verdict != "FAILED"


def test_merge_statements_headerless_following_rows_stay_review():
    spec = replace(DELTA, merge_statements=True)
    out = extract_pages(_two_statements([_bill()], second_header=False), spec)
    assert len(out.rows) == 1 and out.checks.verdict == "REVIEW"


def test_merge_statements_different_account_is_not_merged():
    spec = replace(DELTA, merge_statements=True)
    other = [w("Account", 36, 60), w("Number", 80, 60), w(":", 130, 60), w("99999999999", 140, 60)]
    out = extract_pages(_two_statements([_bill()], second_extra=other), spec)
    assert len(out.rows) == 1 and out.checks.verdict == "REVIEW"


def test_merge_statements_is_off_by_default():
    out = extract_pages(_two_statements([_bill()]), DELTA)
    assert len(out.rows) == 1 and any(x.startswith("additional_statement") for x in out.warnings)


# ---------------------------------------------------------------- monospace text pages, inline page breaks, balance-only opening row
def _line(top, text):
    return Word(text, 57.0, 57.0 + 5.0 * len(text), top, top + 9)


def _mono_page(lines, start_top=100.0):
    return Page([_line(start_top + 11 * i, t) for i, t in enumerate(lines)], 595.0)


_MONO_HEADER = "DATE     PARTICULARS    CHQ.NO.      WITHDRAWALS        DEPOSITS         BALANCE"
MONO = replace(
    ALPHA, layout_id="mono", bank_key="mono", bank_name="Mono Bank", monospace_text=True, opening_row_balance_only=True,
    page_break_re=re.compile(r"^PageTotal:"), ignore_line_res=(re.compile(r"^-{10,}$"),),
    columns={"date": (("date",),), "narration": (("particulars",),), "ref": (("chqno",),), "debit": (("withdrawals",),),
             "credit": (("deposits",),), "balance": (("balance",),)},
    text_columns=("date", "narration", "ref"), date_re=re.compile(r"^\d{2}-\d{2}-\d{2}$"), date_format="%d-%m-%y",
    period_re=re.compile(r"(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"), summary_marker="NOSUMMARYMARKER", summary_label_text="x",
    summary_fields=(), summary_expected=False, header_repeats=True, account_label="a/cnumber")


def _mono_row(date, narr, debit="", credit="", bal=""):
    return f"{date} {narr:<14}{'':<10}{debit:>11}{'':<8}{credit:>11}{'':<6}{bal:>12}"


def test_monospace_split_places_each_piece_by_character_offset():
    from app.services.statement_engine.extraction.engine import _split_monospace
    got = _split_monospace([Word("AB   CD", 10.0, 17.0, 0, 8)])
    assert [x.text for x in got] == ["AB", "CD"] and abs(got[1].x0 - 15.0) < 1e-6


def test_monospace_page_with_inline_page_break_keeps_rows_on_both_sides_and_balance_only_opening():
    p1 = _mono_page(["Statement of account for the period of 01-04-2022 to 30-04-2022", "-" * 80, _MONO_HEADER, "-" * 80,
                     _mono_row("01-04-22", "B/F", bal="1,000.00"),
                     _mono_row("02-04-22", "SHOP", debit="100.00", bal="900.00"),
                     "-" * 80, "Page Total:", "Statement of account for the period of 01-04-2022 to 30-04-2022", "-" * 80, _MONO_HEADER, "-" * 80,
                     _mono_row("03-04-22", "BILL", debit="50.00", bal="850.00")])
    out = extract_pages([p1], MONO)
    assert out.failure is None and [r.txn.description for r in out.rows] == ["SHOP", "BILL"]
    assert out.checks.results["chain"].status == "pass", out.checks.reasons


# ---------------------------------------------------------------- registry resolution: bank anchoring and ambiguity
def _shared_header_registry():
    a1 = replace(ALPHA, layout_id="shared_a", bank_key="bank_a", bank_markers=("ALPHABANK",))
    a2 = replace(ALPHA, layout_id="shared_b", bank_key="bank_b", bank_markers=("BRAVOBANK",))
    return LayoutRegistry([a1, a2])


def _page_with_banner(banner):
    return Page(([w(banner, 30, 40)] if banner else []) + header(ALPHA, 100.0), W)


def test_resolve_refuses_a_header_when_the_page_names_another_bank():
    reg = LayoutRegistry([replace(ALPHA, layout_id="only_a", bank_key="bank_a", bank_markers=("ALPHABANK",)),
                          replace(BETA, layout_id="only_b", bank_key="bank_b", bank_markers=("BRAVOBANK",))])
    res = reg.resolve([_page_with_banner("BRAVOBANK")])
    assert res.spec is None and res.status == "foreign_bank" and res.rejected == ["only_a"]


def test_resolve_prefers_the_layout_whose_bank_is_named_on_a_shared_header():
    res = _shared_header_registry().resolve([_page_with_banner("BRAVOBANK")])
    assert res.status == "resolved" and res.spec.layout_id == "shared_b" and "shared_a" in res.candidates


def test_resolve_shared_header_without_any_bank_name_is_ambiguous_not_first_registered():
    res = _shared_header_registry().resolve([_page_with_banner("")])
    assert res.spec is None and res.status == "ambiguous"


def test_resolve_accepts_a_page_that_names_no_bank_when_only_one_layout_matches():
    reg = LayoutRegistry([replace(ALPHA, layout_id="only_a", bank_key="bank_a", bank_markers=("ALPHABANK",))])
    assert reg.resolve([_page_with_banner("")]).spec.layout_id == "only_a"


def test_resolve_prefers_primary_header_spelling_over_a_fallback_alternative():
    loose = replace(ALPHA, layout_id="loose", bank_key="bank_b", columns={**ALPHA.columns, "narration": (("zzz",), ("particulars",))})
    res = LayoutRegistry([loose, replace(ALPHA, layout_id="exact", bank_key="bank_a")]).resolve([_page_with_banner("")])
    assert res.status == "resolved" and res.spec.layout_id == "exact"


_NO_TEXT_BRAND = {"pnb", "yes", "iob", "south_indian", "bandhan"}   # banks whose brand never prints in the text layer; routing relies on the detector
# (bandhan's Current-and-Savings exports print no brand; the BDBL ifsc_re in the account block is the own-bank evidence)


def test_default_registry_every_layout_names_its_bank_and_markers_do_not_collide():
    owners = {}
    for sp in DEFAULT_REGISTRY.specs():
        assert sp.bank_markers or sp.bank_key in _NO_TEXT_BRAND, sp.layout_id
        for m in sp.bank_markers:
            assert owners.setdefault(m, sp.bank_key) == sp.bank_key, (m, sp.layout_id)


def test_default_registry_older_icici_header_is_icici_not_canara():
    spec = DEFAULT_REGISTRY.get("icici_date_mode_particulars_deposits_withdrawals_balance")
    assert spec.bank_key == "icici" and not any(s.bank_key == "canara" and s.columns.keys() == spec.columns.keys() for s in DEFAULT_REGISTRY.specs())


# ---------------------------------------------------------------- undated rows, carried-forward balance, repeated credit-first totals
def test_parse_date_accepts_alternative_spellings():
    from app.services.statement_engine.extraction.normalize import parse_date
    assert parse_date("05 Jan 23", "%d %b %y|%d %b %Y") == parse_date("05 Jan 2023", "%d %b %y|%d %b %Y") == "2023-01-05"


def test_undated_rows_carry_forward_lines_and_repeated_credit_first_totals():
    spec = replace(MONO, undated_rows_inherit_date=True, carry_forward_re=re.compile(r"BALANCEFORWARD"), opening_row_balance_only=True,
                   totals_line_re=re.compile(r"^TOTAL([\d,]+\.\d{2})([\d,]+\.\d{2})([\d,]+\.\d{2})$"), totals_credit_first=True, totals_accumulate=True)
    pg = _mono_page(["Statement of account for the period of 01-04-2022 to 30-04-2022", "-" * 80, _MONO_HEADER, "-" * 80,
                     _mono_row("01-04-22", "OPENING", bal="1,000.00"),
                     _mono_row("02-04-22", "SHOP", debit="100.00", bal="900.00"),
                     _mono_row("        ", "SHOP2", debit="50.00", bal="850.00"),
                     "TOTAL        0.00        150.00        850.00",
                     _mono_row("02-04-22", "BALANCE FORWARD", bal="850.00"),
                     _mono_row("        ", "SHOP3", credit="25.00", bal="875.00"),
                     "TOTAL       25.00          0.00        875.00"])
    out = extract_pages([pg], spec)
    assert out.failure is None, out.failure_detail
    assert [r.txn.description for r in out.rows] == ["SHOP", "SHOP2", "SHOP3"] and {r.txn.date for r in out.rows} == {"2022-04-02"}
    assert out.summary.debits == Decimal("150.00") and out.summary.credits == Decimal("25.00") and out.summary.closing == Decimal("875.00")
    assert out.checks.verdict == "VERIFIED", out.checks.reasons


def test_empty_amount_marker_in_a_money_cell_is_empty_not_narration():
    spec = replace(ALPHA, empty_amount_marker="-", summary_expected=False)
    ws = list(ALPHA_PERIOD) + header(ALPHA)
    ws += [w("01-04-2022", 30, 220), w("SHOP", 120, 220), rt("-", 470, 220), rt("100.00", 400, 220), rt("900.00", 560, 220)]
    ws += [w("02-04-2022", 30, 237), w("PAY", 120, 237), rt("-", 400, 237), rt("50.00", 470, 237), rt("950.00", 560, 237)]
    out = extract_pages([Page(ws, W)], spec)
    assert [r.txn.description for r in out.rows] == ["SHOP", "PAY"]
    assert out.rows[0].txn.debit == Decimal("100.00") and out.rows[1].txn.credit == Decimal("50.00")
    assert out.checks.results["chain"].status == "pass", out.checks.reasons


def test_row_order_auto_reverses_only_when_the_chain_holds_newest_first():
    spec = replace(ALPHA, row_order="auto")
    def page(first, second):
        ws = list(ALPHA_PERIOD) + header(ALPHA)
        for top, (date, narr, dr, cr, bal) in zip((220, 237), (first, second)):
            ws += [w(date, 30, top), w(narr, 120, top)] + ([rt(dr, 400, top)] if dr else []) + ([rt(cr, 470, top)] if cr else []) + [rt(bal, 560, top)]
        return Page(ws, W)
    shop, pay = ("01-04-2022", "SHOP", "100.00", None, "900.00"), ("02-04-2022", "PAY", None, "50.00", "950.00")
    fwd = extract_pages([page(shop, pay)], spec)
    rev = extract_pages([page(pay, shop)], spec)
    assert [r.txn.description for r in fwd.rows] == ["SHOP", "PAY"] and [r.txn.description for r in rev.rows] == ["SHOP", "PAY"]
    assert "row_order:reversed" in rev.notes and "row_order:reversed" not in fwd.notes
    bad = extract_pages([page(("01-04-2022", "SHOP", "100.00", None, "900.00"), ("02-04-2022", "PAY", None, "50.00", "999.00"))], spec)
    assert "row_order:reversed" not in bad.notes and bad.checks.verdict != "VERIFIED"


def test_year_from_period_picks_the_year_inside_the_period():
    from types import SimpleNamespace
    from app.services.statement_engine.extraction.engine import _add_years
    from app.services.statement_engine.extraction.rows import RawRow
    spec = SimpleNamespace(period_date_format="%d%b%Y", date_format="%b %d %Y")
    rows = [RawRow(page=1, top=0, date="Dec 30", value_date="Dec 31"), RawRow(page=1, top=1, date="Jan 02")]
    _add_years(rows, ("15Nov2024", "15Feb2025"), spec)
    assert (rows[0].date, rows[0].value_date, rows[1].date) == ("Dec 30 2024", "Dec 31 2024", "Jan 02 2025")
    rows = [RawRow(page=1, top=0, date="Dec 30")]
    _add_years(rows, None, spec)          # no period: left as printed
    assert rows[0].date == "Dec 30"


def test_wrapped_amount_tokens_join_a_money_cell_split_mid_number():
    # a money cell too wide for its column prints its tail on the row's continuation line: "1,000.0" + "0"
    spec = replace(ALPHA, wrapped_amount_tokens=True)
    ws = list(ALPHA_PERIOD) + header(ALPHA)
    ws += [w("01-04-2022", 30, 220), w("SALARY", 120, 220), rt("1,000.0", 470, 220), rt("1,900.00", 560, 220)]
    ws += [w("0", 469, 237)]
    ws += [w("02-04-2022", 30, 254), w("SHOP", 120, 254), rt("100.00", 400, 254), rt("1,800.00", 560, 254)]
    out = extract_pages([Page(ws, W)], spec)
    assert len(out.rows) == 2, out.schema_errors
    assert out.rows[0].txn.credit == Decimal("1000.00") and out.rows[1].txn.debit == Decimal("100.00")
    assert out.checks.results["chain"].status == "pass", out.checks.reasons
    # flag off: the cut token must not be guessed, the row stays schema-broken
    off = extract_pages([Page(ws, W)], ALPHA)
    assert len(off.rows) < 2 or off.schema_errors


def test_side_marker_on_continuation_line_supplies_the_side_of_a_wrapped_amount():
    # a row whose money cell and Dr/Cr marker sit on the undated wrap line still gets its side
    spec = LayoutSpec(
        layout_id="sigma", bank_key="sigma", bank_name="Sigma Bank",
        columns={"date": (("date",),), "narration": (("description",),), "ref": (("ref",),),
                 "amount": (("amount",),), "drcr": (("drcr",), ("dr", "cr")), "balance": (("balance",),)},
        text_columns=("date", "narration", "ref", "drcr"),
        debit_column="amount_dr", credit_column="amount_cr",
        single_amount_column="amount", side_marker_column="drcr", balance_column="balance",
        continuation_amounts=True, band_left_pad={"drcr": 130.0},
        date_re=re.compile(r"^\d{2}-\d{2}-\d{4}$"), date_format="%d-%m-%Y",
        amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?:\s+(?i:cr|dr))?$"),
        period_re=re.compile(r"Period:(\d{2}-\d{2}-\d{4})to(\d{2}-\d{2}-\d{4})"), period_date_format="%d-%m-%Y",
        summary_marker="", summary_label_text="", header_repeats=True)
    ws = [w("Period : 01-04-2022 to 05-04-2022", 20, 70)]
    ws += [w("Date", 20, 50), w("Description", 80, 50), w("Ref", 210, 50), w("Amount", 300, 50),
           w("Dr / Cr", 380, 50), w("Balance", 460, 50)]
    ws += [w("01-04-2022", 20, 100), w("SALARY", 80, 100), w("R1", 210, 100), rt("1,000.00", 330, 100),
           w("CR", 380, 100), rt("1,900.00", 490, 100)]
    ws += [w("02-04-2022", 20, 124), w("SHOP", 80, 124), w("R2", 210, 124), rt("1,800.00", 490, 124)]
    ws += [w("at counter", 80, 141), rt("100.00", 330, 141), w("DR", 380, 141)]
    out = extract_pages([Page(ws, W)], spec)
    assert len(out.rows) == 2, out.schema_errors
    assert out.rows[1].txn.debit == Decimal("100.00"), out.rows[1].txn
    assert out.checks.results["chain"].status == "pass", out.checks.reasons


def test_drcr_suffix_decoration_strips_redundant_side_words_on_split_columns():
    # "220.00 DR" printed as one cell in the debit column: the suffix only restates the column
    spec = replace(ALPHA, drcr_suffix_decoration=True,
                   amount_re=re.compile(r"^-?[\d,]+\.\d{2}\s*(?i:(?:cr|dr))?\.?$"))
    ws = list(ALPHA_PERIOD) + header(ALPHA)
    ws += [w("01-04-2022", 30, 220), w("SALARY", 120, 220), rt("1,000.00 CR", 470, 220), rt("1,900.00 CR", 560, 220)]
    ws += [w("02-04-2022", 30, 254), w("SHOP", 120, 254), rt("100.00 DR", 400, 254), rt("1,800.00 CR", 560, 254)]
    out = extract_pages([Page(ws, W)], spec)
    assert len(out.rows) == 2, out.schema_errors
    assert out.rows[0].txn.credit == Decimal("1000.00") and out.rows[1].txn.debit == Decimal("100.00")
    assert out.checks.results["chain"].status == "pass", out.checks.reasons


def test_date_outlier_check_flags_an_isolated_row_only():
    from types import SimpleNamespace
    from app.services.statement_engine.extraction.checks import check_date_outliers
    mk = lambda ds: [SimpleNamespace(txn=SimpleNamespace(date=d)) for d in ds]          # noqa: E731
    base = ["2024-01-02", "2024-01-05", "2024-01-09", "2024-01-15", "2024-01-20"]
    assert check_date_outliers(mk(base)).status == "pass"
    shifted = base[:2] + ["2025-01-09"] + base[3:]                       # one row a year off, neighbours agree
    assert check_date_outliers(mk(shifted)).status == "warn"
    assert check_date_outliers(mk(["2025-01-02"] + base[1:])).status == "warn"          # first row
    assert check_date_outliers(mk(base[:4] + ["2025-01-20"])).status == "warn"          # last row
    quiet = ["2024-01-02", "2024-01-05", "2024-06-01", "2024-06-04", "2024-06-09"]      # a quiet spell is not an outlier
    assert check_date_outliers(mk(quiet)).status == "pass"
    assert check_date_outliers(mk(base[:2])).status == "skipped"


# ---------------------------------------------------------------- CLIP: balance cells clipped at the page edge print "…C"/"…D" instead of
# "…Cr"/"…Dr" (the Indian Bank post/remitter family). Opt-in field; the chain still proves every value.
CLIP = replace(ALPHA, layout_id="clip", bank_key="clip",
               amount_re=re.compile(r"^-?[\d,]+\.\d{2}(?: ?(?:Cr|Dr|C|D))?$"), clipped_drcr_suffix=True)
GEO["clip"] = GEO["alpha"]


def test_clipped_drcr_suffix_reads_page_edge_balance_markers():
    assert parse_amount("750041.02C", suffix_sign=True, clipped_sign=True) == Decimal("750041.02")
    assert parse_amount("100.00D", suffix_sign=True, clipped_sign=True) == Decimal("-100.00")
    assert parse_amount("100.00(Dr)", suffix_sign=True, clipped_sign=True) == Decimal("-100.00")   # full suffix still wins
    rows = [row(CLIP, 220, "01-04-2022", "SHOP", debit="100.00", balance="900.00C"),
            row(CLIP, 237, "02-04-2022", "SALARY", credit="1,000.00", balance="1,900.00C"),
            row(CLIP, 254, "03-04-2022", "FEE", debit="2,000.00", balance="100.00D")]
    out = extract_pages([page(CLIP, rows, ALPHA_PERIOD, alpha_summary(400, "2,100.00", "1,000.00", "-100.00"))], CLIP)
    assert out.checks.verdict == "VERIFIED", out.checks.reasons
    assert [r.txn.balance for r in out.rows] == [Decimal("900.00"), Decimal("1900.00"), Decimal("-100.00")]


def test_clipped_drcr_suffix_is_opt_in():
    rows = [row(CLIP, 220, "01-04-2022", "SHOP", debit="100.00", balance="900.00C"),
            row(CLIP, 237, "02-04-2022", "SALARY", credit="1,000.00", balance="1,900.00C")]
    out = extract_pages([page(CLIP, rows, ALPHA_PERIOD, alpha_summary(400, "100.00", "1,000.00", "1,900.00"))],
                        replace(CLIP, clipped_drcr_suffix=False))
    assert out.checks.verdict != "VERIFIED"


def test_add_years_keeps_tail_completed_dates():
    """year_from_period + date_tail: a continuation token that already carries the year is not appended again,
    and a bare dd/mm still gets the year that lands inside the printed period (cross-year periods included)."""
    from types import SimpleNamespace
    from app.services.statement_engine.extraction.engine import _add_years
    spec = SimpleNamespace(date_format="%d/%m %Y|%d/%m/ %Y", period_date_format="%d/%m/%Y")
    rows = [SimpleNamespace(date="31/03/ 2024", value_date=""), SimpleNamespace(date="15/01", value_date="")]
    _add_years(rows, ("01/10/2023", "31/03/2024"), spec)
    assert rows[0].date == "31/03/ 2024" and rows[1].date == "15/01 2024"
