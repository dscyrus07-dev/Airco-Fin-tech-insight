"""User list input loading and validation (CSV / XLSX)."""

from __future__ import annotations

import csv
from pathlib import Path

from .logging_utils import get_logger
from .models import InputUser, InputValidation

logger = get_logger(__name__)

_HEADER_ALIASES = {
    "user_id",
    "userid",
    "user id",
    "customer_id",
    "customerid",
    "customer id",
    "id",
    "user",
    "customer",
}


def _looks_like_header(row: list[str]) -> str | None:
    """Return the header cell matching a known user-id column name."""
    for cell in row:
        if cell.strip().lower() in _HEADER_ALIASES:
            return cell.strip()
    return None


def _load_csv(path: Path) -> list[list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = []
        for row in csv.reader(fh):
            rows.append([cell.strip() for cell in row])
        return rows


def _load_xlsx(path: Path) -> list[list[str]]:
    from openpyxl import load_workbook

    wb = load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = []
    for row in ws.iter_rows(values_only=True):
        cells = []
        for value in row:
            if value is None:
                cells.append("")
            elif isinstance(value, float) and value.is_integer():
                cells.append(str(int(value)))  # 656296.0 -> "656296"
            else:
                cells.append(str(value).strip())
        rows.append(cells)  # keep fully-empty rows so they count as blank
    wb.close()
    return rows


def load_users(path: Path) -> InputValidation:
    """Load and validate the user list.

    - ignores blank rows
    - trims whitespace
    - detects a header row (known user-id column names)
    - detects duplicate user IDs (first occurrence wins)
    - preserves the trimmed user ID exactly for API requests
    """
    validation = InputValidation()
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        rows = _load_xlsx(path)
    else:
        rows = _load_csv(path)

    validation.total_rows = len(rows)
    if not rows:
        return validation

    id_column = 0
    data_rows = rows
    header = _looks_like_header(rows[0])
    extra_columns: dict[int, str] = {}
    if header is not None:
        id_column = rows[0].index(header)
        for col, name in enumerate(rows[0]):
            if col != id_column and name.strip():
                extra_columns[col] = name.strip().lower()
        data_rows = rows[1:]

    seen: set[str] = set()
    users_by_id: dict[str, InputUser] = {}
    for offset, row in enumerate(data_rows, start=2):
        if id_column >= len(row):
            validation.blank_rows += 1
            continue
        raw = row[id_column].strip()
        if raw.endswith(".0") and raw[:-2].isdigit():
            raw = raw[:-2]
        if not raw:
            validation.blank_rows += 1
            continue
        if any(sep in raw for sep in (" ", ",", ";")):
            validation.invalid.append((offset, f"invalid user id: {raw!r}"))
            continue
        extra = {
            extra_columns[col]: row[col].strip()
            for col in extra_columns
            if col < len(row) and row[col].strip()
        }
        if raw in seen:
            validation.duplicates.append(raw)
            _merge_goalid(users_by_id[raw], extra.get("goalid"))
            continue
        seen.add(raw)
        user = InputUser(user_id=raw, source_row=offset, extra=extra)
        users_by_id[raw] = user
        validation.users.append(user)

    if validation.duplicates:
        logger.warning(
            "duplicate user ids ignored",
            count=len(validation.duplicates),
            examples=validation.duplicates[:10],
        )
    if validation.invalid:
        logger.warning("invalid rows skipped", count=len(validation.invalid))
    logger.info(
        "input validated",
        file=path.name,
        total_rows=validation.total_rows,
        unique_users=len(validation.users),
        blank_rows=validation.blank_rows,
        duplicates=len(validation.duplicates),
        invalid_rows=len(validation.invalid),
    )
    return validation


def _merge_goalid(user: InputUser, goalid: str | None):
    """Collect unique goal IDs when the same user appears on several rows."""
    if not goalid:
        return
    existing = user.extra.get("goalid", "")
    parts = [g for g in existing.split(",") if g]
    if goalid not in parts:
        user.extra["goalid"] = ",".join([*parts, goalid])


def write_validation_report(validation: InputValidation, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["section", "value"])
        writer.writerow(["total_rows", validation.total_rows])
        writer.writerow(["unique_users", len(validation.users)])
        writer.writerow(["blank_rows", validation.blank_rows])
        for dup in validation.duplicates:
            writer.writerow(["duplicate", dup])
        for row, reason in validation.invalid:
            writer.writerow([f"invalid_row_{row}", reason])
