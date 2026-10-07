"""Parser for the printed STATEMENT SUMMARY block (opening, Dr count, Cr count, debits, credits, closing)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Sequence

from .words import Word, norm_token

_LABELS = "openingbalancedrcountcrcountdebitscreditsclosingbal"
_NUM = re.compile(r"^-?[\d,]+(?:\.\d+)?(?:cr|dr)?$", re.I)


@dataclass(frozen=True)
class PrintedSummary:
    opening: Decimal
    dr_count: int
    cr_count: int
    debits: Decimal
    credits: Decimal
    closing: Decimal


def _dec(tok: str) -> Decimal:
    return Decimal(re.sub(r"(?i)(cr|dr)$", "", tok).replace(",", ""))


def _line_tokens(line: Sequence[Word]) -> List[str]:
    return [t for w in line for t in w.text.split() if t]


def parse_summary(lines: Sequence[Sequence[Word]]) -> Optional[PrintedSummary]:
    """Find the six column labels, then the first following line made of exactly six numbers.

    The labels can sit at the bottom of one page and the numbers at the top of the next, with unrelated numeric text
    (footer, page header) in between, so only a line consisting entirely of six numeric tokens is accepted.
    """
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
                if _LABELS.startswith(acc + n):
                    acc += n
                else:
                    acc = n if _LABELS.startswith(n) else ""
            labelled = acc == _LABELS
            continue
        if len(toks) == 6 and all(_NUM.match(t) for t in toks):
            try:
                return PrintedSummary(
                    opening=_dec(toks[0]), dr_count=int(toks[1].replace(",", "")), cr_count=int(toks[2].replace(",", "")),
                    debits=_dec(toks[3]), credits=_dec(toks[4]), closing=_dec(toks[5]),
                )
            except (ValueError, ArithmeticError):
                return None
    return None
