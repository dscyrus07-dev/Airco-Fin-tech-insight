"""Shadow-readiness fixes: summary-less layouts cannot be VERIFIED on a self-derived chain (first-row blindness),
the shadow hook is fail-safe for unsupported modes, and no registered layout is header-only by default.
Plain functions (no pytest fixtures) so they also run in a bare interpreter."""
import inspect
import os
from decimal import Decimal

from app.services.pipeline.models import NormalizedTransaction
from app.services.statement_engine import shadow
from app.services.statement_engine.extraction.checks import run_checks
from app.services.statement_engine.extraction.normalize import NormalizedRow
from app.services.statement_engine.extraction.summary import PrintedSummary

D = Decimal


def _rows(spec):
    """spec: list of (date, debit, credit, balance) with a consistent chain."""
    out = []
    for d, dr, cr, bal in spec:
        t = NormalizedTransaction(date=d, description="X", debit=D(dr) if dr else None,
                                  credit=D(cr) if cr else None, balance=D(bal))
        out.append(NormalizedRow(txn=t, page=1, printed_side="debit" if dr else "credit", reversal=False,
                                 printed_kind="debit" if dr else "credit"))
    return out


# opening 1000: -100 -> 900, +50 -> 950, -200 -> 750, +25 -> 775
GOOD = [("2025-01-02", "100", None, "900"), ("2025-01-03", None, "50", "950"),
        ("2025-01-04", "200", None, "750"), ("2025-01-05", None, "25", "775")]
SUMMARY = PrintedSummary(opening=D("1000"), closing=D("775"))


def _run(rows, summary=None, summary_expected=False):
    return run_checks(rows, None, summary, [], [], summary_expected=summary_expected)


def test_summary_less_layout_is_capped_at_review_not_verified():
    for expected in (False, True):
        out = _run(_rows(GOOD), None, summary_expected=expected)
        assert out.verdict == "REVIEW", out.reasons
        assert any("anchor" in r or "no printed summary" in r for r in out.reasons)


def test_summary_less_reason_names_the_self_derived_chain():
    out = _run(_rows(GOOD), None, summary_expected=False)
    assert "no independent opening/closing anchor: balance chain is self-derived" in out.reasons


def test_independent_anchor_still_verifies():
    out = _run(_rows(GOOD), SUMMARY)
    assert out.verdict == "VERIFIED", out.reasons


def test_summary_printing_neither_opening_nor_closing_is_not_an_anchor():
    out = _run(_rows(GOOD), PrintedSummary(dr_count=2, cr_count=2, debits=D("300"), credits=D("75")))
    assert out.verdict == "REVIEW"


def _mut_first_amount(rows):
    r = rows[0].txn
    r.debit = r.debit + D("1")                      # row 0 amount +1, printed balance untouched
    return rows


def _mut_first_side(rows):
    r = rows[0].txn
    r.credit, r.debit = r.debit, None               # row 0 debit printed as credit
    return rows


def test_first_row_amount_mutation_is_never_verified():
    assert _run(_mut_first_amount(_rows(GOOD)), None).verdict != "VERIFIED"      # anchor-less: capped
    assert _run(_mut_first_amount(_rows(GOOD)), SUMMARY).verdict == "FAILED"     # anchored: caught


def test_first_row_side_mutation_is_never_verified():
    assert _run(_mut_first_side(_rows(GOOD)), None).verdict != "VERIFIED"
    assert _run(_mut_first_side(_rows(GOOD)), SUMMARY).verdict == "FAILED"


# ------------------------------------------------------------------ shadow hook fail-safe
class _Legacy:
    status = "success"
    transactions = []
    verification = {}


def _with_mode(value, fn):
    old = os.environ.get(shadow.MODE_ENV)
    os.environ[shadow.MODE_ENV] = value
    try:
        return fn()
    finally:
        if old is None:
            os.environ.pop(shadow.MODE_ENV, None)
        else:
            os.environ[shadow.MODE_ENV] = old


def test_v2_mode_accepts_serve_and_maps_garbage_to_off():
    # contract §1 (Wave 8): "serve" is a supported mode; unsupported values are logged and treated as off
    assert _with_mode("serve", shadow.v2_mode) == "serve"
    assert _with_mode("garbage", shadow.v2_mode) == "off"


def test_hook_is_failsafe_for_serve_and_garbage_modes():
    for bad in ("serve", "SERVE", "banana", "on", "1", ""):
        calls = []
        out = _with_mode(bad, lambda: shadow.run_v2_shadow("no/such.pdf", "alpha", _Legacy(), sink=calls.append))
        assert out is None and calls == [], bad          # no exception, no v2 work, no record


def test_hook_never_raises_when_sink_and_router_fail():
    old_route = shadow._v2_route
    shadow._v2_route = lambda p: (_ for _ in ()).throw(RuntimeError("boom"))

    def bad_sink(rec):
        raise OSError("sink down")

    try:
        out = _with_mode("shadow", lambda: shadow.run_v2_shadow("no/such.pdf", "alpha", _Legacy(), sink=bad_sink))
    finally:
        shadow._v2_route = old_route
    assert out is None


def test_orchestrator_wraps_the_shadow_hook():
    from app.services import pipeline_orchestrator as po
    src = inspect.getsource(po)
    i = src.index("run_v2_shadow(file_path")
    assert "try:" in src[max(0, i - 120):i] and "except Exception" in src[i:i + 400]


# ------------------------------------------------------------------ registry safety
def test_no_registered_layout_is_header_only_by_default():
    from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
    on = [s.layout_id for s in DEFAULT_REGISTRY.specs() if getattr(s, "header_only_ok", False)]
    assert on == [], on


def test_dead_sbi_layout_2_is_not_registered_and_l3_is_():
    from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
    ids = {s.layout_id for s in DEFAULT_REGISTRY.specs()}
    assert "sbi_date_details_debit_credit_balance" not in ids
    assert "sbi_date_details_refnocheque_debit_credit_balance" in ids
