from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import re


_DEFAULT_FORMATS: Tuple[str, ...] = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%d-%m-%y",
    "%d/%m/%y",
    "%d.%m.%y",
    "%d %b %Y",
    "%d %b %y",
    "%d-%b-%Y",
    "%d-%b-%y",
    "%d/%b/%Y",
    "%d/%b/%y",
)

_BANK_FORMATS: Dict[str, Tuple[str, ...]] = {
    "HDFC": ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", *_DEFAULT_FORMATS),
    "SBI": ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d %b %Y", "%d %b %y", *_DEFAULT_FORMATS),
    "ICICI": (
        "%d-%m-%Y", "%d/%m/%Y", "%d-%m-%y", "%d/%m/%y",
        "%d-%b-%Y", "%d-%b-%y", "%d %b %Y", "%d %b %y",
        "%B %d, %Y", "%B %d %Y",
        *_DEFAULT_FORMATS,
    ),
    "KOTAK": ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d %b %Y", "%d %b %y", *_DEFAULT_FORMATS),
    "AXIS": ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d %b %Y", "%d %b %y", *_DEFAULT_FORMATS),
    "CANARA": ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d %b %Y", "%d %b %y", *_DEFAULT_FORMATS),
    "IDFC": ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d %b %Y", "%d %b %y", *_DEFAULT_FORMATS),
    "KARNATAKA": ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d %b %Y", "%d %b %y", *_DEFAULT_FORMATS),
    "PAYTM": ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d %b %Y", "%d %b %y", *_DEFAULT_FORMATS),
    "BANK OF BARODA": ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d %b %Y", "%d %b %y", *_DEFAULT_FORMATS),
    "BOB": ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d %b %Y", "%d %b %y", *_DEFAULT_FORMATS),
    "UNION": ("%d/%m/%Y", "%d/%m/%y", "%d-%m-%Y", "%d-%m-%y", "%d %b %Y", "%d %b %y", *_DEFAULT_FORMATS),
    "UNKNOWN": _DEFAULT_FORMATS,
}

_BANK_RANGE_TOLERANCE_DAYS: Dict[str, int] = {
    "CANARA": 1,
}

_DATE_PAIR_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?P<start>\d{1,2}[./-]\d{1,2}[./-]\d{2,4})\s*(?:to|till|through|until|[-–—])\s*(?P<end>\d{1,2}[./-]\d{1,2}[./-]\d{2,4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<start>\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})\s*(?:to|till|through|until|[-–—])\s*(?P<end>\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?:statement\s*(?:from|date from|period)|from)\s*[:\-]??\s*(?P<start>\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})\s*(?:to|till|through|until|[-–—])\s*(?P<end>\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4})",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class DateNormalizationResult:
    raw_value: Any
    iso_date: Optional[str]
    detected_format: Optional[str]
    confidence: float
    bank_name: str = ""


@dataclass
class StatementDateAudit:
    startdate: Optional[str] = None
    enddate: Optional[str] = None
    detected_date_format: Optional[str] = None
    date_confidence: float = 0.0
    status: str = "missing"
    warnings: List[str] = field(default_factory=list)
    header_startdate: Optional[str] = None
    header_enddate: Optional[str] = None
    parsed_startdate: Optional[str] = None
    parsed_enddate: Optional[str] = None
    parsed_transaction_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "startdate": self.startdate,
            "enddate": self.enddate,
            "detected_date_format": self.detected_date_format,
            "date_confidence": round(float(self.date_confidence), 4),
            "date_validation_status": self.status,
            "date_validation_warnings": list(self.warnings),
            "header_date_range": {
                "start": self.header_startdate,
                "end": self.header_enddate,
            },
            "parsed_date_range": {
                "start": self.parsed_startdate,
                "end": self.parsed_enddate,
            },
            "parsed_transaction_count": self.parsed_transaction_count,
        }


def _bank_key(bank_name: Optional[str]) -> str:
    text = str(bank_name or "").strip().upper()
    return text or "UNKNOWN"


def _formats_for_bank(bank_name: Optional[str], preferred_formats: Optional[Sequence[str]] = None) -> Tuple[str, ...]:
    if preferred_formats:
        return tuple(preferred_formats)
    bank_key = _bank_key(bank_name)
    if bank_key in _BANK_FORMATS:
        return _BANK_FORMATS[bank_key]
    return _DEFAULT_FORMATS


