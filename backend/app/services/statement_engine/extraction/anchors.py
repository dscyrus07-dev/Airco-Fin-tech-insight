"""Column anchors derived from the table header on the first page that carries it.

Geometry is read from the document. Nothing is hard-coded: page width differs between files (638 and 595 pt seen).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .layout_spec import LayoutSpec
from .words import Word, group_lines, norm_token, squash


@dataclass(frozen=True)
class ColumnAnchors:
    layout_id: str
    page_width: Optional[float]
    header_top: float
    header_bottom: float
    spans: Dict[str, Tuple[float, float]]      # column -> (x0, x1) of its header title
    date_left: float                           # words left of this are page furniture (e.g. footer text)
    date_right: float                          # date column | narration column boundary
    text_lefts: Dict[str, float]               # left boundary of each text column after narration
    amount_edges: Dict[str, float]             # money column -> right edge of its header title
    amount_lefts: Dict[str, float] = field(default_factory=dict)   # money column -> left edge of its header title


class AnchorError(ValueError):
    pass


# Margin between a header title and the first character of its data cell column boundary
_BOUNDARY_PAD = 4.0
_DATE_FALLBACK_LEFT_PAD = 8.0
_DATE_FALLBACK_RIGHT_PAD = 10.0
_DATE_DATA_RIGHT_PAD = 3.0
_TRAILING_COLUMN_GAP = 20.0

# A number that is only the visible part of a wrapped money cell: comma-grouped digits with a possibly cut
# decimal ("9,99,999.9") or a lone 1-2 digit tail. Only meaningful when spec.wrapped_amount_tokens is on -
# position (near a money column's right edge) still decides the column.
_WRAPPED_AMOUNT_FRAGMENT = re.compile(r"^\d{1,3}(?:,\d{2,3})+\.?\d{0,2}$|^\.?\d{1,2}$")


def _tokens(line: Sequence[Word]) -> List[Tuple[str, float, float]]:
    out = []
    for w in line:
        t = norm_token(w.text)
        if t:
            out.append((t, w.x0, w.x1))
    return out


def _find_sequence(tokens: Sequence[Tuple[str, float, float]], seq: Tuple[str, ...]) -> Optional[Tuple[float, float]]:
    n = len(seq)
    for i in range(len(tokens) - n + 1):
        if all(tokens[i + k][0] == seq[k] for k in range(n)):
            # x-range of the whole run: wrapped fragments can sit left of the last token
            hit = tokens[i:i + n]
            return min(t[1] for t in hit), max(t[2] for t in hit)
    return None


def _match_spans(line: Sequence[Word], spec: LayoutSpec) -> Dict[str, Tuple[float, float]]:
    toks = _tokens(line)
    spans: Dict[str, Tuple[float, float]] = {}
    for col, alternatives in spec.columns.items():
        for seq in alternatives:
            hit = _find_sequence(toks, seq)
            if hit:
                spans[col] = hit
                break
    return spans


def _complete(line: Sequence[Word], spans: Dict[str, Tuple[float, float]], spec: LayoutSpec,
              center_test: bool = False) -> bool:
    if len(spans) != len(spec.columns):
        return False
    # a header with an extra, unknown column between the known ones is another layout: refuse it
    lo, hi = min(x[0] for x in spans.values()), max(x[1] for x in spans.values())
    def covered(w: Word) -> bool:
        if center_test:
            # wrapped-header words can protrude past their seq span by font epsilon (the first
            # title word is wider than the continuation): a word belongs when its centre sits in a span
            mid = (w.x0 + w.x1) / 2.0
            return any(a - 0.5 <= mid <= b + 0.5 for a, b in spans.values())
        return any(a - 0.5 <= w.x0 and w.x1 <= b + 0.5 for a, b in spans.values())
    unknown = [w for w in line if norm_token(w.text) and lo <= w.x0 and w.x1 <= hi and not covered(w)]
    return not unknown


def _merge_header_pair(upper: Sequence[Word], lower: Sequence[Word]) -> List[Word]:
    """Two visual lines of one wrapped header row as a single matchable stream: words are clustered
    by x0 (a title and its downward continuation sit at ~the same x, apart by font epsilon), and each
    cluster emits its upper-line words before the lower line's, preserving title word order."""
    first = {id(w) for w in upper}
    words = sorted((*upper, *lower), key=lambda w: w.x0)
    merged: List[Word] = []
    cluster: List[Word] = []
    cluster_x = None
    for w in words:
        if cluster_x is None or w.x0 - cluster_x <= 2.5:
            cluster.append(w)
            cluster_x = w.x0 if cluster_x is None else cluster_x
        else:
            merged.extend(sorted(cluster, key=lambda v: 0 if id(v) in first else 1))
            cluster = [w]
            cluster_x = w.x0
    merged.extend(sorted(cluster, key=lambda v: 0 if id(v) in first else 1))
    return merged


