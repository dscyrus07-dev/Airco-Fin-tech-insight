"""Parser for the printed STATEMENT SUMMARY block (opening, Dr count, Cr count, debits, credits, closing)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Sequence

from .layout_spec import LayoutSpec
from .words import Word, norm_token

_NUM = re.compile(r"^-?[\d,]+(?:\.\d+)?(?:cr|dr)?$", re.I)


@dataclass(frozen=True)
class PrintedSummary:
    """Printed summary numbers; a field the layout does not print is None."""
    opening: Optional[Decimal] = None
    dr_count: Optional[int] = None
    cr_count: Optional[int] = None
    debits: Optional[Decimal] = None
    credits: Optional[Decimal] = None
    closing: Optional[Decimal] = None


def _dec(tok: str) -> Decimal:
    return Decimal(re.sub(r"(?i)(cr|dr)$", "", tok).replace(",", ""))


def _line_tokens(line: Sequence[Word]) -> List[str]:
    return [t for w in line for t in w.text.split() if t]


def parse_summary(lines: Sequence[Sequence[Word]], spec: LayoutSpec) -> Optional[PrintedSummary]:
    """Find the summary column labels (spec.summary_label_text), then the first following line made of exactly
    len(spec.summary_fields) numbers.

    The labels can sit at the bottom of one page and the numbers at the top of the next, with unrelated numeric text
    (footer, page header) in between, so only a line consisting entirely of that many numeric tokens is accepted.
    """
    labels = spec.summary_label_text
    fields = spec.summary_fields
    acc = ""
    labelled = False
    for line in lines:
        toks = _line_tokens(line)
        if not labelled:
            for t in toks:
                if _NUM.match(t):
                    acc = ""
                    continue
                n = norm_token(t)
                if not n:
                    continue
                if labels.startswith(acc + n):
                    acc += n
                else:
                    acc = n if labels.startswith(n) else ""
            labelled = acc == labels
            continue
        if len(toks) == len(fields) and all(_NUM.match(t) for t in toks):
            try:
                values = {}
                for name, tok in zip(fields, toks):
                    values[name] = int(tok.replace(",", "")) if name in ("dr_count", "cr_count") else _dec(tok)
                return PrintedSummary(**values)
            except (ValueError, ArithmeticError, TypeError):
                return None
    return None