def _is_icici_transaction_history_layout(bank_name: Optional[str], header_text: Optional[str]) -> bool:
    if _bank_key(bank_name) != "ICICI" or not header_text:
        return False

    header = header_text.upper()
    return (
        "STATEMENT OF TRANSACTIONS IN SAVING ACCOUNT" in header
        and "TRANSACTION WITHDRAWAL DEPOSIT BALANCE" in header
    ) or (
        "TRANSACTION WITHDRAWAL DEPOSIT BALANCE" in header
        and "S NO. CHEQUE NUMBER TRANSACTION REMARKS" in header
    )


def _try_parse_with_formats(value: str, formats: Sequence[str]) -> DateNormalizationResult:
    for fmt in formats:
        try:
            dt = datetime.strptime(value, fmt)
            return DateNormalizationResult(
                raw_value=value,
                iso_date=dt.date().isoformat(),
                detected_format=fmt,
                confidence=0.98 if fmt in _DEFAULT_FORMATS[:2] else 0.93,
            )
        except ValueError:
            continue
    return DateNormalizationResult(raw_value=value, iso_date=None, detected_format=None, confidence=0.0)


def normalize_date_value(
    value: Any,
    *,
    bank_name: Optional[str] = None,
    preferred_formats: Optional[Sequence[str]] = None,
) -> DateNormalizationResult:
    if value is None:
        return DateNormalizationResult(raw_value=value, iso_date=None, detected_format=None, confidence=0.0, bank_name=_bank_key(bank_name))

    if isinstance(value, datetime):
        return DateNormalizationResult(
            raw_value=value,
            iso_date=value.date().isoformat(),
            detected_format="datetime",
            confidence=1.0,
            bank_name=_bank_key(bank_name),
        )

    if isinstance(value, date):
        return DateNormalizationResult(
            raw_value=value,
            iso_date=value.isoformat(),
            detected_format="date",
            confidence=1.0,
            bank_name=_bank_key(bank_name),
        )

    text = str(value).strip()
    if not text:
        return DateNormalizationResult(raw_value=value, iso_date=None, detected_format=None, confidence=0.0, bank_name=_bank_key(bank_name))

    bank_key = _bank_key(bank_name)
    formats = _formats_for_bank(bank_name, preferred_formats)

    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            parsed = datetime.strptime(text, "%Y-%m-%d")
            return DateNormalizationResult(
                raw_value=value,
                iso_date=parsed.date().isoformat(),
                detected_format="%Y-%m-%d",
                confidence=1.0,
                bank_name=bank_key,
            )
    except ValueError:
        pass

    try:
        if re.fullmatch(r"\d{4}/\d{2}/\d{2}", text):
            parsed = datetime.strptime(text, "%Y/%m/%d")
            return DateNormalizationResult(
                raw_value=value,
                iso_date=parsed.date().isoformat(),
                detected_format="%Y/%m/%d",
                confidence=1.0,
                bank_name=bank_key,
            )
    except ValueError:
        pass

    candidate = _try_parse_with_formats(text, formats)
    if candidate.iso_date:
        object.__setattr__(candidate, "bank_name", bank_key)
        return candidate

    if "." in text:
        dotted = _try_parse_with_formats(text, tuple(fmt for fmt in formats if "." in fmt))
        if dotted.iso_date:
            object.__setattr__(dotted, "bank_name", bank_key)
            return dotted

    return DateNormalizationResult(raw_value=value, iso_date=None, detected_format=None, confidence=0.0, bank_name=bank_key)


def extract_statement_date_range(
    text: Optional[str],
    *,
    bank_name: Optional[str] = None,
    preferred_formats: Optional[Sequence[str]] = None,
) -> Tuple[Optional[DateNormalizationResult], Optional[DateNormalizationResult]]:
    if not text:
        return None, None

    for pattern in _DATE_PAIR_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        start = normalize_date_value(match.group("start"), bank_name=bank_name, preferred_formats=preferred_formats)
        end = normalize_date_value(match.group("end"), bank_name=bank_name, preferred_formats=preferred_formats)
        if start.iso_date and end.iso_date:
            return start, end
    return None, None


