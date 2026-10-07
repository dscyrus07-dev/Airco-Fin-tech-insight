"""Comparator tests on controlled fixtures. No PDFs, no V2 extractor."""
from decimal import Decimal as D

import pytest

from app.services.migration import (
    ComparatorConfig, ContractError, CorpusItem, Diff, ExtractionResult, run_parity, compare_results,
)
from app.services.pipeline.models import NormalizedTransaction as T, StatementMetadata as M


def meta(**kw):
    base = dict(bank_name="HDFC Bank", bank_key="hdfc", account_number="1234", opening_balance=D("1000"),
                closing_balance=D("1150"), statement_from="2025-01-01", statement_to="2025-01-31")
    base.update(kw)
    return M(**base)


def txns():
    return [
        T(date="2025-01-02", description="UPI/ABC", debit=D("100"), balance=D("900")),
        T(date="2025-01-05", description="SALARY", credit=D("500"), balance=D("1400")),
        T(date="2025-01-09", description="ATM WDL", debit=D("250"), balance=D("1150")),
    ]


def res(engine="old", m=None, t=None, **kw):
    return ExtractionResult(engine=engine, metadata=m or meta(), transactions=t if t is not None else txns(), **kw)


def cmp(old, new, **kw):
    return compare_results("f1", "hdfc", old, new, **kw)


def codes(r):
    return {f.code for f in r.findings}


def test_identical_is_exact_match():
    r = cmp(res(), res("v2"))
    assert r.overall == Diff.EXACT_MATCH and r.findings == [] and r.exact
    assert r.opening_match and r.closing_match


def test_description_whitespace_and_case_is_not_a_difference():
    t = txns(); t[0].description = "  upi/abc "
    assert cmp(res(), res("v2", t=t)).overall == Diff.EXACT_MATCH


def test_description_change_is_minor():
    t = txns(); t[1].description = "SALARY JAN"
    r = cmp(res(), res("v2", t=t))
    assert r.overall == Diff.MINOR_DIFFERENCE and codes(r) == {"DESCRIPTION"}


def test_missing_transaction():
    r = cmp(res(), res("v2", t=txns()[:2]))
    assert r.overall == Diff.MAJOR_DIFFERENCE  # count + totals differ => major dominates
    assert "MISSING" in codes(r) and "TXN_COUNT" in codes(r)
    assert r.counts["MISSING_TRANSACTION"] == 1


def test_extra_transaction():
    t = txns() + [T(date="2025-01-10", description="X", debit=D("5"), balance=D("1145"))]
    r = cmp(res(), res("v2", t=t))
    assert "EXTRA" in codes(r) and r.counts["EXTRA_TRANSACTION"] == 1
    assert r.overall == Diff.MAJOR_DIFFERENCE


def test_wrong_side_is_major_amount_diff():
    t = txns(); t[0] = T(date="2025-01-02", description="UPI/ABC", credit=D("100"), balance=D("900"))
    r = cmp(res(), res("v2", t=t))
    assert "AMOUNT_DIFF" in codes(r) and r.overall == Diff.MAJOR_DIFFERENCE
    assert "DEBIT_COUNT" in codes(r) and "CREDIT_COUNT" in codes(r)


def test_row_balance_mismatch():
    t = txns(); t[2].balance = D("1149")
    r = cmp(res(), res("v2", t=t))
    assert "ROW_BALANCE" in codes(r) and r.counts.get("MISSING_TRANSACTION") is None
    assert r.overall == Diff.BALANCE_MISMATCH


def test_opening_and_closing_balance_mismatch():
    r = cmp(res(), res("v2", m=meta(opening_balance=D("999"), closing_balance=D("1151"))))
    assert r.overall == Diff.BALANCE_MISMATCH and not r.opening_match and not r.closing_match
    assert {"OPENING_BALANCE", "CLOSING_BALANCE"} <= codes(r)


def test_tolerance_is_strict_by_default_and_configurable():
    n = res("v2", m=meta(closing_balance=D("1150.01")))
    assert cmp(res(), n).overall == Diff.BALANCE_MISMATCH
    assert cmp(res(), n, cfg=ComparatorConfig(amount_tolerance=D("0.01"))).overall == Diff.EXACT_MATCH


def test_period_mismatch():
    r = cmp(res(), res("v2", m=meta(statement_to="2025-02-01")))
    assert r.overall == Diff.MAJOR_DIFFERENCE and "STATEMENT_TO" in codes(r)
    r2 = cmp(res(), res("v2", m=meta(statement_to="")))
    assert r2.overall == Diff.MINOR_DIFFERENCE


def test_bank_key_mismatch_is_major():
    assert cmp(res(), res("v2", m=meta(bank_key="sbi"))).overall == Diff.MAJOR_DIFFERENCE


def test_ordering_difference_is_minor():
    t = list(reversed(txns()))
    r = cmp(res(), res("v2", t=t))
    assert r.overall == Diff.MINOR_DIFFERENCE and codes(r) == {"ORDERING"}


