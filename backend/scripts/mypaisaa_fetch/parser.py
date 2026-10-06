"""Robust parser for MyPaisaa customerbankdetails API responses.

The API returns ``{"status": ..., "message": ..., "data": [...], "timeStamp": ...}``
where ``data`` holds all statements for the user. Because the exact statement
object schema is not documented, this parser walks the payload recursively and
collects every statement-like record it can identify:

- any http(s) URL value in URL-ish keys (or any key) becomes a statement URL
- password-like keys supply the statement password
- id/name-like keys supply statement identifiers and filename hints
- date-like keys supply pull/statement timestamps

It never assumes a fixed index or a single statement per user. Passwords are
kept on the record objects only; they are never logged.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from .models import StatementRecord

_URL_KEYS = {
    "url", "uri", "link", "href", "file", "document", "doc", "statement",
    "pdf", "s3_url", "s3url", "file_url", "fileurl", "document_url",
    "documenturl", "doc_url", "docurl", "download_url", "downloadurl",
    "statement_url", "statementurl", "statement_link", "pdf_url", "pdfurl",
    "attachment", "attachment_url", "location", "path",
}
_PASSWORD_KEYS = {
    "password", "passwd", "pwd", "pass", "statement_password",
    "statementpassword", "pdf_password", "pdfpassword", "file_password",
    "filepassword", "doc_password", "docpassword", "document_password",
}
_ID_KEYS = {
    "statement_id", "statementid", "id", "doc_id", "docid", "document_id",
    "documentid", "file_id", "fileid", "uuid", "guid",
}
_NAME_KEYS = {
    "filename", "file_name", "filename", "document_name", "documentname",
    "doc_name", "docname", "name", "title", "document", "doc", "file",
    "statement_name", "storenode", "filetype",
}
_BANK_KEYS = {"bankname", "bank_name", "bank", "bankcode", "bank_code"}
_ACCOUNT_KEYS = {"accounttype", "account_type"}
# High-priority pull-date keys (docStore.createdate is the actual pull time;
# createdDate is a system constant and only used as fallback).
_PULL_DATE_KEYS = {
    "createdate", "created_at", "createdat", "created_on", "createdon",
    "pulled_at", "pulledat", "pull_date", "pulldate", "uploaded_at",
    "uploadedat", "upload_date", "generated_at", "generatedat",
}
_DATE_KEYS = _PULL_DATE_KEYS | {
    "created_date", "createddate", "created", "statement_date",
    "statementdate", "date", "datetime", "timestamp", "time_stamp",
    "from_date", "fromdate", "start_date", "startdate", "to_date", "todate",
    "end_date", "enddate",
}

_MAX_DEPTH = 12


def _is_url(value: str) -> bool:
    if not value.startswith(("http://", "https://")):
        return False
    try:
        parts = urlsplit(value)
        return bool(parts.netloc)
    except ValueError:
        return False


def _match(key: str, candidates: set[str]) -> bool:
    return key.strip().lower().replace("-", "_").replace(" ", "_") in candidates


class _Candidate:
    __slots__ = (
        "url", "statement_id", "filename_hint", "password", "pulled_at",
        "statement_date", "bank_name", "account_type",
    )

    def __init__(self):
        self.url: str | None = None
        self.statement_id: str | None = None
        self.filename_hint: str | None = None
        self.password: str | None = None
        self.pulled_at: str | None = None
        self.statement_date: str | None = None
        self.bank_name: str | None = None
        self.account_type: str | None = None


def _stringify(value) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _scan_dict(node: dict) -> _Candidate:
    cand = _Candidate()
    fallback_pulled_at: str | None = None
    for key, value in node.items():
        if not isinstance(key, str):
            continue
        lk = key.strip().lower().replace("-", "_").replace(" ", "_")
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                continue
            if _is_url(stripped) and (_match(lk, _URL_KEYS) or cand.url is None):
                if cand.url is None or _match(lk, _URL_KEYS):
                    cand.url = stripped
            elif _match(lk, _PASSWORD_KEYS):
                cand.password = stripped
            elif _match(lk, _ID_KEYS):
                if cand.statement_id is None:
                    cand.statement_id = stripped
            elif _match(lk, _NAME_KEYS):
                if cand.filename_hint is None:
                    cand.filename_hint = stripped
            elif _match(lk, _BANK_KEYS):
                cand.bank_name = stripped
            elif _match(lk, _ACCOUNT_KEYS):
                cand.account_type = stripped
            elif _match(lk, _PULL_DATE_KEYS):
                cand.pulled_at = cand.pulled_at or stripped
            elif _match(lk, _DATE_KEYS):
                if "date" in lk and ("from" in lk or "start" in lk or "statement" in lk):
                    cand.statement_date = cand.statement_date or stripped
                else:
                    fallback_pulled_at = fallback_pulled_at or stripped
        elif isinstance(value, (int, float)):
            if _match(lk, _PASSWORD_KEYS):
                cand.password = _stringify(value)
            elif _match(lk, _ID_KEYS):
                cand.statement_id = _stringify(value)
    cand.pulled_at = cand.pulled_at or fallback_pulled_at
    return cand


def _walk(node, user_id: str, depth: int, inherited: _Candidate, records: list[StatementRecord]):
    if depth > _MAX_DEPTH:
        return
    if isinstance(node, list):
        for item in node:
            _walk(item, user_id, depth + 1, inherited, records)
        return
    if not isinstance(node, dict):
        return

    cand = _scan_dict(node)
    # Inherit password/dates/bank info from an enclosing object when missing.
    if cand.password is None:
        cand.password = inherited.password
    if cand.pulled_at is None:
        cand.pulled_at = inherited.pulled_at
    if cand.bank_name is None:
        cand.bank_name = inherited.bank_name
    if cand.account_type is None:
        cand.account_type = inherited.account_type

    nested = [value for value in node.values() if isinstance(value, (dict, list))]

    if cand.url:
        records.append(
            StatementRecord(
                user_id=user_id,
                statement_id=cand.statement_id,
                source_url=cand.url,
                password=cand.password,
                filename_hint=cand.filename_hint,
                pulled_at=cand.pulled_at,
                statement_date=cand.statement_date,
                bank_name=cand.bank_name,
                account_type=cand.account_type,
                raw_index=len(records),
            )
        )
        # Do not descend further: this object already yielded its statement.
        return

    if cand.filename_hint and not nested:
        # Document name without a URL (e.g. {"document": "AccountStatement_..."}).
        records.append(
            StatementRecord(
                user_id=user_id,
                statement_id=cand.statement_id or cand.filename_hint,
                source_url=None,
                password=cand.password,
                filename_hint=cand.filename_hint,
                pulled_at=cand.pulled_at,
                statement_date=cand.statement_date,
                bank_name=cand.bank_name,
                account_type=cand.account_type,
                raw_index=len(records),
            )
        )
        return

    for value in nested:
        _walk(value, user_id, depth + 1, cand, records)


def extract_statements(user_id: str, payload: dict) -> list[StatementRecord]:
    """Extract every statement record from an API response payload."""
    records: list[StatementRecord] = []
    data = payload.get("data", payload) if isinstance(payload, dict) else payload
    _walk(data, user_id, 0, _Candidate(), records)

    # De-duplicate identical documents within the same user (keep first).
    # Compare by URL path: presigned query params differ per request.
    seen_urls: set[str] = set()
    unique: list[StatementRecord] = []
    for record in records:
        if record.source_url:
            key = record.source_url.split("?", 1)[0]
            if key in seen_urls:
                continue
            seen_urls.add(key)
        unique.append(record)
    return unique