def analyze_statement_dates(
    transactions: Iterable[Dict[str, Any]],
    *,
    bank_name: Optional[str] = None,
    header_start: Any = None,
    header_end: Any = None,
    header_text: Optional[str] = None,
    preferred_formats: Optional[Sequence[str]] = None,
) -> StatementDateAudit:
    bank_key = _bank_key(bank_name)
    normalizer_formats = _formats_for_bank(bank_name, preferred_formats)
    range_tolerance = timedelta(days=_BANK_RANGE_TOLERANCE_DAYS.get(bank_key, 0))
    header_agnostic = _is_icici_transaction_history_layout(bank_name, header_text)
    txn_results: List[DateNormalizationResult] = []
    warnings: List[str] = []

    for txn in transactions:
        if not isinstance(txn, dict):
            continue
        raw_value = txn.get("date") or txn.get("Date")
        result = normalize_date_value(raw_value, bank_name=bank_name, preferred_formats=normalizer_formats)
        if result.iso_date:
            txn_results.append(result)

    header_start_result = normalize_date_value(header_start, bank_name=bank_name, preferred_formats=normalizer_formats)
    header_end_result = normalize_date_value(header_end, bank_name=bank_name, preferred_formats=normalizer_formats)

    if not header_agnostic and (not header_start_result.iso_date or not header_end_result.iso_date) and header_text:
        extracted_start, extracted_end = extract_statement_date_range(
            header_text,
            bank_name=bank_name,
            preferred_formats=normalizer_formats,
        )
        if not header_start_result.iso_date and extracted_start:
            header_start_result = extracted_start
        if not header_end_result.iso_date and extracted_end:
            header_end_result = extracted_end

    parsed_dates = [r.iso_date for r in txn_results if r.iso_date]
    parsed_dates_sorted = sorted(parsed_dates)

    parsed_start = parsed_dates_sorted[0] if parsed_dates_sorted else None
    parsed_end = parsed_dates_sorted[-1] if parsed_dates_sorted else None

    chosen_start = header_start_result.iso_date or parsed_start
    chosen_end = header_end_result.iso_date or parsed_end

    chronology_ok = True
    if len(parsed_dates) > 1:
        ascending = all(parsed_dates[i] <= parsed_dates[i + 1] for i in range(len(parsed_dates) - 1))
        descending = all(parsed_dates[i] >= parsed_dates[i + 1] for i in range(len(parsed_dates) - 1))
        chronology_ok = ascending or descending
        if not chronology_ok:
            warnings.append("DATE_ORDER_SUSPECTED")

    if not header_agnostic and header_start_result.iso_date and header_end_result.iso_date and parsed_start and parsed_end:
        header_start_date = date.fromisoformat(header_start_result.iso_date)
        header_end_date = date.fromisoformat(header_end_result.iso_date)
        parsed_start_date = date.fromisoformat(parsed_start)
        parsed_end_date = date.fromisoformat(parsed_end)
        if parsed_start_date < (header_start_date - range_tolerance) or parsed_end_date > (header_end_date + range_tolerance):
            warnings.append("PARSED_RANGE_OUTSIDE_HEADER_RANGE")
    elif not header_agnostic and not header_start_result.iso_date and not header_end_result.iso_date and parsed_dates:
        warnings.append("HEADER_DATE_RANGE_MISSING")

    confidence = 0.0
    if parsed_dates:
        confidence = 0.72
    if header_start_result.iso_date and header_end_result.iso_date:
        confidence += 0.2
    if chronology_ok and parsed_dates:
        confidence += 0.05
    if parsed_dates and len({r.detected_format for r in txn_results if r.detected_format}) == 1:
        confidence += 0.03
    if warnings:
        confidence -= min(0.2 * len(warnings), 0.35)
    confidence = max(0.05, min(confidence, 0.99))

    status = "missing"
    if parsed_dates:
        status = "parsed_only"
    if header_agnostic and parsed_dates:
        status = "validated"
    if header_start_result.iso_date and header_end_result.iso_date:
        status = "validated" if not warnings else "suspect"

    detected_format = None
    if txn_results:
        format_counts: Dict[str, int] = {}
        for result in txn_results:
            if result.detected_format:
                format_counts[result.detected_format] = format_counts.get(result.detected_format, 0) + 1
        if format_counts:
            detected_format = max(format_counts.items(), key=lambda item: item[1])[0]

    return StatementDateAudit(
        startdate=chosen_start,
        enddate=chosen_end,
        detected_date_format=detected_format,
        date_confidence=confidence,
        status=status,
        warnings=warnings,
        header_startdate=header_start_result.iso_date,
        header_enddate=header_end_result.iso_date,
        parsed_startdate=parsed_start,
        parsed_enddate=parsed_end,
        parsed_transaction_count=len(parsed_dates),
    )
