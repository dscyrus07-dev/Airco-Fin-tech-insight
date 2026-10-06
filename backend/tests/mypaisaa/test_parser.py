"""Parser tests: multi-statement shapes, nesting, passwords, dedup."""

from __future__ import annotations

from scripts.mypaisaa_fetch.parser import extract_statements


def test_flat_list_single_statement():
    payload = {
        "status": "success",
        "data": [
            {
                "statement_url": "https://statements.test/a/statement_001.pdf",
                "password": "1234",
                "created_at": "2026-05-10T13:21:47Z",
            }
        ],
    }
    records = extract_statements("U1", payload)
    assert len(records) == 1
    assert records[0].source_url == "https://statements.test/a/statement_001.pdf"
    assert records[0].password == "1234"
    assert records[0].pulled_at == "2026-05-10T13:21:47Z"


def test_multiple_statements_all_returned():
    payload = {
        "data": [
            {"url": "https://statements.test/a/1.pdf", "password": "p1"},
            {"url": "https://statements.test/a/2.pdf", "password": "p2"},
            {"url": "https://statements.test/a/3.pdf"},
        ]
    }
    records = extract_statements("U1", payload)
    assert len(records) == 3
    assert [r.source_url for r in records] == [
        "https://statements.test/a/1.pdf",
        "https://statements.test/a/2.pdf",
        "https://statements.test/a/3.pdf",
    ]
    assert records[0].password == "p1"
    assert records[2].password is None


def test_no_statements_empty_data():
    payload = {"status": "success", "message": "...", "data": []}
    assert extract_statements("U1", payload) == []


def test_nested_statements_array():
    payload = {
        "data": [
            {
                "customer_id": "U1",
                "password": "shared-pass",
                "statements": [
                    {"file_url": "https://statements.test/a/1.pdf"},
                    {"file_url": "https://statements.test/a/2.pdf"},
                ],
            }
        ]
    }
    records = extract_statements("U1", payload)
    assert len(records) == 2
    assert all(r.password == "shared-pass" for r in records)


def test_document_name_without_url():
    payload = {"data": [{"document": "AccountStatement_10-05-202613_21_47_1778"}]}
    records = extract_statements("U1", payload)
    assert len(records) == 1
    assert records[0].source_url is None
    assert records[0].filename_hint == "AccountStatement_10-05-202613_21_47_1778"


def test_duplicate_urls_within_user_deduped():
    payload = {
        "data": [
            {"url": "https://statements.test/a/1.pdf"},
            {"url": "https://statements.test/a/1.pdf"},
            {"url": "https://statements.test/a/2.pdf"},
        ]
    }
    records = extract_statements("U1", payload)
    assert [r.source_url for r in records] == [
        "https://statements.test/a/1.pdf",
        "https://statements.test/a/2.pdf",
    ]


def test_numeric_password_converted_to_string():
    payload = {"data": [{"url": "https://statements.test/a/1.pdf", "password": 252774154}]}
    records = extract_statements("U1", payload)
    assert records[0].password == "252774154"


def test_data_as_single_dict():
    payload = {"data": {"url": "https://statements.test/a/1.pdf", "pwd": "pw"}}
    records = extract_statements("U1", payload)
    assert len(records) == 1
    assert records[0].password == "pw"


def test_statement_id_and_dates_extracted():
    payload = {
        "data": [
            {
                "statement_id": "abc123",
                "url": "https://statements.test/a/1.pdf",
                "pulled_at": "02-10-2026 03:06:42",
                "statement_date": "01-04-2023",
            }
        ]
    }
    records = extract_statements("U1", payload)
    assert records[0].statement_id == "abc123"
    assert records[0].pulled_at == "02-10-2026 03:06:42"
    assert records[0].statement_date == "01-04-2023"


def test_unrelated_fields_ignored():
    payload = {
        "data": [
            {
                "url": "https://statements.test/a/1.pdf",
                "customer_name": "John Doe",
                "email": "john@example.com",
                "phone": "9999999999",
                "balance": 12345.67,
            }
        ]
    }
    records = extract_statements("U1", payload)
    assert len(records) == 1
    assert records[0].password is None


def test_deeply_nested_recovers_all():
    payload = {
        "data": [
            {
                "accounts": [
                    {
                        "bank": "HDFC",
                        "files": [
                            {"link": "https://statements.test/a/1.pdf"},
                            {"link": "https://statements.test/a/2.pdf"},
                        ],
                    },
                    {"bank": "ICICI", "files": [{"link": "https://statements.test/a/3.pdf"}]},
                ]
            }
        ]
    }
    records = extract_statements("U1", payload)
    assert len(records) == 3
