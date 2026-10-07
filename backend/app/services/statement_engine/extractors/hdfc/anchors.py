"""Column anchors derived from the table header on the first page that carries it (HDFC prints the header once).

Geometry is read from the document. Nothing is hard-coded: page width differs between files (638 and 595 pt seen).
"""
from __future__ import annotations

from dataclasses import dataclass
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
    ref_left: float                            # narration | reference boundary
    value_left: float                          # reference | value-date boundary
    amount_edges: Dict[str, float]             # money column -> right edge of its header title


class AnchorError(ValueError):
    pass


# Margin between a header title and the first character of its data cell column boundary
_BOUNDARY_PAD = 4.0
_DATE_FALLBACK_LEFT_PAD = 8.0
_DATE_FALLBACK_RIGHT_PAD = 10.0
_DATE_DATA_LEFT_PAD = 3.0
_DATE_DATA_RIGHT_PAD = 3.0


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
            return tokens[i][1], tokens[i + n - 1][2]
    return None


def find_header(lines: Sequence[Sequence[Word]], spec: LayoutSpec) -> Optional[Tuple[int, Dict[str, Tuple[float, float]]]]:
    """Index of the first line holding every column title, and each title's x-span."""
    for idx, line in enumerate(lines):
        toks = _tokens(line)
        spans: Dict[str, Tuple[float, float]] = {}
        for col, alternatives in spec.columns.items():
            for seq in alternatives:
                hit = _find_sequence(toks, seq)
                if hit:
                    spans[col] = hit
                    break
        if len(spans) == len(spec.columns):
            return idx, spans
    return None


def derive_anchors(page_words: Sequence[Word], spec: LayoutSpec, page_width: Optional[float] = None) -> ColumnAnchors:
    lines = group_lines(page_words)
    found = find_header(lines, spec)
    if not found:
        raise AnchorError("table header not found")
    idx, spans = found
    header_line = lines[idx]
    header_top = min(w.top for w in header_line)
    header_bottom = max((w.bottom or w.top) for w in header_line)
    ref_left = spans["ref"][0] - _BOUNDARY_PAD
    value_left = spans["value_date"][0] - _BOUNDARY_PAD

    first_date: Optional[Word] = None
    for line in lines[idx + 1:]:
        for w in line:
            if spec.date_re.match(w.text.strip()) and w.x0 < ref_left:
                first_date = w
                break
        if first_date:
            break
    if first_date:
        date_left = first_date.x0 - _DATE_DATA_LEFT_PAD
        date_right = first_date.x1 + _DATE_DATA_RIGHT_PAD
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
        ref_left=ref_left,
        value_left=value_left,
        amount_edges={c: spans[c][1] for c in spec.amount_columns},
    )


def classify_word(word: Word, anchors: ColumnAnchors, spec: LayoutSpec) -> Optional[str]:
    """Column of a data word, or None when the word is page furniture / unclassifiable."""
    text = word.text.strip()
    if word.x0 < anchors.date_left:
        return None
    if word.x0 < anchors.date_right:
        return "date" if spec.date_re.match(text) else "narration"   # undated text in the date band = narration wrap
    if word.x0 < anchors.ref_left:
        return "narration"
    if word.x0 < anchors.value_left:
        return "ref"
    if spec.date_re.match(text):
        return "value_date"
    if spec.amount_re.match(text):
        edges = anchors.amount_edges
        nearest = min(edges, key=lambda c: abs(word.x1 - edges[c]))
        # an amount must sit close to a money column's right edge; reject stray numbers elsewhere
        gap = abs(word.x1 - edges[nearest])
        limit = _amount_tolerance(edges, nearest)
        return nearest if gap <= limit else None
    return None


def _amount_tolerance(edges: Dict[str, float], name: str) -> float:
    others = [abs(edges[name] - e) for k, e in edges.items() if k != name]
    return max(20.0, min(others) * 0.5) if others else 20.0
