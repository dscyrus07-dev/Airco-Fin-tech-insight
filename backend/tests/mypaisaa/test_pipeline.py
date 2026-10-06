"""End-to-end pipeline tests with mocked API + download servers.

Covers: single/multiple/no statements, dedup, resume after interruption,
retry-failed, force re-download, dry-run, large user lists, concurrency.
"""

from __future__ import annotations

import httpx
import pytest

from scripts.mypaisaa_fetch.pipeline import run_pipeline
from tests.mypaisaa.conftest import (
    api_transport,
    download_transport,
    encrypted_pdf_bytes,
    make_config,
    minimal_pdf_bytes,
    multi_page_pdf_bytes,
    write_users_csv,
)


@pytest.mark.asyncio
async def test_single_statement_user(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1"])
    config = make_config(tmp_path, input_file=input_file)
    api = api_transport({"U1": [{"url": "https://statements.test/U1/1.pdf", "password": "pw"}]})
    pipeline, stats = await run_pipeline(
        config, transport=api, download_transport=download_transport({"/U1/1.pdf": minimal_pdf_bytes()})
    )
    assert stats.users_successful == 1
    assert stats.statements_downloaded == 1
    assert (config.output_dir / "U1" / "statement_001.pdf").exists()


@pytest.mark.asyncio
async def test_multi_statement_user(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1"])
    config = make_config(tmp_path, input_file=input_file)
    api = api_transport(
        {
            "U1": [
                {"url": "https://statements.test/U1/1.pdf", "createdate": "2022-06-13 10:42:03"},
                {"url": "https://statements.test/U1/2.pdf", "createdate": "2022-06-11 10:00:00"},
                {"url": "https://statements.test/U1/3.pdf", "createdate": "2022-06-12 09:00:00", "password": "p"},
            ]
        }
    )
    files = {
        "/U1/1.pdf": multi_page_pdf_bytes(3),
        "/U1/2.pdf": multi_page_pdf_bytes(1),
        "/U1/3.pdf": encrypted_pdf_bytes("p"),
    }
    pipeline, stats = await run_pipeline(config, transport=api, download_transport=download_transport(files))
    assert stats.statements_downloaded == 3
    # Sorted by pulled_at: 2.pdf (11th) -> statement_001, 3.pdf (12th) -> 002, 1.pdf (13th) -> 003
    assert (config.output_dir / "U1" / "statement_001.pdf").exists()
    assert (config.output_dir / "U1" / "statement_003.pdf").exists()


@pytest.mark.asyncio
async def test_no_statements_user(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1", "U2"])
    config = make_config(tmp_path, input_file=input_file)
    pipeline, stats = await run_pipeline(
        config, transport=api_transport({"U1": [], "U2": []}), download_transport=download_transport({})
    )
    assert stats.users_no_statements == 2
    assert stats.statements_discovered == 0


@pytest.mark.asyncio
async def test_duplicate_statement_by_hash(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1"])
    config = make_config(tmp_path, input_file=input_file)
    api = api_transport(
        {"U1": [{"url": "https://statements.test/U1/1.pdf"}, {"url": "https://statements.test/U1/2.pdf"}]}
    )
    files = {"/U1/1.pdf": minimal_pdf_bytes(), "/U1/2.pdf": minimal_pdf_bytes()}  # same content
    pipeline, stats = await run_pipeline(config, transport=api, download_transport=download_transport(files))
    assert stats.statements_downloaded == 1
    assert stats.duplicates_skipped == 1


@pytest.mark.asyncio
async def test_download_failure_recorded(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1"])
    config = make_config(tmp_path, input_file=input_file)
    api = api_transport({"U1": [{"url": "https://statements.test/U1/missing.pdf"}]})
    pipeline, stats = await run_pipeline(config, transport=api, download_transport=download_transport({}))
    assert stats.download_failures == 1
    assert stats.users_with_errors == 1
    assert list(config.output_dir.glob("failed_statements_*.csv"))
    # users table must reflect the failed outcome, not just the API call
    manifest = __import__(
        "scripts.mypaisaa_fetch.manifest", fromlist=["Manifest"]
    ).Manifest(config.output_dir / "manifest.db")
    user_row = manifest.get_user("U1")
    manifest.close()
    assert user_row["api_status"] == "error"
    assert "download_failed" in user_row["error_message"]


@pytest.mark.asyncio
async def test_resume_after_interruption(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1", "U2", "U3"])
    api = api_transport(
        {
            "U1": [{"url": "https://statements.test/U1/1.pdf"}],
            "U2": [{"url": "https://statements.test/U2/1.pdf"}],
            "U3": [{"url": "https://statements.test/U3/1.pdf"}],
        }
    )
    config = make_config(tmp_path, input_file=input_file)

    # "Interrupted" run: only U1's file exists on the server; U2/U3 fail.
    partial = download_transport({"/U1/1.pdf": minimal_pdf_bytes()})
    pipeline, stats = await run_pipeline(config, transport=api, download_transport=partial)
    assert stats.users_successful == 1
    assert stats.users_with_errors == 2

    # Restart: server now has all files; only failed users reprocessed.
    full = download_transport(
        {
            "/U1/1.pdf": minimal_pdf_bytes(),
            "/U2/1.pdf": minimal_pdf_bytes(),
            "/U3/1.pdf": minimal_pdf_bytes(),
        }
    )
    pipeline, stats = await run_pipeline(config, transport=api, download_transport=full)
    assert stats.users_skipped == 1  # U1 already complete
    assert stats.users_processed == 2
    assert stats.users_successful == 2
    assert (config.output_dir / "U2" / "statement_001.pdf").exists()
    assert (config.output_dir / "U3" / "statement_001.pdf").exists()


@pytest.mark.asyncio
async def test_completed_statements_not_redownloaded(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1"])
    config = make_config(tmp_path, input_file=input_file)
    api = api_transport({"U1": [{"url": "https://statements.test/U1/1.pdf"}]})
    files = download_transport({"/U1/1.pdf": minimal_pdf_bytes()})

    await run_pipeline(config, transport=api, download_transport=files)
    pipeline, stats = await run_pipeline(config, transport=api, download_transport=files)
    assert stats.users_processed == 0
    assert stats.users_skipped == 1


@pytest.mark.asyncio
async def test_force_redownloads(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1"])
    config = make_config(tmp_path, input_file=input_file)
    api = api_transport({"U1": [{"url": "https://statements.test/U1/1.pdf"}]})
    files = download_transport({"/U1/1.pdf": minimal_pdf_bytes()})

    await run_pipeline(config, transport=api, download_transport=files)
    pipeline, stats = await run_pipeline(config, transport=api, download_transport=files, force=True)
    assert stats.users_processed == 1
    assert stats.statements_downloaded == 1


@pytest.mark.asyncio
async def test_dry_run_validates_only(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1", "U1", "U2"])
    config = make_config(tmp_path, input_file=input_file)

    def exploding_handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("dry run must not call the API")

    pipeline, stats = await run_pipeline(
        config,
        transport=httpx.MockTransport(exploding_handler),
        download_transport=download_transport({}),
        dry_run=True,
    )
    assert stats.users_received == 2  # duplicate removed
    assert stats.users_processed == 0
    assert stats.statements_downloaded == 0
    assert not (config.output_dir / "U1").exists()
    assert (config.output_dir / "users_report.csv").exists()


@pytest.mark.asyncio
async def test_password_invalid_preserved_on_resume(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1"])
    config = make_config(tmp_path, input_file=input_file)
    api = api_transport({"U1": [{"url": "https://statements.test/U1/1.pdf", "password": "wrong"}]})
    files = download_transport({"/U1/1.pdf": encrypted_pdf_bytes("real")})

    pipeline, stats = await run_pipeline(config, transport=api, download_transport=files)
    assert stats.password_failures == 1

    pipeline, stats = await run_pipeline(config, transport=api, download_transport=files)
    assert stats.password_failures == 1  # still invalid, not re-downloaded as duplicate


@pytest.mark.asyncio
async def test_large_user_list_with_concurrency(tmp_path):
    users = [f"U{i:03d}" for i in range(60)]
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, users)
    statements = {uid: [{"url": f"https://statements.test/{uid}/1.pdf"}] for uid in users}
    files = {f"/{uid}/1.pdf": minimal_pdf_bytes() for uid in users}
    config = make_config(tmp_path, input_file=input_file, max_concurrent_users=5)
    pipeline, stats = await run_pipeline(
        config, transport=api_transport(statements), download_transport=download_transport(files)
    )
    assert stats.users_successful == 60
    assert stats.statements_downloaded == 60


@pytest.mark.asyncio
async def test_duplicate_user_in_input_processed_once(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1", "U1", "U1"])
    config = make_config(tmp_path, input_file=input_file)
    api = api_transport({"U1": [{"url": "https://statements.test/U1/1.pdf"}]})
    pipeline, stats = await run_pipeline(
        config, transport=api, download_transport=download_transport({"/U1/1.pdf": minimal_pdf_bytes()})
    )
    assert stats.users_received == 1  # deduplicated by input loader


@pytest.mark.asyncio
async def test_api_5xx_user_retried_and_marked_error(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1"])
    config = make_config(tmp_path, input_file=input_file)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    api = httpx.MockTransport(handler)
    pipeline, stats = await run_pipeline(config, transport=api, download_transport=download_transport({}))
    assert stats.users_with_errors == 1


@pytest.mark.asyncio
async def test_limit_processes_only_n_users(tmp_path):
    users = [f"U{i:02d}" for i in range(20)]
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, users)
    statements = {uid: [{"url": f"https://statements.test/{uid}/1.pdf"}] for uid in users}
    files = {f"/{uid}/1.pdf": minimal_pdf_bytes() for uid in users}
    config = make_config(tmp_path, input_file=input_file)
    pipeline, stats = await run_pipeline(
        config,
        transport=api_transport(statements),
        download_transport=download_transport(files),
        limit=5,
    )
    assert stats.users_received == 5
    assert stats.users_successful == 5


@pytest.mark.asyncio
async def test_reports_generated(tmp_path):
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["U1", "U2"])
    config = make_config(tmp_path, input_file=input_file)
    api = api_transport(
        {
            "U1": [{"url": "https://statements.test/U1/1.pdf", "password": "pw"}],
            "U2": [],
        }
    )
    files = download_transport({"/U1/1.pdf": encrypted_pdf_bytes("pw")})
    pipeline, stats = await run_pipeline(config, transport=api, download_transport=files)

    out = config.output_dir
    assert (out / "summary.json").exists()
    assert (out / "users_report.csv").exists()
    assert (out / "statements_report.csv").exists()
    assert (out / "failed_users.csv").exists()
    assert (out / "failed_statements.csv").exists()

    # statements_report.csv must not contain the password column
    import csv as _csv

    with (out / "statements_report.csv").open(encoding="utf-8", newline="") as fh:
        header = next(_csv.reader(fh))
    assert "password" not in header
    assert "password_available" in header

    summary = (out / "summary.json").read_text(encoding="utf-8")
    assert '"discovered": 1' in summary


@pytest.mark.asyncio
async def test_failure_isolation_one_bad_user(tmp_path):
    """A user raising an unexpected error must not stop the batch."""
    input_file = tmp_path / "users.csv"
    write_users_csv(input_file, ["BAD", "U1", "U2"])
    config = make_config(tmp_path, input_file=input_file)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/BAD"):
            raise RuntimeError("simulated crash")
        return httpx.Response(200, json={"status": "success", "data": []})

    pipeline, stats = await run_pipeline(
        config, transport=httpx.MockTransport(handler), download_transport=download_transport({})
    )
    assert stats.users_processed == 3
    assert stats.users_no_statements == 2
    assert stats.users_with_errors == 1
