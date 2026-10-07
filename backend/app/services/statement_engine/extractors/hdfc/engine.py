"""Pure HDFC V2 extraction over pages of words (no PDF library). The pdfplumber glue is in extractor.py."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

from .anchors import AnchorError, ColumnAnchors, derive_anchors
from .checks import Checks, run_checks
from .layout_spec import HDFC_LAYOUT_A, LayoutSpec
from .normalize import NormalizedRow, normalize_rows
from .rows import AssembledTable, Page, assemble
from .summary import PrintedSummary, parse_summary
from .words import Word, group_lines, norm_token, squash

# failure codes (design section 13)
NO_TABLE_HEADER = "NO_TABLE_HEADER"
NO_ROWS = "NO_ROWS"


@dataclass
class V2Outcome:
    failure: Optional[str] = None
    failure_detail: str = ""
    rows: List[NormalizedRow] = field(default_factory=list)
    anchors: Optional[ColumnAnchors] = None
    table: Optional[AssembledTable] = None
    period: Optional[Tuple[str, str]] = None
    summary: Optional[PrintedSummary] = None
    checks: Optional[Checks] = None
    account_number: str = ""
    ifsc: str = ""
    warnings: List[str] = field(default_factory=list)


def _account_number(page_words: Sequence[Word], spec: LayoutSpec) -> str:
    for line in group_lines(page_words):
        for i, w in enumerate(line):
            if norm_token(w.text) == spec.account_label:
                for nxt in line[i + 1:]:
                    t = nxt.text.strip()
                    if t and t != ":" and re.fullmatch(r"\d{6,}", t):
                        return t
    return ""


def extract_pages(pages: Sequence[Page], spec: LayoutSpec = HDFC_LAYOUT_A) -> V2Outcome:
    out = V2Outcome()
    if not pages:
        out.failure, out.failure_detail = NO_TABLE_HEADER, "no pages"
        return out
    first = pages[0]
    try:
        anchors = derive_anchors(first.words, spec, first.width)
    except AnchorError as exc:
        out.failure, out.failure_detail = NO_TABLE_HEADER, str(exc)
        return out
    out.anchors = anchors
    table = assemble(pages, anchors, spec)
    out.table = table
    out.period = table.period
    out.warnings.extend(table.warnings)
    page1_text = "".join(squash(line) for line in group_lines(first.words))
    m = spec.ifsc_re.search(page1_text)
    out.ifsc = m.group(0) if m else ""
    out.account_number = _account_number(first.words, spec)
    out.summary = parse_summary(table.summary_lines) if table.summary_lines else None
    rows, errors = normalize_rows(table.rows, spec)
    out.rows = rows
    if not table.rows and not (out.summary and out.summary.dr_count == 0 and out.summary.cr_count == 0):
        out.failure, out.failure_detail = NO_ROWS, "header found but no transaction rows"
        return out
    out.checks = run_checks(rows, out.period, out.summary, errors, out.warnings)
    return out