def test_duplicates_counted():
    t = txns() + [txns()[0]]
    r = cmp(res(t=t), res("v2"))
    assert "DUPLICATES" in codes(r)
    assert cmp(res(t=t), res("v2", t=list(t))).overall == Diff.EXACT_MATCH


def test_printed_totals_checked_per_engine():
    r = cmp(res(printed_total_debit=D("350"), printed_total_credit=D("500")), res("v2", printed_total_debit=D("351")))
    assert "NEW_PRINTED_DEBIT" in codes(r) and "OLD_PRINTED_DEBIT" not in codes(r)


def test_verification_verdict_difference_is_major():
    r = cmp(res(verification_status="VERIFIED"), res("v2", verification_status="REVIEW"))
    assert r.overall == Diff.MAJOR_DIFFERENCE and "VERIFICATION" in codes(r)


def test_parser_failure_new_or_old():
    bad = res("v2", t=[], failure="NO_TRANSACTIONS")
    r = cmp(res(), bad)
    assert r.overall == Diff.PARSER_FAILURE and codes(r) == {"NEW_FAILED"}
    assert cmp(bad, res("v2")).overall == Diff.PARSER_FAILURE
    assert codes(cmp(bad, bad)) == {"OLD_FAILED", "NEW_FAILED"}


def test_contract_rejects_non_raw_stage():
    with pytest.raises(ContractError):
        cmp(res(), res("v2", stage="REPAIRED"))
    with pytest.raises(ContractError):
        res(t=txns(), failure="x").validate()


def test_comparison_is_deterministic():
    t = list(reversed(txns())); t[0].description = "changed"
    a = cmp(res(), res("v2", t=t)).to_dict()
    b = cmp(res(), res("v2", t=t)).to_dict()
    assert a == b


# ---- batch runner
class Fake:
    def __init__(self, name, by_path, boom=()):
        self.name, self.by_path, self.boom = name, by_path, set(boom)

    def extract(self, path, password=None):
        if path in self.boom:
            raise RuntimeError("kaboom")
        return self.by_path[path]


def test_run_parity_isolates_failures_and_reports():
    corpus = [CorpusItem("a", "a.pdf", "hdfc"), CorpusItem("b", "b.pdf", "hdfc"), CorpusItem("c", "c.pdf", "sbi")]
    old = Fake("old", {p: res() for p in ("a.pdf", "b.pdf", "c.pdf")})
    t = txns(); t[2].balance = D("1149")
    new = Fake("v2", {"a.pdf": res("v2"), "b.pdf": res("v2", t=t), "c.pdf": res("v2")}, boom={"c.pdf"})
    rep = run_parity(corpus, old, new)
    s = rep.summary()
    assert s["files"] == 3 and s["passed"] == 1 and s["failed"] == 2
    assert s["by_class"]["EXACT_MATCH"] == 1 and s["by_class"]["BALANCE_MISMATCH"] == 1 and s["by_class"]["PARSER_FAILURE"] == 1
    assert rep.by_bank() == {"hdfc": {"EXACT_MATCH": 1, "BALANCE_MISMATCH": 1}, "sbi": {"PARSER_FAILURE": 1}}
    md = rep.to_markdown()
    assert "Files tested: 3" in md and "kaboom" not in md.split("## Failures")[0]


def test_allow_minor_only_when_explicit():
    t = txns(); t[0].description = "other"
    corpus = [CorpusItem("a", "a.pdf", "hdfc")]
    old, new = Fake("old", {"a.pdf": res()}), Fake("v2", {"a.pdf": res("v2", t=t)})
    assert run_parity(corpus, old, new).summary()["passed"] == 0
    assert run_parity(corpus, old, new, allow_minor=True).summary()["passed"] == 1


def test_extractor_reconciled_printed_totals_are_not_flagged():
    # the extractor proved the printed totals reconcile (e.g. via the reversal rule): no PRINTED_* finding for it
    r = cmp(res(), res("v2", printed_total_debit=D("351"), printed_totals_reconciled=True))
    assert "NEW_PRINTED_DEBIT" not in codes(r)
    r2 = cmp(res(), res("v2", printed_total_debit=D("351"), printed_totals_reconciled=False))
    assert "NEW_PRINTED_DEBIT" in codes(r2)


def test_ignore_codes_gives_rows_only_view():
    from app.services.migration.comparator import LEGACY_METADATA_DEFECT_CODES
    new = res("v2", m=meta(closing_balance=D("1"), account_number="9"), verification_status="VERIFIED")
    old = res(verification_status="FAILED")
    assert cmp(old, new).overall != Diff.EXACT_MATCH
    assert cmp(old, new, cfg=ComparatorConfig(ignore_codes=LEGACY_METADATA_DEFECT_CODES)).overall == Diff.EXACT_MATCH
