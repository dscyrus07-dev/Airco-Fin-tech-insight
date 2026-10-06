"""Strict, deterministic old-vs-new statement comparator.

Never uses "close enough": any difference is classified and reported. Overall
verdict passes only on EXACT_MATCH (minor differences only pass when explicitly
allowed by the caller).
"""

from __future__ import annotations

import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .contract import (
    ContractError,
    Corpus,
    ExtractionResult,
    StatementExtractor,
)
from app.services.pipeline.models import NormalizedTransaction

logger = logging.getLogger(__name__)

ZERO = Decimal("0")


class Diff(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    MINOR_DIFFERENCE = "MINOR_DIFFERENCE"
    MAJOR_DIFFERENCE = "MAJOR_DIFFERENCE"
    MISSING_TRANSACTION = "MISSING_TRANSACTION"
    EXTRA_TRANSACTION = "EXTRA_TRANSACTION"
    BALANCE_MISMATCH = "BALANCE_MISMATCH"
    PARSER_FAILURE = "PARSER_FAILURE"


# worst first; the overall verdict is the first class present
SEVERITY_ORDER: Tuple[Diff, ...] = (
    Diff.PARSER_FAILURE,
    Diff.MAJOR_DIFFERENCE,
    Diff.MISSING_TRANSACTION,
    Diff.EXTRA_TRANSACTION,
    Diff.BALANCE_MISMATCH,
    Diff.MINOR_DIFFERENCE,
    Diff.EXACT_MATCH,
)


@dataclass(frozen=True)
class Finding:
    kind: Diff
    code: str
    detail: str
    old: Any = None
    new: Any = None

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind.value, "code": self.code, "detail": self.detail,
                "old": None if self.old is None else str(self.old),
                "new": None if self.new is None else str(self.new)}


@dataclass
class ComparisonResult:
    item_id: str
    bank_key: str
    overall: Diff
    findings: List[Finding] = field(default_factory=list)
    counts: Dict[str, int] = field(default_factory=dict)
    old_count: int = 0
    new_count: int = 0
    opening_match: Optional[bool] = None
    closing_match: Optional[bool] = None

    @property
    def exact(self) -> bool:
        return self.overall == Diff.EXACT_MATCH

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id, "bank_key": self.bank_key, "overall": self.overall.value,
            "old_count": self.old_count, "new_count": self.new_count,
            "opening_match": self.opening_match, "closing_match": self.closing_match,
            "counts": dict(self.counts), "findings": [f.to_dict() for f in self.findings],
        }


@dataclass(frozen=True)
class ComparatorConfig:
    amount_tolerance: Decimal = ZERO       # strict by default
    compare_ref_no: bool = False
    max_findings_per_item: int = 200


def _d(x: Optional[Decimal]) -> Decimal:
    return ZERO if x is None else Decimal(x)


def _norm_desc(s: str) -> str:
    return " ".join((s or "").split()).casefold()


def _eq(a: Decimal, b: Decimal, tol: Decimal) -> bool:
    return abs(a - b) <= tol


def _key(t: NormalizedTransaction) -> Tuple[str, Decimal, Decimal, Decimal]:
    return (t.date, _d(t.debit), _d(t.credit), _d(t.balance))


def _dup_count(txns: Iterable[NormalizedTransaction]) -> int:
    c = Counter((_key(t), _norm_desc(t.description)) for t in txns)
    return sum(n - 1 for n in c.values() if n > 1)