def _merge_header_lines(lines: Sequence[Sequence[Word]], tol: float) -> List[Word]:
    """Adjacent visual lines of one wrapped header row as a single matchable stream. Unlike
    `_merge_header_pair` (x0-proximity, two lines), words cluster by horizontal overlap: a fragment
    joins a cluster when its x0 lands within `tol` of the cluster's right edge, so a title's pieces
    join across non-adjacent lines (top / middle / bottom). Each cluster emits its fragments in
    top-to-bottom line order, preserving the title's word order."""
    line_of = {}
    words: List[Word] = []
    for i, line in enumerate(lines):
        for w in line:
            line_of[id(w)] = i
            words.append(w)
    words.sort(key=lambda w: w.x0)
    clusters: List[List[Word]] = []
    for w in words:
        if clusters and w.x0 <= max(v.x1 for v in clusters[-1]) + tol:
            clusters[-1].append(w)
        else:
            clusters.append([w])
    merged: List[Word] = []
    for cl in clusters:
        merged.extend(sorted(cl, key=lambda v: (line_of[id(v)], v.x0)))
    return merged


def _find_untitled_date(lines: Sequence[Sequence[Word]], spec: LayoutSpec, start: int,
                        right: float, probe: int = 12) -> Optional[Tuple[float, float]]:
    """x-span of an untitled leading date column, read from data rows below the header: every word
    landing left of `right` on the next `probe` lines is clustered by x-range; a cluster qualifies
    only when it holds >= 2 cells and every cell matches the spec's date shape. Exactly one
    qualifying cluster may exist."""
    clusters: List[List[Word]] = []
    started = False
    for line in lines[start:start + probe]:
        # a line that puts no date-shaped cell in the zone ends the data run: footers and
        # summary blocks below the table must not poison (or fake) column membership
        zoned = [w for w in sorted(line, key=lambda v: v.x0) if w.x1 <= right and norm_token(w.text)]
        if started and not any(spec.date_re.match(w.text.strip()) for w in zoned):
            break
        for w in zoned:
            for cl in clusters:
                if w.x0 <= max(v.x1 for v in cl) + 4.0:
                    cl.append(w)
                    break
            else:
                clusters.append([w])
            if spec.date_re.match(w.text.strip()):
                started = True
    candidates = [cl for cl in clusters
                  if len(cl) >= 2 and all(spec.date_re.match(c.text.strip()) for c in cl)]
    if len(candidates) != 1:
        return None
    cl = candidates[0]
    return min(c.x0 for c in cl), max(c.x1 for c in cl)


def _complete_without_date(line: Sequence[Word], spans: Dict[str, Tuple[float, float]],
                           spec: LayoutSpec) -> bool:
    """Every column except 'date' titled, and no token left of the first title or between titles."""
    if len(spans) != len(spec.columns) - 1 or "date" in spans:
        return False
    lo, hi = min(x[0] for x in spans.values()), max(x[1] for x in spans.values())
    for w in line:
        if not norm_token(w.text) or w.x1 > hi:
            continue
        if not any(a - 0.5 <= w.x0 and w.x1 <= b + 0.5 for a, b in spans.values()):
            return False
    return True


