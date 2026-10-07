"""Word and line primitives. Pure data; no PDF library is imported here."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Sequence


@dataclass(frozen=True)
class Word:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float = 0.0


def norm_token(text: str) -> str:
    """Lower-case alphanumerics only ("Chq./Ref.No." -> "chqrefno")."""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def squash(words: Sequence[Word]) -> str:
    """Whitespace-free, case-preserving text of a line (for marker matching)."""
    return "".join(re.sub(r"\s+", "", w.text) for w in words)


def group_lines(words: Sequence[Word], tol: float = 6.0) -> List[List[Word]]:
    """Group words into visual lines by their top coordinate; words in a line are sorted left to right.

    Cells of one printed row can sit a few points apart vertically (observed up to ~5 pt), while the closest wrapped
    table lines are ~17 pt apart, so the default tolerance is 6 pt."""
    ordered = sorted(words, key=lambda w: (w.top, w.x0))
    lines: List[List[Word]] = []
    ref_top = None
    for w in ordered:
        if ref_top is None or w.top - ref_top > tol:
            lines.append([w])
            ref_top = w.top
        else:
            lines[-1].append(w)
    return [sorted(line, key=lambda w: w.x0) for line in lines]


def words_from_dicts(items: Sequence[Dict[str, float]]) -> List[Word]:
    return [Word(str(i["text"]), float(i["x0"]), float(i["x1"]), float(i["top"]), float(i.get("bottom", 0.0))) for i in items]
