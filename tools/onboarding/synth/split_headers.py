"""Emit wrapped / interleaved / centred multi-line header rows for a LayoutSpec.

Each function returns word tuples (text, x0, x1, top, bottom) for `lines_n`
visual lines 10pt apart, starting at `top`. Column x anchors are supplied by the
caller (`anchors[col]` = (x0, width)) so the same generator serves synthetic and
spec-derived geometry.

Shapes covered (docs/engine/N1_HEADER_CAPABILITIES.md):
  * two_line_wrap       every title split across two adjacent lines
  * three_line_interleave  fragments on lines 0 and 2 with an unrelated middle line
  * centred_titles      multi-word titles centred over the column, split top/bottom
"""
from typing import Dict, List, Sequence, Tuple

Word5 = Tuple[str, float, float, float, float]

_CHW = 5.5  # pt per char, same convention as tests' onboarded_kit


def _emit(tokens: Sequence[str], x0: float, top: float) -> List[Word5]:
    ws = []
    for t in tokens:
        ws.append((t, x0, x0 + _CHW * len(t), top, top + 8))
        x0 += _CHW * len(t) + 3
    return ws


def _split(tokens: Sequence[str], parts: int) -> List[List[str]]:
    """Contiguous chunks of the seq over `parts` lines, preserving order (a title
    wraps at a word boundary, its pieces stay adjacent in the merged stream)."""
    if len(tokens) <= parts:
        chunks = [[t] for t in tokens]
    else:
        per = (len(tokens) + parts - 1) // parts
        chunks = [list(tokens[i:i + per]) for i in range(0, len(tokens), per)]
    return [c for c in chunks if c]


def two_line_wrap(spec, anchors: Dict[str, Tuple[float, float]], top: float = 200.0) -> List[Word5]:
    """Each column title split across two adjacent visual lines."""
    words: List[Word5] = []
    for col, (x0, _w) in anchors.items():
        toks = spec.columns[col][0]
        halves = _split(toks, 2) if len(toks) > 1 else [list(toks), ["Cont"]]  # lone word + wrapped tail
        for i, frag in enumerate(halves):
            words += _emit(frag, x0, top + i * 10)
    return words


def three_line_interleave(spec, anchors: Dict[str, Tuple[float, float]], top: float = 200.0,
                          middle: Sequence[str] = ()) -> List[Word5]:
    """Column titles split over three visual lines; alternate columns put their
    second fragment on the middle or the bottom line, so a title can span
    non-adjacent lines while the middle line still carries title pieces."""
    words: List[Word5] = []
    cols = list(anchors.items())
    for i, (col, (x0, _w)) in enumerate(cols):
        toks = spec.columns[col][0]
        parts = _split(toks, 2)
        words += _emit(parts[0], x0, top)
        if len(parts) > 1:
            second_top = top + 10 if i % 2 else top + 20   # even cols: line 0+2 (non-adjacent)
            words += _emit(parts[1], x0, second_top)
    if middle:
        mx = max(x for x, _w in anchors.values()) + 60
        words += _emit(list(middle), mx, top + 10)
    return words


def centred_titles(spec, anchors: Dict[str, Tuple[float, float]], top: float = 200.0) -> List[Word5]:
    """Multi-word titles printed centred over the column: first word(s) centred on line 0,
    remainder centred on line 1 (x-offset differs from the left-aligned case)."""
    words: List[Word5] = []
    for col, (x0, width) in anchors.items():
        toks = spec.columns[col][0]
        parts = _split(toks, 2)
        for i, frag in enumerate(parts):
            frag_w = sum(_CHW * len(t) + 3 for t in frag) - 3
            cx = x0 + max(0.0, (width - frag_w) / 2.0)
            words += _emit(frag, cx, top + i * 10)
    return words