def find_header(lines: Sequence[Sequence[Word]], spec: LayoutSpec) -> Optional[Tuple[int, Dict[str, Tuple[float, float]]]]:
    """Index of the header row's last line holding every column title, and each title's x-span.

    When spec.header_wraps is set, a title that wraps onto the next visual line is merged into the
    candidate line (words re-sorted by x0): the pair is accepted only when the merged view completes
    the column set with no unknown tokens inside the span. The returned index is the pair's second
    line, so row scanning starts after both header lines."""
    for idx, line in enumerate(lines):
        spans = _match_spans(line, spec)
        if _complete(line, spans, spec):
            return idx, spans
        if getattr(spec, "untitled_date_column", False) and _complete_without_date(line, spans, spec):
            # every other column titled; the date column prints no title: read its span from the data rows
            dsp = _find_untitled_date(lines, spec, idx + 1, min(x[0] for x in spans.values()))
            if dsp:
                return idx, {**spans, "date": dsp}
        if getattr(spec, "header_wraps", False) and idx + 1 < len(lines) and "date" in spans and len(spans) >= 2:
            merged = _merge_header_pair(line, lines[idx + 1])
            mspans = _match_spans(merged, spec)
            if _complete(merged, mspans, spec, center_test=True):
                return idx + 1, mspans
        if getattr(spec, "header_lines", 1) > 1:
            for n in range(2, spec.header_lines + 1):
                if idx + n > len(lines):
                    break
                merged = _merge_header_lines(lines[idx:idx + n], spec.header_merge_tol)
                mspans = _match_spans(merged, spec)
                if _complete(merged, mspans, spec, center_test=True):
                    return idx + n - 1, mspans
    return None


def _implicit_row_match(line: Sequence[Word], spec: LayoutSpec) -> Optional[Dict[str, Tuple[float, float]]]:
    """Spans synthesized when a dated data line fits spec.implicit_header: every declared role in order, except that
    "narration" (and only narration) may carry no token on the dated line. Money-role cells must be amounts or the
    spec's empty marker; the first two roles must hold dates."""
    roles = spec.implicit_header
    toks = sorted((w for w in line if norm_token(w.text) or w.text.strip() == spec.empty_amount_marker), key=lambda w: w.x0)
    if len(toks) == len(roles):
        seq = roles
    elif len(toks) == len(roles) - 1:
        seq = tuple(r for r in roles if r != "narration")
    else:
        return None
    if len(toks) != len(seq):
        return None
    spans: Dict[str, Tuple[float, float]] = {}
    for role, w in zip(seq, toks):
        text = w.text.strip()
        if role in spec.amount_columns:
            if not (spec.amount_re.match(text) or text == spec.empty_amount_marker):
                return None
        elif role in ("date", spec.secondary_date_column) and not spec.date_re.match(text):
            return None
        spans[role] = (w.x0, w.x1)
    if "date" not in spans:
        return None
    if "narration" in roles and "narration" not in spans:
        i = roles.index("narration")
        left = spans[roles[i - 1]][1] + _BOUNDARY_PAD
        right = spans[roles[i + 1]][0] - _BOUNDARY_PAD
        if right <= left:
            return None
        spans["narration"] = (left, right)
    return spans if len(spans) == len(roles) else None


def find_implicit_row(lines: Sequence[Sequence[Word]], spec: LayoutSpec) -> Optional[Tuple[int, Dict[str, Tuple[float, float]]]]:
    """First dated line that fits spec.implicit_header, and the spans its own cells define. A real table repeats the
    shape: require a second conforming dated line below the first so a coincidental summary line cannot anchor."""
    for idx, line in enumerate(lines):
        spans = _implicit_row_match(line, spec)
        if not spans:
            continue
        for nxt in lines[idx + 1:]:
            if _implicit_row_match(nxt, spec):
                return idx, spans
        return None
    return None


