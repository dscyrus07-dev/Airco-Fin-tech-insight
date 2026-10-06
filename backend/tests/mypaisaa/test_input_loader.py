"""Input list validation tests (blank rows, duplicates, trimming, xlsx)."""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from scripts.mypaisaa_fetch.input_loader import load_users
from tests.mypaisaa.conftest import write_users_csv


def test_basic_list(tmp_path: Path):
    path = tmp_path / "users.csv"
    write_users_csv(path, ["U1", "U2", "U3"])
    result = load_users(path)
    assert [u.user_id for u in result.users] == ["U1", "U2", "U3"]
    assert result.total_rows == 4  # header + 3
    assert result.blank_rows == 0
    assert result.duplicates == []


def test_blank_rows_and_whitespace_trimmed(tmp_path: Path):
    path = tmp_path / "users.csv"
    path.write_text("user_id\n  U1  \n\n   \nU2\n", encoding="utf-8")
    result = load_users(path)
    assert [u.user_id for u in result.users] == ["U1", "U2"]
    assert result.blank_rows == 2


def test_duplicate_user_ids_detected_first_wins(tmp_path: Path):
    path = tmp_path / "users.csv"
    write_users_csv(path, ["U1", "U2", "U1", "U3", "U2"])
    result = load_users(path)
    assert [u.user_id for u in result.users] == ["U1", "U2", "U3"]
    assert result.duplicates == ["U1", "U2"]


def test_preserves_user_id_exactly(tmp_path: Path):
    path = tmp_path / "users.csv"
    write_users_csv(path, ["C25331952091", "f7a312ce-62ef-40b0-ba09-6aa5553d18db"])
    result = load_users(path)
    assert result.users[0].user_id == "C25331952091"
    assert result.users[1].user_id == "f7a312ce-62ef-40b0-ba09-6aa5553d18db"


def test_alternative_header_names(tmp_path: Path):
    path = tmp_path / "users.csv"
    path.write_text("Customer ID\nU1\nU2\n", encoding="utf-8")
    result = load_users(path)
    assert [u.user_id for u in result.users] == ["U1", "U2"]


def test_xlsx_input(tmp_path: Path):
    path = tmp_path / "users.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["user_id"])
    ws.append(["U1"])
    ws.append(["   "])  # blank row
    ws.append(["U2"])
    wb.save(path)
    result = load_users(path)
    assert [u.user_id for u in result.users] == ["U1", "U2"]
    assert result.blank_rows == 1


def test_missing_file_raises(tmp_path: Path):
    import pytest

    with pytest.raises(FileNotFoundError):
        load_users(tmp_path / "nope.csv")


def test_empty_file(tmp_path: Path):
    path = tmp_path / "users.csv"
    path.write_text("", encoding="utf-8")
    result = load_users(path)
    assert result.users == []


def test_ps_ids_xlsx_columns_and_extras(tmp_path: Path):
    """goalid/userid/ps_month/ps_date shape: extras captured, IDs normalized."""
    path = tmp_path / "ps.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["goalid", "userid", "ps_month", "ps_date"])
    ws.append([656316.0, 656296.0, "2022-06", "2022-06-13"])
    ws.append([332700.0, 274841.0, "2022-06", "2022-06-14"])
    ws.append([999999.0, 656296.0, "2022-07", "2022-07-10"])  # same user, new goal
    ws.append([111111.0, None, "2022-06", "2022-06-15"])  # missing user id
    wb.save(path)
    result = load_users(path)
    assert [u.user_id for u in result.users] == ["656296", "274841"]
    assert result.duplicates == ["656296"]
    assert result.blank_rows == 1  # row with missing user id
    u = result.users[0]
    assert u.extra["ps_date"] == "2022-06-13"
    assert u.extra["ps_month"] == "2022-06"
    # goalids from both rows merged, unique, comma-joined
    assert u.extra["goalid"] == "656316,999999"
