"""T3 universal reader entry point.

read(pdf_path) -> UniversalResult. Never raises: any exception, budget overrun or
undecidable structure returns a FAILED result with a reason code. The verdict is
capped at REVIEW with the GENERAL_READER code — T3 cannot produce VERIFIED.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import List, Optional

from ..extraction.engine import V2Outcome, extract_pages
from ..extraction.pdf_extractor import read_pages
from ..extraction.words import group_lines

from . import infer as _infer
from .lexicon import CID_RE

GENERAL_READER = "GENERAL_READER"

# failure / t0 codes
NO_TEXT_LAYER = "NO_TEXT_LAYER"
GLYPH_DUMP = "GLYPH_DUMP"
LOCKED = "LOCKED"
READ_ERROR = "READ_ERROR"
TOO_MANY_PAGES = "TOO_MANY_PAGES"
TIME_BUDGET = "TIME_BUDGET"
NON_STATEMENT = "NON_STATEMENT"

MAX_PAGES = 120
BUDGET_S = 20.0
MIN_WORDS_PER_PAGE = 15


@dataclass
class UniversalResult:
    verdict: str                       # REVIEW | FAILED | T0 codes are verdicts too
    code: str = ""                     # GENERAL_READER or failure code
    detail: str = ""
    outcome: Optional[V2Outcome] = None
    notes: List[str] = field(default_factory=list)
    meta: dict = field(default_factory=dict)
    elapsed_s: float = 0.0
    bank_hint: str = "Unknown bank"    # detector's bank if the caller supplies one

    @property
    def ok(self) -> bool:
        return self.verdict == "REVIEW" and (
            (self.outcome is not None and bool(self.outcome.rows)) or bool(self.meta.get("rows")))


def _is_password(exc: BaseException) -> bool:
    seen, stack = [], [exc]
    while stack and len(seen) < 6:
        e = stack.pop()
        seen.append(e)
        text = f"{type(e).__name__} {e}"
        if "Password" in text or "Encrypt" in text or "encrypt" in text:
            return True
        stack.extend(a for a in getattr(e, "args", ()) if isinstance(a, BaseException))
        if e.__cause__ is not None:
            stack.append(e.__cause__)
    return False


def read(pdf_path: Optional[str] = None, password: Optional[str] = None,
           budget_s: float = BUDGET_S, max_pages: int = MAX_PAGES,
           bank_hint: str = "Unknown bank", pages=None) -> UniversalResult:
    t0 = time.monotonic()
    res = UniversalResult(verdict="FAILED", code="", bank_hint=bank_hint)

    def over(code: str, detail: str):
        res.verdict, res.code, res.detail = "FAILED", code, detail
        res.elapsed_s = time.monotonic() - t0
        return res

    if pages is None:
        try:
            pages = read_pages(pdf_path, password)
        except Exception as exc:
            return over(LOCKED if _is_password(exc) else READ_ERROR, type(exc).__name__)
    if not pages:
        return over(NO_TEXT_LAYER, "no pages")
    if len(pages) > max_pages:
        return over(TOO_MANY_PAGES, f"{len(pages)} pages > cap {max_pages}")
    total_words = sum(len(p.words) for p in pages)
    if total_words == 0:
        return over(NO_TEXT_LAYER, "no text layer")
    cid = sum(1 for p in pages for w in p.words if CID_RE.match(w.text.strip()))
    if cid > max(20, total_words * 0.3):
        return over(GLYPH_DUMP, f"{cid} cid tokens")
    if total_words / len(pages) < MIN_WORDS_PER_PAGE:
        return over(NO_TEXT_LAYER, f"{total_words} words over {len(pages)} pages")
    res.meta["pages"] = len(pages)
    res.meta["words"] = total_words

    try:
        inf = _infer.infer(pages)
    except Exception as exc:
        return over("INFER_ERROR", type(exc).__name__)
    res.notes = list(inf.notes)
    res.meta.update(inf.meta)
    if inf.failure:
        return over(inf.failure, inf.detail)
    if time.monotonic() - t0 > budget_s:
        return over(TIME_BUDGET, f"inference took >{budget_s}s")

    try:
        outcome = extract_pages(pages, inf.spec)
    except Exception as exc:
        return over("EXTRACT_ERROR", type(exc).__name__)
    res.elapsed_s = time.monotonic() - t0
    res.outcome = outcome
    if res.elapsed_s > budget_s:
        return over(TIME_BUDGET, f"extraction took {res.elapsed_s:.1f}s")

    if outcome.failure:
        return over(outcome.failure, outcome.failure_detail)
    checks = outcome.checks
    v = checks.verdict if checks else "FAILED"
    res.meta["checks_verdict"] = v
    res.meta["check_results"] = {k: r.status for k, r in checks.results.items()} if checks else {}
    res.meta["rows"] = len(outcome.rows)
    if v == "FAILED":
        res.verdict, res.code = "FAILED", "CHECKS_FAILED"
        res.detail = "; ".join(checks.reasons[:4]) if checks else ""
        return res
    # VERIFIED is not reachable for T3: cap at REVIEW either way.
    res.verdict, res.code = "REVIEW", GENERAL_READER
    res.detail = "capped from VERIFIED" if v == "VERIFIED" else "; ".join(checks.reasons[:4])
    return res


def quick_verdict(pdf_path: str, **kw) -> str:
    return read(pdf_path, **kw).verdict
