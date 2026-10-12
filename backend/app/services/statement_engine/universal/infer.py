"""Structure inference: words-on-pages -> a runtime LayoutSpec.

Nothing here parses transactions. The output is a LayoutSpec that the ordinary
extraction engine + checks then run on, so T3 results pass through the same
verdict code as registered layouts. Any step that cannot be decided returns a
failure dict (never raises): the caller turns it into a FAILED outcome.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Sequence, Tuple

from ..extraction.layout_spec import LayoutSpec
from ..extraction.rows import Page
from ..extraction.words import Word, group_lines, norm_token, squash

from . import lexicon as LX


@dataclass
class Inference:
    spec: Optional[LayoutSpec]
    failure: Optional[str] = None
    detail: str = ""
    notes: List[str] = field(default_factory=list)
    meta: Dict[str, object] = field(default_factory=dict)   # shape names, margins — for observability


def _fail(code: str, detail: str, meta: Dict = None) -> Inference:
    return Inference(spec=None, failure=code, detail=detail, meta=meta or {})


# ---------------- furniture ----------------

def furniture_prefixes(pages: Sequence[Page]) -> List[str]:
    """Whitespace-free upper-case prefixes of lines repeated on >= 60% of pages (>=4 pages)."""
    n = len(pages)
    if n < 4:
        return []
    from collections import Counter
    seen = Counter()
    for p in pages:
        texts = {squash(ln).upper() for ln in group_lines(p.words)}
        seen.update(texts)
    out = []
    for t, c in sorted(seen.items()):
        if c >= max(2, int(n * 0.6)) and len(t) >= 8 and not re.search(r"\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}", t):
            out.append(t[:40])
    return out


# ---------------- header discovery ----------------

def _line_tokens(line: Sequence[Word]) -> List[Tuple[str, float, float]]:
    return [(norm_token(w.text), w.x0, w.x1) for w in line if norm_token(w.text)]


def _alts_sorted(alternatives: Sequence[Tuple[str, ...]]) -> List[Tuple[str, ...]]:
    """Longest alternatives first; within a length prefer the longer text (fused 'txndate' beats 'date')."""
    return sorted(alternatives, key=lambda a: (len(a), sum(len(t) for t in a)), reverse=True)


def _match_role(toks: Sequence[Tuple[str, float, float]], used: set,
                alternatives: Sequence[Tuple[str, ...]]) -> Optional[Tuple[float, float, Tuple[str, ...], Tuple[int, ...]]]:
    """Longest alternative that occurs as a contiguous run of unused tokens."""
    for alt in _alts_sorted(alternatives):
        n = len(alt)
        for i in range(len(toks) - n + 1):
            if any(i + k in used for k in range(n)):
                continue
            if all(toks[i + k][0] == alt[k] for k in range(n)):
                return toks[i][1], toks[i + n - 1][2], alt, tuple(range(i, i + n))
    return None


def merge_header_pair(upper: Sequence[Word], lower: Sequence[Word]) -> List[Tuple[Word, int]]:
    """Same cluster-aware order as anchors._merge_header_pair, but every emitted word keeps a tag of
    which source line it came from (0 = upper)."""
    first = {id(w) for w in upper}
    words = sorted((*upper, *lower), key=lambda w: w.x0)
    merged: List[Tuple[Word, int]] = []
    cluster: List[Word] = []
    cluster_x = None
    for w in words:
        if cluster_x is None or w.x0 - cluster_x <= 2.5:
            cluster.append(w)
            cluster_x = w.x0 if cluster_x is None else cluster_x
        else:
            for v in sorted(cluster, key=lambda v: 0 if id(v) in first else 1):
                merged.append((v, 0 if id(v) in first else 1))
            cluster = [w]
            cluster_x = w.x0
    for v in sorted(cluster, key=lambda v: 0 if id(v) in first else 1):
        merged.append((v, 0 if id(v) in first else 1))
    return merged


@dataclass
class HeaderHit:
    spans: Dict[str, Tuple[float, float, Tuple[str, ...]]]   # role -> (x0, x1, tokens)
    aux: List[Tuple[float, float, Tuple[str, ...]]]          # uncovered token runs inside the span
    upper_alts: Dict[str, Tuple[str, ...]]                   # role -> extra alternative made of its upper-line tokens
    score: float
    line_idx: int
    wrapped: bool


def _try_header_on(tagged: Sequence[Tuple[Word, int]], line_idx: int, wrapped: bool) -> Optional[HeaderHit]:
    """tagged = [(word, source_line)]. For an unwrapped call every source is 0."""
    toks = [(norm_token(w.text), w.x0, w.x1, src) for w, src in tagged if norm_token(w.text)]
    if len(toks) < 3:
        return None
    used: set = set()
    spans: Dict[str, Tuple[float, float, Tuple[str, ...]]] = {}
    idx_of: Dict[str, Tuple[int, ...]] = {}
    for role in ("date", "value_date", "balance", "debit", "credit", "amount",
                 "narration", "type", "ref", "serial", "branch", "category"):
        hit = _match_role(toks, used, LX.HEADER_SYNONYMS[role])
        if hit:
            spans[role] = hit[:3]
            idx_of[role] = hit[3]
            used.update(hit[3])
    if not all(r in spans for r in LX.REQUIRED_ROLES):
        return None
    if not ("amount" in spans or ("debit" in spans and "credit" in spans)):
        return None
    if not spans["date"][0] < spans["balance"][0]:
        return None
    money_x = min(spans[r][0] for r in ("debit", "credit", "amount", "balance") if r in spans)
    if spans["narration"][1] > money_x:
        return None
    # the engine merges a wrapped header only when "date" already matched on the upper line.
    # A date match spanning both lines is fine when its upper-line tokens form a usable
    # alternative ("transaction" of "transaction date"); a match with no upper token at all
    # can never trigger the merge -> this candidate is not servable by the engine.
    if wrapped and all(toks[i][3] != 0 for i in idx_of["date"]):
        return None
    upper_alts: Dict[str, Tuple[str, ...]] = {}
    if wrapped:
        for role, idxs in idx_of.items():
            if all(toks[i][3] == 0 for i in idxs):
                continue
            prefix = tuple(toks[i][0] for i in idxs if toks[i][3] == 0)
            if prefix:
                upper_alts[role] = prefix
    lo = min(s[0] for s in spans.values())
    hi = max(s[1] for s in spans.values())
    aux: List[Tuple[float, float, Tuple[str, ...]]] = []
    run: List[Tuple[str, float, float]] = []
    for i, t in enumerate(toks):
        inside = i not in used and lo <= t[1] and t[2] <= hi
        if inside:
            run.append(t[:3])
        elif run:
            aux.append((run[0][1], run[-1][2], tuple(x[0] for x in run)))
            run = []
    if run:
        aux.append((run[0][1], run[-1][2], tuple(x[0] for x in run)))
    score = len(spans) * 2 - len(aux)
    return HeaderHit(spans=spans, aux=aux, upper_alts=upper_alts, score=score,
                     line_idx=line_idx, wrapped=wrapped)


def find_header(lines: Sequence[Sequence[Word]]) -> Optional[HeaderHit]:
    best = None
    for i, line in enumerate(lines):
        hit = _try_header_on([(w, 0) for w in line], i, False)
        if hit and (best is None or hit.score > best.score):
            best = hit
        if i + 1 < len(lines):
            hit = _try_header_on(merge_header_pair(line, lines[i + 1]), i + 1, True)
            if hit and (best is None or hit.score > best.score):
                best = hit
    return best


# ---------------- dated-line discovery ----------------

def _as_amount(text: str) -> Optional[Decimal]:
    t = text.strip()
    if not LX.AMOUNT_RE.match(t):
        return None
    neg = t[:1] == "-"
    t = re.sub(r"(?i)\(?\s*(cr|dr)\s*\.?\)?\s*$", "", t)
    t = re.sub(r"^[+-]?\s*(?:Rs\.?|₹)?\s*", "", t)
    if t.startswith("(") and t.endswith(")"):
        neg = True
        t = t[1:-1]
    t = t.replace(",", "")
    try:
        v = Decimal(t)
        return -v if neg else v
    except InvalidOperation:
        return None


def _line_is_dated(line: Sequence[Word], date_re: re.Pattern) -> bool:
    return any(date_re.match(w.text.strip()) for w in line[:4])


def dated_lines(lines: Sequence[Sequence[Word]], date_re: re.Pattern) -> List[int]:
    return [i for i, ln in enumerate(lines) if _line_is_dated(ln, date_re)]


# ---------------- date shape ----------------

def infer_date_shape(lines: Sequence[Sequence[Word]], date_left: Optional[float] = None):
    """Pick the date shape covering the most dated-looking lines on page 1."""
    counts = []
    for name, pat, fmt, tail in LX.DATE_SHAPES:
        if pat is None:
            continue
        rx = re.compile(pat)
        n = sum(1 for ln in lines if any(rx.match(w.text.strip()) for w in ln[:3]))
        counts.append((n, name, rx, fmt, tail))
    counts.sort(reverse=True)
    if not counts or counts[0][0] < 3:
        return None
    n, name, rx, fmt, tail = counts[0]
    return {"name": name, "re": rx, "format": fmt, "tail_re": re.compile(tail) if tail else None, "hits": n}


# ---------------- money-role inference by balance chain ----------------

def _x_bands(words: Sequence[Word]) -> List[Tuple[float, float]]:
    """Cluster right edges of numeric tokens into columns (by x1 within 14pt)."""
    pts = sorted(w.x1 for w in words if _as_amount(w.text) is not None)
    bands: List[List[float]] = []
    for x in pts:
        if bands and x - bands[-1][-1] <= 14.0:
            bands[-1].append(x)
        else:
            bands.append([x])
    return [(sum(b) / len(b) - 8.0, max(b)) for b in bands]


def _rows_values(lines: Sequence[Sequence[Word]], idxs: Sequence[int], date_re, x_lo: float):
    """Per dated line: (balance-candidate right-side numeric tokens as (x1, Decimal))."""
    out = []
    for i in idxs:
        vals = [(w.x1, _as_amount(w.text), w.text) for w in lines[i]
                if w.x1 > x_lo and _as_amount(w.text) is not None]
        out.append(vals)
    return out


def _chain_fraction(rows_vals, assign) -> float:
    """Score for an assignment: adjacent rows where bal_i = bal_{i-1} + cr - dr (cells may be empty)."""
    ok = tot = 0
    prev_bal = None
    for vals in rows_vals:
        cols = {r: None for r in ("debit", "credit", "balance")}
        for x1, v, _t in vals:
            col = assign(x1)
            if col:
                cols[col] = v
        bal = cols["balance"]
        if bal is None:
            continue
        if prev_bal is not None:
            tot += 1
            delta = (cols["credit"] or Decimal(0)) - (cols["debit"] or Decimal(0))
            if bal - prev_bal == delta:
                ok += 1
        prev_bal = bal
    return ok / tot if tot else 0.0


def infer_money_assignment(rows_vals: List[list], edges: List[float]):
    """Try money-column role assignments; return (best, runner_up, details).

    edges = sorted right edges of the money x-clusters (2 or 3).
    """
    scored = []
    if len(edges) == 3:
        e0, e1, e2 = edges
        cands = {
            "d_c_b": lambda x: "debit" if abs(x - e0) <= 10 else ("credit" if abs(x - e1) <= 10 else "balance"),
            "c_d_b": lambda x: "credit" if abs(x - e0) <= 10 else ("debit" if abs(x - e1) <= 10 else "balance"),
        }
        for name, f in cands.items():
            scored.append((_chain_fraction(rows_vals, f), name, f))
    elif len(edges) == 2:
        e0, e1 = edges
        for name, bal_edge in (("amt_b", e1), ("b_amt", e0)):
            amt_edge = e0 if bal_edge == e1 else e1
            ok = tot = 0
            prev = None
            for vals in rows_vals:
                bal = amt = None
                for x1, v, _t in vals:
                    if abs(x1 - bal_edge) <= 10:
                        bal = v
                    elif abs(x1 - amt_edge) <= 10:
                        amt = v
                if bal is None:
                    continue
                if prev is not None and amt is not None:
                    tot += 1
                    if abs(bal - prev) == abs(amt):
                        ok += 1
                prev = bal
            scored.append((ok / tot if tot else 0.0, name, None))
    scored.sort(reverse=True, key=lambda s: s[0])
    if not scored:
        return None
    best = scored[0]
    runner = scored[1][0] if len(scored) > 1 else 0.0
    return {"name": best[0], "score": best[1] if False else best[0], "runner_up": runner}


# ---------------- summary / period / markers ----------------

def infer_summary_lines(page_texts: Sequence[str]) -> Dict[str, object]:
    out: Dict[str, object] = {}
    joined = "\n".join(page_texts)
    for kind, res in (("opening", LX.OPENING_RES), ("closing", LX.CLOSING_RES)):
        for pat in res:
            m = re.search(pat, joined)
            if m:
                out[kind] = re.compile(pat)
                out[kind + "_val"] = m.group(1)
                break
    for pat, fmt in LX.PERIOD_RES:
        m = re.search(pat, joined)
        if m:
            out["period"] = re.compile(pat)
            out["period_fmt"] = fmt
            out["period_val"] = m.groups()
            break
    for pat in LX.TOTALS_RES:
        m = re.search(pat, joined)
        if m:
            out["totals"] = re.compile(pat)
            break
    return out


def count_accounts(page_texts: Sequence[str]) -> int:
    vals: List[str] = []
    for t in page_texts[:4]:
        for rx in LX.ACCOUNT_RES:
            vals.extend(rx.findall(t))
    # a capture can absorb digits of a following number on squashed text ("018301589018" + "6,779.53"
    # -> "0183015890186"): collapses to one account when one value is a prefix of another.
    distinct: List[str] = []
    for v in sorted(set(vals)):
        if not any(v.startswith(d) or d.startswith(v) for d in distinct):
            distinct.append(v)
    return len(distinct)


# ---------------- main entry ----------------

def infer(pages: Sequence[Page], budget_check=lambda: None) -> Inference:
    if not pages:
        return _fail("NO_PAGES", "no pages read")
    texts = [("\n".join(squash(ln) for ln in group_lines(p.words))) for p in pages]

    furn = furniture_prefixes(pages)
    notes: List[str] = [f"furniture_lines:{len(furn)}"] if furn else []

    # --- date shape must be known before dated-row scan ---
    p1 = pages[0]
    lines1 = group_lines(p1.words)
    shape = infer_date_shape(lines1)
    if shape is None and len(pages) > 1:
        shape = infer_date_shape(group_lines(pages[1].words))
    if shape is None:
        return _fail("NO_DATES", "no repeated date shape found")
    date_re, date_fmt, tail_re = shape["re"], shape["format"], shape["tail_re"]
    notes.append(f"date_shape:{shape['name']}({shape['hits']})")

    # --- header discovery on first 3 pages ---
    hit = None
    hit_page = 0
    for pno, p in enumerate(pages[:3]):
        hit = find_header(group_lines(p.words))
        if hit:
            hit_page = pno
            notes.append(f"header:p{pno + 1}{'wrapped' if hit.wrapped else ''}")
            break
    # multi-statement check: >1 distinct account number in the region above the table header
    header_top = None
    if hit is not None:
        lns = group_lines(pages[hit_page].words)
        if hit.line_idx < len(lns):
            header_top = min(w.top for w in lns[min(hit.line_idx, len(lns) - 1)])
    head_text = "\n".join(squash(ln) for ln in group_lines(pages[0].words)
                          if header_top is None or max(w.top for w in ln) <= header_top + 1.0)
    if count_accounts([head_text]) > 1:
        return _fail("MULTI_STATEMENT", "several account numbers detected")

    header_repeats = False
    if hit is None:
        return _infer_implicit(pages, date_re, date_fmt, tail_re, texts, furn, notes)
    if len(pages) > 1:
        header_repeats = any(find_header(group_lines(p.words)) for p in pages[1:min(len(pages), 5)])
    if header_repeats:
        notes.append("header_repeats")

    return _spec_from_header(pages, hit, header_repeats, date_re, date_fmt, tail_re, texts, furn, notes)


def _roles_to_columns(hit: HeaderHit) -> Tuple[Dict[str, Tuple[Tuple[str, ...], ...]], Dict[str, float]]:
    """role -> spec columns entry (full match first, then its upper-line prefix); plus role -> x0."""
    cols: Dict[str, Tuple[Tuple[str, ...], ...]] = {}
    xs: Dict[str, float] = {}
    for role, (x0, _x1, tokens) in hit.spans.items():
        alts = [tokens]
        if role in hit.upper_alts and hit.upper_alts[role] != tokens:
            alts.append(hit.upper_alts[role])
        cols[role] = tuple(alts)
        xs[role] = x0
    return cols, xs


def _spec_from_header(pages, hit: HeaderHit, header_repeats: bool, date_re, date_fmt, tail_re,
                      texts, furn, notes) -> Inference:
    spec, err, n2 = _build_spec(pages, hit, header_repeats, date_re, date_fmt, tail_re, texts, furn)
    notes.extend(n2)
    if err:
        return _fail(*err)
    return _check_margin(spec, pages, date_re, hit, notes, meta_extra={"header": True})


def _build_spec(pages, hit: HeaderHit, header_repeats: bool, date_re, date_fmt, tail_re,
                texts, furn) -> Tuple[Optional[LayoutSpec], Optional[Tuple[str, str]], List[str]]:
    notes: List[str] = []
    spans = hit.spans
    money_roles = [r for r in ("debit", "credit", "amount", "balance") if r in spans]
    columns, xs = _roles_to_columns(hit)
    if "narration" not in spans:
        return None, ("NO_NARRATION_COL", "header has no narration-like column"), notes
    # every token run between the outer spans must be a declared column, or the engine's
    # completeness check refuses the header: give each uncovered run an aux role and place it
    # in text_columns by x so its data lands in an unused band rather than in narration.
    money_x0 = min(xs[r] for r in money_roles)
    date_x0 = xs["date"]
    aux_roles: List[Tuple[float, str]] = []
    for i, (x0, _x1, toks) in enumerate(hit.aux):
        name = f"aux{i}"
        columns[name] = (toks,)
        aux_roles.append((x0, name))
    # text bands must sit between date and money: a column LEFT of the date breaks date_right
    # (the engine caps it at the second text column's left edge); one inside the money block
    # would swallow amounts. Both stay declared in `columns` for header completeness.
    def _xkey(r: str) -> float:
        if r in xs:
            return xs[r]
        return next((x for x, n in aux_roles if n == r), 0.0)
    text_roles = [r for r, (x0, _x1, _t) in sorted(spans.items(), key=lambda kv: kv[1][0])
                  if r not in money_roles and x0 > date_x0]
    text_roles = sorted(text_roles + [n for x, n in aux_roles if date_x0 < x < money_x0], key=_xkey)

    text_columns = tuple(["date"] + [r for r in text_roles if r != "date"])
    if "narration" not in text_columns:
        text_columns = ("date", "narration") + tuple(r for r in text_roles if r not in ("date", "narration"))

    single_amount = "amount" in spans and "debit" not in spans
    type_col = "type" if "type" in text_roles else ""
    # single_amount_column makes debit/credit purely virtual names for normalize's side
    # bookkeeping: they must be distinct and must NOT coincide with the amount column name.
    debit_col = "amount_dr" if single_amount else "debit"
    credit_col = "amount_cr" if single_amount else "credit"

    summ = infer_summary_lines([texts[0], texts[-1]])
    # scan dated lines for amount-form evidence
    dlines = dated_lines(group_lines(pages[0].words), date_re)
    suffix_hits = sign_hits = sep_suffix = 0
    for i in dlines[:80]:
        for w in group_lines(pages[0].words)[i]:
            t = w.text.strip()
            if LX.DRCR_SUFFIX_RE.search(t) and _as_amount(re.sub(LX.DRCR_SUFFIX_RE, "", t)):
                suffix_hits += 1
            elif t.lower() in ("cr", "dr", "(cr)", "(dr)"):
                sep_suffix += 1
            elif LX.SIGNED_RE.match(t) and _as_amount(t):
                sign_hits += 1
    merge_drcr = sep_suffix > 0
    merge_sign = sign_hits > 0 and not suffix_hits
    if suffix_hits:
        notes.append("amount_form:drcr_suffix")
    elif sign_hits:
        notes.append("amount_form:signed")
    elif merge_drcr:
        notes.append("amount_form:separate_drcr")

    # empty-cell marker
    empty_marker = ""
    for i in dlines[:40]:
        for w in group_lines(pages[0].words)[i]:
            if w.text.strip() in ("-", "–"):
                empty_marker = "-"
                break

    spec = LayoutSpec(
        layout_id="universal_auto",
        bank_key="universal",
        bank_name="Unknown bank",
        columns=columns,
        text_columns=text_columns,
        debit_column=debit_col,
        credit_column=credit_col,
        balance_column="balance",
        date_re=date_re,
        date_format=date_fmt,
        amount_re=LX.AMOUNT_RE,
        period_re=summ.get("period", re.compile(r"(?!x)x")),
        period_date_format=summ.get("period_fmt", "%d/%m/%Y"),
        summary_marker="",
        summary_label_text="",
        secondary_date_column="value_date" if "value_date" in text_roles else None,
        header_repeats=header_repeats,
        header_wraps=hit.wrapped,
        end_markers=tuple(),
        date_tail_re=tail_re,
        continuation_start="top",
        summary_expected=bool(summ),
        opening_balance_re=summ.get("opening"),
        closing_balance_re=summ.get("closing"),
        totals_line_re=summ.get("totals"),
        single_amount_column="amount" if single_amount else "",
        side_marker_column=type_col if (single_amount and type_col) else "",
        merge_drcr_suffix=merge_drcr,
        merge_sign_prefix=merge_sign,
        amount_prefix="Rs.|₹|INR",
        empty_amount_marker=empty_marker,
        row_order="auto",
        ignore_line_res=tuple(re.compile(r"^" + re.escape(f)) for f in sorted(furn)[:30]),
        year_from_period=bool(tail_re or "-Y" not in date_fmt) and "period" in summ,
        opening_row_balance_only=True,
    )
    return spec, None, notes


def _infer_implicit(pages, date_re, date_fmt, tail_re, texts, furn, notes) -> Inference:
    """Headerless table: dated lines whose token-count shape repeats define implicit columns."""
    lines = group_lines(pages[0].words)
    idxs = dated_lines(lines, date_re)
    if len(idxs) < 4:
        return _fail("NO_DATED_ROWS", "fewer than 4 dated lines on first page")
    # cluster x1 of numeric tokens across dated lines
    bands = _x_bands([w for i in idxs[:60] for w in lines[i]])
    if len(bands) < 2:
        return _fail("NO_MONEY_COLUMNS", "dated lines carry < 2 numeric columns")
    notes.append(f"implicit:bands={len(bands)}")
    # token-count consistency: role count = median tokens per dated line
    counts = [len(lines[i]) for i in idxs[:40]]
    counts.sort()
    med = counts[len(counts) // 2]
    edges = [e for _l, e in bands]
    roles_guess = len(bands) + 1   # date + money cols (narration carried on separate lines)

    margin = _implicit_margin(lines, idxs, edges, date_re)
    if margin is None or margin["score"] < 0.85 or margin["score"] - margin["runner_up"] < 0.15:
        return _fail("LOW_CONFIDENCE_COLUMNS",
                     f"chain margin unclear best={margin and margin['score']:.2f} next={margin and margin['runner_up']:.2f}",
                     meta={"margin": margin})

    # build implicit role order: date, [secondary date], narration, <money roles>, balance last
    if len(edges) == 3:
        money_roles = ["debit", "credit", "balance"] if margin["name"] == "d_c_b" else ["credit", "debit", "balance"]
        single = ""
    elif len(edges) == 2:
        money_roles = (["amount", "balance"] if margin["name"] == "amt_b" else ["balance", "amount"])
        single = "amount" if "amount" in money_roles else ""
    else:
        return _fail("TOO_MANY_MONEY_COLUMNS", f"{len(edges)} money bands")
    implicit_roles = ["date", "narration", *money_roles]
    columns = {r: (("x",),) for r in implicit_roles}   # placeholders; implicit_header ignores them for anchoring
    spec = LayoutSpec(
        layout_id="universal_implicit",
        bank_key="universal",
        bank_name="Unknown bank",
        columns=columns,
        text_columns=("date", "narration"),
        debit_column="amount_dr" if single else money_roles[0],
        credit_column="amount_cr" if single else money_roles[1],
        balance_column="balance",
        date_re=date_re, date_format=date_fmt,
        amount_re=LX.AMOUNT_RE,
        period_re=re.compile(r"(?!x)x"), period_date_format="%d/%m/%Y",
        summary_marker="", summary_label_text="",
        implicit_header=tuple(implicit_roles),
        continuation_start="top",
        summary_expected=False,
        single_amount_column=single,
        merge_drcr_suffix=True,
        merge_sign_prefix=True,
        amount_prefix="Rs.|₹|INR",
        row_order="auto",
        ignore_line_res=tuple(re.compile(r"^" + re.escape(f)) for f in sorted(furn)[:30]),
        opening_row_balance_only=True,
    )
    summ = infer_summary_lines([texts[0], texts[-1]])
    if summ:
        spec = _respec(spec, summ)
    notes.append(f"implicit_margin:{margin['score']:.2f}/{margin['runner_up']:.2f}")
    return Inference(spec=spec, notes=notes, meta={"header": False, "margin": margin})


def _respec(spec: LayoutSpec, summ) -> LayoutSpec:
    from dataclasses import replace
    return replace(spec,
                   opening_balance_re=summ.get("opening"),
                   closing_balance_re=summ.get("closing"),
                   totals_line_re=summ.get("totals"),
                   period_re=summ.get("period", spec.period_re),
                   period_date_format=summ.get("period_fmt", spec.period_date_format),
                   summary_expected=True)


def _implicit_margin(lines, idxs, edges, date_re):
    """Balance-chain margin over dated lines: try every full role assignment."""
    vals = []
    for i in idxs[:120]:
        row = [(w.x1, _as_amount(w.text)) for w in lines[i] if _as_amount(w.text) is not None]
        if row:
            vals.append(row)
    cand = []
    if len(edges) == 3:
        # (debit, credit, balance) over all 6 permutations
        import itertools
        for perm in itertools.permutations(edges):
            cand.append((perm, "d_c_b" if perm[0] < perm[1] else "c_d_b"))
    elif len(edges) == 2:
        cand = [((edges[0], edges[1]), "amt_b"), ((edges[1], edges[0]), "b_amt")]
    scores = []
    for perm, name in cand:
        bal_e = perm[-1]
        ok = tot = 0
        prev = None
        for row in vals:
            cells = {"debit": None, "credit": None, "amount": None, "balance": None}
            if len(perm) == 3:
                roles = ("debit", "credit", "balance")
            else:
                roles = ("amount", "balance")
            for x1, v in row:
                best_r, best_d = None, 1e9
                for r, e in zip(roles, perm):
                    if abs(x1 - e) <= 10 and abs(x1 - e) < best_d:
                        best_r, best_d = r, abs(x1 - e)
                if best_r:
                    cells[best_r] = v
            bal = cells["balance"]
            if bal is None:
                continue
            if prev is not None:
                if len(perm) == 3:
                    d, c = cells["debit"], cells["credit"]
                    if d is not None or c is not None:
                        tot += 1
                        if bal - prev == (c or Decimal(0)) - (d or Decimal(0)):
                            ok += 1
                else:
                    amt = cells["amount"]
                    if amt is not None:
                        tot += 1
                        if abs(bal - prev) == abs(amt):
                            ok += 1
            prev = bal
        scores.append((ok / tot if tot else 0.0, name))
    scores.sort(reverse=True)
    if not scores:
        return None
    return {"name": scores[0][1], "score": scores[0][0],
            "runner_up": scores[1][0] if len(scores) > 1 else 0.0}


def _check_margin(spec: LayoutSpec, pages, date_re, hit, notes, meta_extra) -> Inference:
    """For explicit headers the roles are named, not inferred — the margin check still runs to
    guard against a lexicon hit on a non-table line: sampled dated rows must chain under the
    declared money columns."""
    from ..extraction.engine import extract_pages
    try:
        out = extract_pages(pages[: min(len(pages), 4)], spec)
    except Exception as exc:
        return _fail("ENGINE_ERROR", f"{type(exc).__name__}", meta=meta_extra)
    n = len(out.rows)
    if out.failure:
        return _fail(out.failure, out.failure_detail, meta=meta_extra)
    checks = out.checks
    chained = 0
    if checks:
        chained = checks.results["chain"].detail.get("rows_checked", 0) - checks.results["chain"].detail.get("breaks", 0)
    total = max(n - 1, 1)
    frac = chained / total if n else 0.0
    meta = {**meta_extra, "rows_sample": n, "chain_frac": round(frac, 3)}
    if (n < 3 or frac < 0.80) and not spec.left_aligned_amounts:
        # wide cells right-aligned past their column's title edge fall to the neighbouring edge;
        # left-edge assignment is the alternative geometry, retry it before giving up.
        from dataclasses import replace
        alt = replace(spec, left_aligned_amounts=True)
        retry = _check_margin(alt, pages, date_re, hit, [], meta_extra)
        if retry.spec is not None and retry.failure is None:
            retry.notes.insert(0, "left_aligned_amounts")
            return retry
        meta["left_aligned_frac"] = retry.meta.get("chain_frac")
    if n < 3:
        return Inference(spec=spec, failure="TOO_FEW_ROWS", detail=f"only {n} rows extracted", meta=meta)
    if frac < 0.80:
        return Inference(spec=spec, failure="LOW_CONFIDENCE_COLUMNS",
                         detail=f"declared money columns chain only {frac:.2f}", meta=meta)
    notes.append(f"chain_sample:{chained}/{total}")
    return Inference(spec=spec, notes=notes, meta=meta)