def compare_results(
    item_id: str, bank_key: str, old: ExtractionResult, new: ExtractionResult, cfg: Optional[ComparatorConfig] = None
) -> ComparisonResult:
    """Compare two RAW extraction results for the same statement."""
    cfg = cfg or ComparatorConfig()
    old.validate()
    new.validate()
    tol = cfg.amount_tolerance
    f: List[Finding] = []

    def add(kind: Diff, code: str, detail: str, o: Any = None, n: Any = None) -> None:
        f.append(Finding(kind, code, detail, o, n))

    res = ComparisonResult(item_id=item_id, bank_key=bank_key, overall=Diff.EXACT_MATCH,
                           old_count=len(old.transactions), new_count=len(new.transactions))

    if old.failure or new.failure:
        if old.failure:
            add(Diff.PARSER_FAILURE, "OLD_FAILED", "old extractor failed", old.failure, None)
        if new.failure:
            add(Diff.PARSER_FAILURE, "NEW_FAILED", "new extractor failed", None, new.failure)
        return _finish(res, f, cfg)

    om, nm = old.metadata, new.metadata
    # ---- statement level
    if (om.bank_key or "") != (nm.bank_key or ""):
        add(Diff.MAJOR_DIFFERENCE, "BANK_KEY", "bank differs", om.bank_key, nm.bank_key)
    for fld in ("statement_from", "statement_to"):
        a, b = getattr(om, fld) or "", getattr(nm, fld) or ""
        if a != b:
            kind = Diff.MAJOR_DIFFERENCE if (a and b) else Diff.MINOR_DIFFERENCE
            add(kind, fld.upper(), f"{fld} differs", a, b)
    for fld, attr in (("opening_balance", "opening_match"), ("closing_balance", "closing_match")):
        a, b = _d(getattr(om, fld)), _d(getattr(nm, fld))
        ok = _eq(a, b, tol)
        setattr(res, attr, ok)
        if not ok:
            add(Diff.BALANCE_MISMATCH, fld.upper(), f"{fld} differs", a, b)
    if (om.account_number or "") != (nm.account_number or ""):
        add(Diff.MINOR_DIFFERENCE, "ACCOUNT_NUMBER", "account number differs", om.account_number, nm.account_number)

    ot, nt = old.transactions, new.transactions
    if len(ot) != len(nt):
        add(Diff.MAJOR_DIFFERENCE, "TXN_COUNT", "transaction count differs", len(ot), len(nt))
    o_deb, n_deb = sum(1 for t in ot if _d(t.debit) > 0), sum(1 for t in nt if _d(t.debit) > 0)
    o_cr, n_cr = sum(1 for t in ot if _d(t.credit) > 0), sum(1 for t in nt if _d(t.credit) > 0)
    if o_deb != n_deb:
        add(Diff.MAJOR_DIFFERENCE, "DEBIT_COUNT", "debit count differs", o_deb, n_deb)
    if o_cr != n_cr:
        add(Diff.MAJOR_DIFFERENCE, "CREDIT_COUNT", "credit count differs", o_cr, n_cr)
    o_sd, n_sd = sum((_d(t.debit) for t in ot), ZERO), sum((_d(t.debit) for t in nt), ZERO)
    o_sc, n_sc = sum((_d(t.credit) for t in ot), ZERO), sum((_d(t.credit) for t in nt), ZERO)
    if not _eq(o_sd, n_sd, tol):
        add(Diff.MAJOR_DIFFERENCE, "TOTAL_DEBIT", "total debits differ", o_sd, n_sd)
    if not _eq(o_sc, n_sc, tol):
        add(Diff.MAJOR_DIFFERENCE, "TOTAL_CREDIT", "total credits differ", o_sc, n_sc)
    # printed totals: each engine must agree with what the statement prints, when known
    for eng, r, sd, sc in (("OLD", old, o_sd, o_sc), ("NEW", new, n_sd, n_sc)):
        if r.printed_total_debit is not None and not _eq(sd, _d(r.printed_total_debit), tol):
            add(Diff.MAJOR_DIFFERENCE, f"{eng}_PRINTED_DEBIT", "sum of debits != printed total", sd, r.printed_total_debit)
        if r.printed_total_credit is not None and not _eq(sc, _d(r.printed_total_credit), tol):
            add(Diff.MAJOR_DIFFERENCE, f"{eng}_PRINTED_CREDIT", "sum of credits != printed total", sc, r.printed_total_credit)
    od, nd = _dup_count(ot), _dup_count(nt)
    if od != nd:
        add(Diff.MAJOR_DIFFERENCE, "DUPLICATES", "duplicate-transaction count differs", od, nd)
    if old.verification_status != new.verification_status and (old.verification_status or new.verification_status):
        add(Diff.MAJOR_DIFFERENCE, "VERIFICATION", "verification verdict differs",
            old.verification_status, new.verification_status)

    # ---- transaction level: exact-key matching, then classify leftovers
    o_idx: Dict[Tuple, List[int]] = defaultdict(list)
    n_idx: Dict[Tuple, List[int]] = defaultdict(list)
    for i, t in enumerate(ot):
        o_idx[_key(t)].append(i)
    for j, t in enumerate(nt):
        n_idx[_key(t)].append(j)
    matched: List[Tuple[int, int]] = []
    o_left: List[int] = []
    n_left: List[int] = []
    for k in sorted(set(o_idx) | set(n_idx), key=lambda x: (x[0], str(x[1]), str(x[2]), str(x[3]))):
        a, b = o_idx.get(k, []), n_idx.get(k, [])
        m = min(len(a), len(b))
        matched += list(zip(a[:m], b[:m]))
        o_left += a[m:]
        n_left += b[m:]
    for i, j in matched:
        a, b = ot[i], nt[j]
        if _norm_desc(a.description) != _norm_desc(b.description):
            add(Diff.MINOR_DIFFERENCE, "DESCRIPTION", f"row {i}: description differs", a.description, b.description)
        if cfg.compare_ref_no and (a.ref_no or "") != (b.ref_no or ""):
            add(Diff.MINOR_DIFFERENCE, "REF_NO", f"row {i}: ref_no differs", a.ref_no, b.ref_no)
    # leftovers: same date+balance but different amounts -> MAJOR; same date+amounts but different balance -> BALANCE
    def pair(o_ids: List[int], n_ids: List[int], sel, kind: Diff, code: str, msg: str):
        bucket: Dict[Any, List[int]] = defaultdict(list)
        for j in n_ids:
            bucket[sel(nt[j])].append(j)
        rem_o, used = [], set()
        for i in o_ids:
            c = bucket.get(sel(ot[i]))
            if c:
                j = c.pop(0)
                used.add(j)
                add(kind, code, f"row {i}: {msg}", _key(ot[i]), _key(nt[j]))
            else:
                rem_o.append(i)
        return rem_o, [j for j in n_ids if j not in used]
    o_left, n_left = pair(o_left, n_left, lambda t: (t.date, _d(t.balance)), Diff.MAJOR_DIFFERENCE,
                          "AMOUNT_DIFF", "debit/credit differs for the same date and balance")
    o_left, n_left = pair(o_left, n_left, lambda t: (t.date, _d(t.debit), _d(t.credit)), Diff.BALANCE_MISMATCH,
                          "ROW_BALANCE", "running balance differs for the same date and amounts")
    for i in o_left:
        add(Diff.MISSING_TRANSACTION, "MISSING", f"old row {i} not in new output", _key(ot[i]), None)
    for j in n_left:
        add(Diff.EXTRA_TRANSACTION, "EXTRA", f"new row {j} not in old output", None, _key(nt[j]))
    # ordering: identical multiset (nothing missing/extra) but different sequence
    if not o_left and not n_left and not any(x.code in ("AMOUNT_DIFF", "ROW_BALANCE") for x in f):
        if [_key(t) for t in ot] != [_key(t) for t in nt]:
            add(Diff.MINOR_DIFFERENCE, "ORDERING", "same transactions in a different order")
    return _finish(res, f, cfg)