def derive_anchors(page_words: Sequence[Word], spec: LayoutSpec, page_width: Optional[float] = None) -> ColumnAnchors:
    lines = group_lines(page_words)
    if spec.implicit_header:
        found_i = find_implicit_row(lines, spec)
        if not found_i:
            raise AnchorError("implicit table start not found")
        idx, spans = found_i
        row_line = lines[idx]
        anchor_top = min(w.top for w in row_line)
        date_sp = spans["date"]
        text_lefts = {col: spans[col][0] - spec.band_left_pad.get(col, _BOUNDARY_PAD) for col in spec.text_columns[1:]}
        return ColumnAnchors(
            layout_id=spec.layout_id,
            page_width=page_width,
            header_top=anchor_top - 12.0,          # admits the txn-type line printed just above the dated line
            header_bottom=max(w.bottom or w.top for w in row_line),
            spans=spans,
            date_left=date_sp[0] - spec.date_left_pad,
            date_right=min(date_sp[1] + _DATE_DATA_RIGHT_PAD, text_lefts.get(spec.text_columns[1], float("inf"))),
            text_lefts=text_lefts,
            amount_edges={c: spans[c][1] for c in spec.amount_columns},
            amount_lefts={c: spans[c][0] for c in spec.amount_columns},
        )
    found = find_header(lines, spec)
    if not found:
        raise AnchorError("table header not found")
    idx, spans = found
    header_line = lines[idx]
    header_top = min(w.top for w in header_line)
    header_bottom = max((w.bottom or w.top) for w in header_line)
    text_lefts = {col: spans[col][0] - spec.band_left_pad.get(col, _BOUNDARY_PAD) for col in spec.text_columns[1:]}
    # a first dated data row must sit left of the second text column after date (or anywhere when there is none)
    narration_limit = text_lefts[spec.text_columns[2]] if len(spec.text_columns) > 2 else float("inf")

    first_date: Optional[Word] = None
    header_mid = (spans["date"][0] + spans["date"][1]) / 2.0
    for line in lines[idx + 1:]:
        cands = [w for w in line if spec.date_re.match(w.text.strip()) and w.x0 < narration_limit]
        if cands:   # a line can carry several date-shaped cells (e.g. a value date left of the transaction date): take the one under the date title
            first_date = min(cands, key=lambda w: abs((w.x0 + w.x1) / 2.0 - header_mid))
            break
    if first_date:
        date_left = min(first_date.x0, spans["date"][0]) - spec.date_left_pad    # date cells may be right-aligned
        date_right = min(first_date.x1 + _DATE_DATA_RIGHT_PAD, text_lefts[spec.text_columns[1]])
    else:
        date_left = spans["date"][0] - _DATE_FALLBACK_LEFT_PAD
        date_right = spans["date"][1] + _DATE_FALLBACK_RIGHT_PAD
    return ColumnAnchors(
        layout_id=spec.layout_id,
        page_width=page_width,
        header_top=header_top,
        header_bottom=header_bottom,
        spans=spans,
        date_left=date_left,
        date_right=date_right,
        text_lefts=text_lefts,
        amount_edges={c: spans[c][1] for c in spec.amount_columns},
        amount_lefts={c: spans[c][0] for c in spec.amount_columns},
    )


def classify_word(word: Word, anchors: ColumnAnchors, spec: LayoutSpec) -> Optional[str]:
    """Column role of a data word, or None when the word is page furniture / unclassifiable. A wrapped date cell's
    continuation is reported as "date_tail" / "<secondary>_tail"."""
    text = word.text.strip()
    if word.x0 < anchors.date_left:
        return None
    if word.x0 < anchors.date_right:
        if spec.date_re.match(text):
            return "date"
        if spec.date_tail_re and spec.date_tail_re.match(text):
            return "date_tail"
        return "narration"   # undated text in the date band = narration wrap
    # a non-amount word right of the money columns belongs to a trailing column the layout does not use (e.g. branch code)
    if anchors.amount_edges and word.x0 > max(anchors.amount_edges.values()) + _TRAILING_COLUMN_GAP and not spec.amount_re.match(text):
        return None
    band = spec.text_columns[1]
    for col in spec.text_columns[1:]:
        if word.x0 >= anchors.text_lefts[col]:
            band = col
    last_band = band == spec.text_columns[-1]
    secondary = spec.secondary_date_column
    if secondary and band == secondary:
        if spec.date_re.match(text):
            return secondary
        if spec.date_tail_re and spec.date_tail_re.match(text):
            return secondary + "_tail"
        if not last_band:
            return None
    elif not last_band:
        return band
    if (spec.amount_re.match(text) or (spec.empty_amount_marker and text == spec.empty_amount_marker)
            or (spec.wrapped_amount_tokens and _WRAPPED_AMOUNT_FRAGMENT.match(text))):
        edges = anchors.amount_edges
        nearest = min(edges, key=lambda c: abs(word.x1 - edges[c]))
        # an amount must sit close to a money column's right edge; reject stray numbers elsewhere
        if spec.left_aligned_amounts:
            lefts = anchors.amount_lefts or {c: edges[c] for c in edges}
            for col in sorted(lefts, key=lefts.get, reverse=True):
                if word.x0 >= lefts[col] - 2.0:
                    return col
            return None
        if abs(word.x1 - edges[nearest]) <= _amount_tolerance(edges, nearest):
            return nearest
    return None if band == secondary else band


def _amount_tolerance(edges: Dict[str, float], name: str) -> float:
    others = [abs(edges[name] - e) for k, e in edges.items() if k != name]
    return max(20.0, min(others) * 0.5) if others else 20.0
