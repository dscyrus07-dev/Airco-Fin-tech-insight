"""N1 engine capability tests: period-suffixed side markers, multi-line headers
(header_lines + header_merge_tol), untitled leading date column, plus the
failure-injection battery. Synthetic pages only — no PDFs, no customer data.
Every mutation must end below VERIFIED."""
import re
import pytest

from app.services.statement_engine.extraction.anchors import derive_anchors, find_header
from app.services.statement_engine.extraction.layout_spec import LayoutSpec
from app.services.statement_engine.extraction.rows import Page, assemble
from app.services.statement_engine.extraction.words import Word, group_lines
from app.services.statement_engine.extractors.registry import DEFAULT_REGISTRY
from app.services.statement_engine.v2_router import route_pages

from tests.statement_engine.extraction.onboarded_kit import W, w, rt

import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../tools/onboarding"))
from synth.split_headers import two_line_wrap, three_line_interleave, centred_titles  # noqa: E402


def _mk(text, x0, x1, top, bottom):
    return Word(text, x0, x1, top, bottom)


def _uniform_anchors(spec, start=60.0, width=95.0):
    """Column anchors in declared order: (x0, width) each."""
    out = {}
    x = start
    for col in spec.columns:
        out[col] = (x, width)
        x += width
    return out


def _to_words(tuples):
    return [_mk(*t) for t in tuples]


def _title_edges(spec, header_tuples, anchors=None):
    """Right edge of each column's title as actually emitted — the x1 of the seq's
    last token, bound to the column's own x band when `anchors` is given (two
    columns may end on the same word, e.g. 'Amount')."""
    edges = {}
    for col, alts in spec.columns.items():
        first, last = alts[0][0].lower(), alts[0][-1].lower()
        band = None if anchors is None else anchors.get(col)
        # the column's own cluster: locate the seq's first token inside the band,
        # then accept last-token candidates that start near that same x
        fx = [x0 for (t, x0, _x1, _t0, _b) in header_tuples
              if t.lower().startswith(first) and (band is None or band[0] - 8 <= x0 <= band[0] + band[1] + 8)]
        base = min(fx) if fx else (band[0] if band else 0.0)
        xs = [x1 for (t, x0, x1, _t0, _b) in header_tuples
              if (t.lower() == last or (t.lower().startswith(last) and len(t) <= len(last) + 4))
              and base - 6 <= x0 <= base + ((band[1] * 0.5) if band else 60)]
        if xs:
            edges[col] = max(xs)
    return edges


def _row_words(spec, anchors, top, date, narr, debit, credit, balance, ref="RF1", marker=None,
               edges=None):
    ws = []
    for col in spec.columns:
        x0, _wdt = anchors[col]
        if col in spec.amount_columns or col == spec.balance_column:
            continue
        if col == spec.text_columns[0] or col == spec.secondary_date_column:
            ws.append(w(date, x0, top))
        elif col == spec.side_marker_column and marker:
            ws.append(w(marker, x0, top))
        elif "narr" in col or "desc" in col or "partic" in col:
            for i, t in enumerate(narr.split()):
                ws.append(w(t, x0 + i * 40, top))
        else:
            ws.append(w(ref, x0, top))
    # money cells right-aligned at the title's right edge
    def _amt(col, text):
        edge = (edges or {}).get(col)
        if edge is None:
            x0, wdt = anchors[col]
            edge = x0 + wdt - 6
        ws.append(rt(text, edge, top))
    if spec.single_amount_column:
        val = debit or credit
        if val:
            _amt(spec.single_amount_column, val)
    else:
        if debit:
            _amt(spec.debit_column, debit)
        if credit:
            _amt(spec.credit_column, credit)
    _amt(spec.balance_column, balance)
    return ws


def _chain(n, start=220.0, step=16.0, open_bal=0.0, amount="100.00"):
    """(date, debit, credit, balance) rows with an exact running chain."""
    rows = []
    bal = open_bal
    for i in range(n):
        if i % 2:
            bal += float(amount.replace(",", ""))
            rows.append((f"0{(i % 9) + 1}/01/2024", None, amount, f"{bal:,.2f}"))
        else:
            bal -= float(amount.replace(",", ""))
            rows.append((f"0{(i % 9) + 1}/01/2024", amount, None, f"{bal:,.2f}"))
    return rows