def _finish(res: ComparisonResult, findings: List[Finding], cfg: ComparatorConfig) -> ComparisonResult:
    counts: Counter = Counter(x.kind.value for x in findings)
    res.counts = dict(counts)
    for kind in SEVERITY_ORDER:
        if counts.get(kind.value):
            res.overall = kind
            break
    else:
        res.overall = Diff.EXACT_MATCH
    res.findings = findings[: cfg.max_findings_per_item]
    return res


def _safe_extract(ex: StatementExtractor, path: str, password: Optional[str]) -> ExtractionResult:
    from app.services.pipeline.models import StatementMetadata
    try:
        r = ex.extract(path, password)
        r.validate()
        return r
    except ContractError:
        raise
    except Exception as exc:  # noqa: BLE001 — per-file isolation; never log the password
        return ExtractionResult(engine=getattr(ex, "name", "?"), metadata=StatementMetadata(bank_name="", bank_key=""),
                                transactions=[], failure=f"{type(exc).__name__}: {exc}")


@dataclass
class ParityReport:
    results: List[ComparisonResult]
    allow_minor: bool = False

    def passed(self, r: ComparisonResult) -> bool:
        return r.overall == Diff.EXACT_MATCH or (self.allow_minor and r.overall == Diff.MINOR_DIFFERENCE)

    def summary(self) -> Dict[str, Any]:
        n = len(self.results)
        by = Counter(r.overall.value for r in self.results)
        ok = sum(1 for r in self.results if self.passed(r))
        scored = [r for r in self.results if r.overall != Diff.PARSER_FAILURE]
        return {
            "files": n, "passed": ok, "failed": n - ok, "by_class": {k.value: by.get(k.value, 0) for k in SEVERITY_ORDER},
            "opening_balance_match": f"{sum(1 for r in scored if r.opening_match)}/{len(scored)}",
            "closing_balance_match": f"{sum(1 for r in scored if r.closing_match)}/{len(scored)}",
            "transaction_count_match": f"{sum(1 for r in scored if r.old_count == r.new_count)}/{len(scored)}",
        }

    def by_bank(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in self.results:
            out[r.bank_key][r.overall.value] += 1
        return {k: dict(v) for k, v in out.items()}

    def to_markdown(self) -> str:
        s = self.summary()
        lines = ["# Parity report", "", f"Files tested: {s['files']}  |  passed: {s['passed']}  |  failed: {s['failed']}", ""]
        for k, v in s["by_class"].items():
            lines.append(f"- {k}: {v}")
        lines += ["", f"Opening balance: {s['opening_balance_match']}", f"Closing balance: {s['closing_balance_match']}",
                  f"Transaction count: {s['transaction_count_match']}", "", "## By bank"]
        for b, c in sorted(self.by_bank().items()):
            lines.append(f"- {b}: " + ", ".join(f"{k}={v}" for k, v in sorted(c.items())))
        bad = [r for r in self.results if not self.passed(r)]
        if bad:
            lines += ["", "## Failures"]
            for r in bad:
                lines.append(f"- {r.item_id} [{r.bank_key}] {r.overall.value}: " +
                             "; ".join(f"{x.code}" for x in r.findings[:6]))
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {"summary": self.summary(), "by_bank": self.by_bank(), "results": [r.to_dict() for r in self.results]}


def run_parity(corpus: Corpus, old: StatementExtractor, new: StatementExtractor,
               cfg: Optional[ComparatorConfig] = None, allow_minor: bool = False) -> ParityReport:
    """Run both extractors over every corpus item with per-file failure isolation."""
    results: List[ComparisonResult] = []
    for item in corpus:
        o = _safe_extract(old, item.pdf_path, item.password)
        n = _safe_extract(new, item.pdf_path, item.password)
        results.append(compare_results(item.item_id, item.bank_key, o, n, cfg))
    return ParityReport(results=results, allow_minor=allow_minor)
