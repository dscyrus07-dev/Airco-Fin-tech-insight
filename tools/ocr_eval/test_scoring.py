import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import scoring as s

GT = [{"date": "2026-04-01", "debit": "100.00", "credit": None, "balance": "900.00"},
      {"date": "2026-04-02", "debit": None, "credit": "50.00", "balance": "950.00"}]


def _ext(**over):
    rows = [dict(r) for r in GT]
    rows[0].update(over)
    return rows


def test_perfect():
    r = s.score_statement(GT, _ext())
    assert (r["amounts_total"], r["amounts_exact"], r["side_flips"], r["invented"], r["missing_rows"]) == (4, 4, 0, 0, 0)


def test_side_flip_counted_not_exact():
    r = s.score_statement(GT, _ext(debit=None, credit="100.00"))
    assert r["side_flips"] == 1 and r["amounts_exact"] == 3


def test_misread_digit_is_inexact_not_flip():
    r = s.score_statement(GT, _ext(debit="100.50"))
    assert r["side_flips"] == 0 and r["amounts_exact"] == 3


def test_invented_and_missing():
    ext = _ext() + [{"date": "2026-04-09", "debit": "1.00", "credit": None, "balance": "1.00"}]
    r = s.score_statement(GT, ext[:1] + ext[2:])
    assert r["invented"] == 1 and r["missing_rows"] == 1


def test_no_data_is_never_pass():
    agg = s.aggregate([])
    g = s.gate_report(agg, True)
    assert g["exact_amounts"]["result"] == "NO_DATA" and g["p95_seconds_per_page"]["result"] == "NO_DATA"


def test_percentile():
    assert s.percentile([1, 2, 3, 4, 5], 0.5) == 3 and s.percentile([], 0.5) is None