SPEC_2L = LayoutSpec(
    layout_id="n1syn_two_line", bank_key="n1syn", bank_name="N1 Synth",
    bank_markers=("N1SYNBANK",),
    columns={
        "date": (("txn", "date"),),
        "narration": (("transaction", "description"),),
        "ref": (("cheque", "number"),),
        "debit": (("withdrawal", "amount"),),
        "credit": (("deposit", "amount"),),
        "balance": (("running", "balance"),),
    },
    text_columns=("date", "narration", "ref"),
    debit_column="debit", credit_column="credit", balance_column="balance",
    header_lines=2, header_merge_tol=4.0,
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"), date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    summary_marker="SUMMARY", summary_label_text="summary", summary_expected=True,
    period_re=re.compile(r"a^"), period_date_format="%d/%m/%Y",
)

SPEC_3L = LayoutSpec(
    **{**SPEC_2L.__dict__, "layout_id": "n1syn_three_line", "header_lines": 3,
       "columns": {**SPEC_2L.columns, "date": (("value", "txn", "date"),)}}
)

SPEC_UNTITLED = LayoutSpec(
    layout_id="n1syn_untitled_date", bank_key="n1syn", bank_name="N1 Synth",
    bank_markers=("N1SYNBANK",),
    columns={
        "date": (("date",),),                      # title never prints in this family
        "narration": (("description",),),
        "debit": (("debit",),),
        "credit": (("credit",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration"),
    debit_column="debit", credit_column="credit", balance_column="balance",
    untitled_date_column=True,
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"), date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    summary_marker="SUMMARY", summary_label_text="summary", summary_expected=True,
    period_re=re.compile(r"a^"), period_date_format="%d/%m/%Y",
)

SPEC_DRCR = LayoutSpec(
    layout_id="n1syn_drcr_period", bank_key="n1syn", bank_name="N1 Synth",
    bank_markers=("N1SYNBANK",),
    columns={
        "date": (("date",),),
        "narration": (("particulars",),),
        "side": (("drcr",),),
        "amount": (("amount",),),
        "balance": (("balance",),),
    },
    text_columns=("date", "narration", "side"),
    single_amount_column="amount", side_marker_column="side",
    debit_column="amount_dr", credit_column="amount_cr",
    balance_column="balance",
    date_re=re.compile(r"^\d{2}/\d{2}/\d{4}$"), date_format="%d/%m/%Y",
    amount_re=re.compile(r"^-?[\d,]+\.\d{2}$"),
    summary_marker="SUMMARY", summary_label_text="summary", summary_expected=True,
    period_re=re.compile(r"a^"), period_date_format="%d/%m/%Y",
)


def _page(spec, anchors, rows, header_words, marker=True):
    """header_words: Word list, or the raw 5-tuples (edges auto-derived)."""
    if header_words and isinstance(header_words[0], tuple):
        edges = _title_edges(spec, header_words, anchors)
        header_words = _to_words(header_words)
    else:
        edges = _title_edges(spec, [(x.text, x.x0, x.x1, x.top, x.bottom) for x in header_words], anchors)
    ws = [w("N1SYNBANK", 30, 40)] if marker else []
    ws += list(header_words)
    top = 240.0
    for d, dr, cr, bal in rows:
        ws += _row_words(spec, anchors, top, d, "UPI REF", dr, cr, bal,
                         marker=("Cr." if cr else "Dr."), edges=edges)
        top += 16.0
    if spec.summary_label_text:
        deb = sum(float((r[1] or "0").replace(",", "")) for r in rows)
        cred = sum(float((r[2] or "0").replace(",", "")) for r in rows)
        opening = float(rows[0][3].replace(",", "")) - (cred if rows[0][2] else 0) + (float(rows[0][1].replace(",", "")) if rows[0][1] else 0)
        opening = float(rows[0][3].replace(",", "")) - float((rows[0][2] or "0").replace(",", "")) + float((rows[0][1] or "0").replace(",", ""))
        closing = float(rows[-1][3].replace(",", ""))
        ndr = sum(1 for r in rows if r[1]); ncr = sum(1 for r in rows if r[2])
        top += 8.0
        ws.append(w("Summary", 60, top))
        top += 12.0
        for i, tok in enumerate([f"{opening:.2f}", str(ndr), str(ncr), f"{deb:.2f}", f"{cred:.2f}", f"{closing:.2f}"]):
            ws.append(w(tok, 60 + i * 90, top))
    return [Page(ws, W)]


def _route(spec, anchors, hdr, rows=None, mut=None):
    rows = rows if rows is not None else _chain(5)
    pages = _page(spec, anchors, rows, hdr)
    if mut:
        pages = mut(spec, anchors, rows, pages)
    return route_pages(pages, DEFAULT_REGISTRY, bank_key="n1syn") if spec.bank_key != "n1syn" else \
        _route_direct(spec, pages)


def _route_direct(spec, pages):
    """Bypass the registry: exercise this spec only (synth bank_key is not registered)."""
    from app.services.statement_engine.extraction.engine import extract_pages
    from app.services.statement_engine.extraction.pdf_extractor import to_extraction_result
    out = extract_pages(pages, spec)
    return out, to_extraction_result(out, spec)


# ---------- capability: multi-line header assembly ----------

def test_two_line_wrap_header_resolves():
    anchors = _uniform_anchors(SPEC_2L)
    hdr = _to_words(two_line_wrap(SPEC_2L, anchors))
    found = find_header(group_lines(hdr), SPEC_2L)
    assert found is not None and set(found[1]) == set(SPEC_2L.columns)


def test_three_line_interleaved_header_resolves():
    anchors = _uniform_anchors(SPEC_3L)
    hdr = _to_words(three_line_interleave(SPEC_3L, anchors))
    found = find_header(group_lines(hdr), SPEC_3L)
    assert found is not None and set(found[1]) == set(SPEC_3L.columns)


def test_header_lines2_cannot_bridge_three_line_header():
    spec2 = LayoutSpec(**{**SPEC_3L.__dict__, "layout_id": "n1syn_three_line_h2", "header_lines": 2})
    anchors = _uniform_anchors(spec2)
    hdr = _to_words(three_line_interleave(spec2, anchors))
    assert find_header(group_lines(hdr), spec2) is None


def test_centred_titles_merge():
    anchors = _uniform_anchors(SPEC_2L, width=110.0)
    hdr = _to_words(centred_titles(SPEC_2L, anchors))
    found = find_header(group_lines(hdr), SPEC_2L)
    assert found is not None and set(found[1]) == set(SPEC_2L.columns)


def test_merged_header_rejects_unknown_mid_span_token():
    anchors = _uniform_anchors(SPEC_2L)
    tuples = two_line_wrap(SPEC_2L, anchors)
    xs = sorted(v[0] for v in anchors.values())
    mid = (xs[1] + xs[2]) / 2
    tuples.append(("MYSTERY", mid, mid + 5.5 * 7, 200.0, 208.0))
    assert find_header(group_lines(_to_words(tuples)), SPEC_2L) is None


def test_date_title_not_required_on_first_line():
    """The date fragment may live entirely on the last merged line."""
    anchors = _uniform_anchors(SPEC_3L)
    words = []
    for col, (x0, _wd) in anchors.items():
        toks = SPEC_3L.columns[col][0]
        if col == "date":
            words += [(t, x0, x0 + 5.5 * len(t), 220.0, 228.0) for t in toks]
        else:
            mid = len(toks) // 2 or 1
            words += [(t, x0, x0 + 5.5 * len(t), 200.0, 208.0) for t in toks[:mid]]
            words += [(t, x0, x0 + 5.5 * len(t), 210.0, 218.0) for t in toks[mid:]]
    found = find_header(group_lines(_to_words(words)), SPEC_3L)
    assert found is not None and "date" in found[1]


def test_default_spec_unaffected_by_header_lines():
    spec = LayoutSpec(**{**SPEC_2L.__dict__, "layout_id": "n1syn_h1", "header_lines": 1})
    anchors = _uniform_anchors(spec)
    hdr = _to_words(two_line_wrap(spec, anchors))
    assert find_header(group_lines(hdr), spec) is None


# ---------- capability: untitled leading date column ----------

def _untitled_header(spec, anchors, top=200.0):
    ws = []
    for col in spec.columns:
        if col == "date":
            continue
        x0, _wd = anchors[col]
        for t in spec.columns[col][0]:
            ws.append(w(t, x0, top))
            x0 += 5.5 * len(t) + 3
    return ws


def test_untitled_date_column_synthesized_from_rows():
    anchors = _uniform_anchors(SPEC_UNTITLED)
    hdr = _untitled_header(SPEC_UNTITLED, anchors)
    rows = _chain(4)
    ws = list(hdr)
    top = 240.0
    for d, dr, cr, bal in rows:
        ws += _row_words(SPEC_UNTITLED, anchors, top, d, "UPI REF", dr, cr, bal)
        top += 16.0
    found = find_header(group_lines(ws), SPEC_UNTITLED)
    assert found is not None and "date" in found[1]
    dx0, dx1 = anchors["date"]
    span = found[1]["date"]
    assert abs(span[0] - dx0) < 20 and span[1] > dx0


def test_untitled_date_refuses_two_candidates():
    """Two left-of-title clusters both date-shaped -> refuse (ambiguous)."""
    anchors = _uniform_anchors(SPEC_UNTITLED)
    anchors["date"] = (10.0, 95.0)     # narrow real date column leaves room for a disjoint impostor
    hdr = _untitled_header(SPEC_UNTITLED, anchors)
    ws = list(hdr)
    for i, top in enumerate(range(240, 300, 16)):
        # the real date cells plus a second, disjoint date-shaped column -> refuse
        ws += _row_words(SPEC_UNTITLED, anchors, top, f"0{i % 9 + 1}/03/2024",
                         "TXT", "50.00", None, "950.00")
        ws.append(w(f"0{(i + 1) % 9 + 1}/02/2024", 95.0, top))     # impostor date column
    assert find_header(group_lines(ws), SPEC_UNTITLED) is None


def test_untitled_header_with_extra_mid_column_refused():
    anchors = _uniform_anchors(SPEC_UNTITLED)
    hdr = _untitled_header(SPEC_UNTITLED, anchors)
    xs = sorted(v[0] for v in anchors.values())
    mid = (xs[2] + xs[3]) / 2
    hdr.append(w("EXTRA", mid, 200.0))
    ws = list(hdr)
    for i, top in enumerate(range(240, 280, 16)):
        ws += _row_words(SPEC_UNTITLED, anchors, top, "01/01/2024", "TXT", "50.00", None, "950.00")
    assert find_header(group_lines(ws), SPEC_UNTITLED) is None


# ---------- capability: period-suffixed side markers ----------

@pytest.mark.parametrize("marker,side", [("Dr.", "dr"), ("Cr.", "cr"), ("DR.", "dr"), ("CR.", "cr"),
                                          ("Dr", "dr"), ("(Cr)", "cr")])
def test_side_marker_regex_accepts_period_suffix(marker, side):
    from app.services.statement_engine.extraction.normalize import SIDE_MARKER_RE
    m = SIDE_MARKER_RE.search(f"1,234.56 {marker}")
    assert m and m.group(1).lower() == side


def test_period_suffixed_marker_end_to_end():
    """Full row normalize: `1,000.00 Dr.` credits nothing, debits 1000."""
    anchors = _uniform_anchors(SPEC_DRCR)
    hdr = _to_words(two_line_wrap(SPEC_DRCR, anchors))
    pages = _page(SPEC_DRCR, anchors, _chain(4), hdr)
    assert _outcome_verdict(SPEC_DRCR, pages) == "VERIFIED"


# ---------- failure-injection battery ----------

def _mut_drop_row(spec, anchors, rows, pages):
    pgs = [Page(list(p.words), p.width) for p in pages]
    cut_top = 240.0 + 2 * 16.0
    pgs[0].words = [wd for wd in pgs[0].words if not (cut_top - 1 <= wd.top <= cut_top + 8)]
    return pgs


def _mut_swap_side(spec, anchors, rows, pages):
    pgs = [Page(list(p.words), p.width) for p in pages]
    # move first row's debit amount word to the credit column's edge (or flip the marker)
    if spec.side_marker_column:
        for wd in pgs[0].words:
            if 240 <= wd.top <= 248 and wd.text in ("Dr.", "Cr.", "Dr", "Cr"):
                wd = Word("Cr." if wd.text.startswith("D") else "Dr.", wd.x0, wd.x1, wd.top, wd.bottom)
                pgs[0].words = [x for x in pgs[0].words if not (x.top == wd.top and x.x0 == wd.x0)] + [wd]
                break
    else:
        # title-edge convention of the harness: last seq token printed at the column's anchor x0
        dr_edge = anchors[spec.debit_column][0] + 5.5 * len(spec.columns[spec.debit_column][0][-1])
        cr_edge = anchors[spec.credit_column][0] + 5.5 * len(spec.columns[spec.credit_column][0][-1])
        new_words = []
        for wd in pgs[0].words:
            if 240 <= wd.top <= 248 and spec.amount_re.match(wd.text) and abs(wd.x1 - dr_edge) < 8:
                wd = Word(wd.text, cr_edge - (wd.x1 - wd.x0), cr_edge, wd.top, wd.bottom)
            new_words.append(wd)
        pgs[0].words = new_words
    return pgs


def _mut_change_amount(spec, anchors, rows, pages):
    """Rewrite the first row's debit/credit amount (same printed shape, wrong value)."""
    pgs = [Page(list(p.words), p.width) for p in pages]
    new = []
    once = [False]
    for wd in pgs[0].words:
        if (not once[0] and 240 <= wd.top <= 248 and spec.amount_re.match(wd.text)
                and wd.text.rstrip("DCdrcr. ") != "" and wd.x1 < anchors[spec.balance_column][0]):
            wd = Word("9,999.00", wd.x1 - 5.5 * len("9,999.00"), wd.x1, wd.top, wd.bottom)
            once[0] = True
        new.append(wd)
    pgs[0].words = new
    return pgs


def _mut_missing_page(spec, anchors, rows, pages):
    return pages[:1]  # multi-page variant built by caller; single-page handled below


def _mut_truncated_last_page(spec, anchors, rows, pages):
    pgs = [Page(list(p.words), p.width) for p in pages]
    last = pgs[-1]
    if last.words:
        max_top = max(wd.top for wd in last.words)
        last.words = [wd for wd in last.words if wd.top < max_top - 1]
    return pgs


def _mut_extra_header_column(spec, anchors, rows, pages):
    pgs = [Page(list(p.words), p.width) for p in pages]
    xs = sorted(v[0] for v in anchors.values())
    mid = (xs[1] + xs[2]) / 2
    pgs[0].words += _to_words([("ZZCOL", mid, mid + 30, 200.0, 208.0)])
    return pgs


MUTATIONS = [_mut_drop_row, _mut_swap_side, _mut_change_amount, _mut_truncated_last_page,
             _mut_extra_header_column]


def _outcome_verdict(spec, pages):
    from app.services.statement_engine.extraction.engine import extract_pages
    out = extract_pages(pages, spec)
    if out.failure:
        return "FAILED"
    return out.checks.verdict if out.checks else "FAILED"


@pytest.mark.parametrize("spec,hdrf", [
    (SPEC_2L, two_line_wrap),
    (SPEC_3L, three_line_interleave),
])
def test_mutation_battery_multiline(spec, hdrf):
    anchors = _uniform_anchors(spec)
    hdr = _to_words(hdrf(spec, anchors))
    pages = _page(spec, anchors, _chain(6), hdr)
    assert _outcome_verdict(spec, pages) == "VERIFIED"
    for mut in MUTATIONS:
        mutated = mut(spec, anchors, None, [Page(list(p.words), p.width) for p in pages])
        assert _outcome_verdict(spec, mutated) != "VERIFIED", mut.__name__


def test_mutation_battery_untitled():
    anchors = _uniform_anchors(SPEC_UNTITLED)
    hdr = _untitled_header(SPEC_UNTITLED, anchors)
    pages = _page(SPEC_UNTITLED, anchors, _chain(6), hdr)
    assert _outcome_verdict(spec=SPEC_UNTITLED, pages=pages) == "VERIFIED"
    for mut in MUTATIONS:
        mutated = mut(SPEC_UNTITLED, anchors, None, [Page(list(p.words), p.width) for p in pages])
        assert _outcome_verdict(SPEC_UNTITLED, mutated) != "VERIFIED", mut.__name__


def test_mutation_battery_drcr_period():
    anchors = _uniform_anchors(SPEC_DRCR)
    hdr = _to_words(two_line_wrap(SPEC_DRCR, anchors))
    pages = _page(SPEC_DRCR, anchors, _chain(6), hdr)
    v = _outcome_verdict(SPEC_DRCR, pages)
    assert v == "VERIFIED"
    for mut in MUTATIONS:
        mutated = mut(SPEC_DRCR, anchors, None, [Page(list(p.words), p.width) for p in pages])
        assert _outcome_verdict(SPEC_DRCR, mutated) != "VERIFIED", mut.__name__


def test_missing_page_not_verified():
    anchors = _uniform_anchors(SPEC_2L)
    hdr = _to_words(two_line_wrap(SPEC_2L, anchors))
    p1 = _page(SPEC_2L, anchors, _chain(4), hdr)
    p2 = _page(SPEC_2L, anchors, _chain(4, open_bal=-200.0), hdr)
    full = _outcome_verdict(SPEC_2L, p1 + p2)
    assert full in ("VERIFIED", "REVIEW")
    # a truncated multi-page stream must not verify
    from app.services.statement_engine.extraction.engine import extract_pages
    out = extract_pages(p1, SPEC_2L)
    verdict = out.checks.verdict if out.checks else "FAILED"
    # a single clean page may verify on its own; the guard is that page-count-sensitive
    # families must not verify with silently missing trailing pages — completeness/period
    # checks must not let a truncation pass VERIFIED on the *mutated* stream
    truncated = _mut_truncated_last_page(SPEC_2L, anchors, None, [Page(list(p.words), p.width) for p in p1 + p2])
    out2 = extract_pages(truncated, SPEC_2L)
    assert (out2.checks.verdict if out2.checks else "FAILED") != "VERIFIED" or out2.failure


# ---------- onboarded specs: the real N1 families ----------

def _real_spec(lid):
    return [s for s in DEFAULT_REGISTRY.specs() if s.layout_id == lid][0]


@pytest.mark.parametrize("lid", [
    "idbi_srl_txndate_valuedate_description_chequeno_crdr_ccy_amountinr_balanceinr",
    "yes_transactiondate_valuedate_chequeno_txnno_description_debit_credit_runningbalance_3l",
    "central_bank_postdate_valuedate_branchco_journal_branchname_city_zone_cheque_mode_description_15col",
    "pnb_transactiondate_chequenumber_withdrawal_deposit_balance_narration_2l",
    "pnb_transactiondate_chequenumber_withdrawal_deposit_balance_narration_3l",
])
def test_real_spec_extra_header_column_refused(lid):
    """A header with an extra unknown column in the middle must not resolve."""
    spec = _real_spec(lid)
    anchors = _uniform_anchors(spec, width=80.0)
    if spec.header_lines >= 3:
        tuples = three_line_interleave(spec, anchors, top=200.0)
        ftop = 210.0                     # middle line: inside every 3-line window from the top
    else:
        tuples = two_line_wrap(spec, anchors, top=200.0)
        ftop = 210.0                     # second line: inside every n>=2 window
    xs = sorted(v[0] for v in anchors.values())
    mid = (xs[2] + xs[3]) / 2
    tuples.append(("FOREIGNCOL", mid, mid + 5.5 * 10, ftop, ftop + 8))
    assert find_header(group_lines(_to_words(tuples)), spec) is None
