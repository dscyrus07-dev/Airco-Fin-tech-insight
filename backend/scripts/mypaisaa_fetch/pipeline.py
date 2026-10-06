"""Pipeline orchestration: users -> API -> parse -> download -> manifest.

Controlled concurrency: at most ``max_concurrent_users`` users are processed
at once (API call + its downloads run serially within a user), with optional
global pacing via ``REQUESTS_PER_SECOND``. Restartable: state lives in the
SQLite manifest, so an interrupted run continues where it stopped. One user's
failure never stops the batch.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .api_client import ApiPermanentError, ApiRetryError, MyPaisaaClient
from .config import PipelineConfig
from .downloader import Downloader
from .input_loader import load_users, write_validation_report
from .logging_utils import get_logger
from .manifest import Manifest
from .models import (
    RETRYABLE,
    TERMINAL_OK,
    ST_PENDING,
    US_ERROR,
    US_NO_STATEMENTS,
    US_SUCCESS,
    InputUser,
    RunStats,
    StatementOutcome,
    UserOutcome,
)
from .parser import extract_statements
from .ratelimit import RateLimiter
from .report import (
    render_summary,
    write_failure_reports,
    write_summary_file,
    write_summary_json,
    write_users_report,
)

logger = get_logger(__name__)


class Pipeline:
    def __init__(
        self,
        config: PipelineConfig,
        transport: httpx.BaseTransport | None = None,
        download_transport: httpx.BaseTransport | None = None,
    ):
        self.config = config
        self.transport = transport
        self.download_transport = download_transport
        self.manifest = Manifest(config.output_dir / "manifest.db")
        self.stats = RunStats()
        self.limiter = RateLimiter(config.requests_per_second)

    async def run(
        self,
        retry_failed: bool = False,
        force: bool = False,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> RunStats:
        config = self.config
        validation = load_users(config.input_file)
        write_validation_report(validation, config.output_dir / "input_validation_report.csv")
        if not validation.ok:
            logger.error("no valid users in input; aborting")
            return self.stats

        users = validation.users
        if limit is not None:
            users = users[:limit]
            logger.info("limit applied", requested=len(validation.users), processing=len(users))

        self.stats.users_received = len(users)
        run_id = self.manifest.start_run(str(config.input_file), len(users))

        if dry_run:
            # Validation-only mode: no API calls, no downloads.
            logger.info(
                "dry run complete",
                users=len(users),
                duplicates=len(validation.duplicates),
                invalid_rows=len(validation.invalid),
                blank_rows=validation.blank_rows,
            )
            write_users_report(self.manifest, config.output_dir / "users_report.csv")
            self.manifest.close()
            return self.stats

        pending_users = self._select_users(users, retry_failed, force)
        self.stats.users_skipped = len(users) - len(pending_users)
        client = MyPaisaaClient(config, transport=self.transport, limiter=self.limiter)
        downloader = Downloader(
            config,
            httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=config.connect_timeout_seconds,
                    read=config.request_timeout_seconds,
                    write=config.request_timeout_seconds,
                    pool=config.request_timeout_seconds,
                ),
                follow_redirects=True,
                transport=self.download_transport,
            ),
            limiter=self.limiter,
        )
        semaphore = asyncio.Semaphore(config.max_concurrent_users)

        async def worker(user: InputUser):
            async with semaphore:
                try:
                    return await self._process_user(
                        client, downloader, user, force=force
                    )
                except Exception as exc:  # noqa: BLE001 - isolate one user's failure
                    logger.error(
                        "unexpected user failure", user_id=user.user_id, error=type(exc).__name__
                    )
                    return self._record_user_error(
                        user, f"unexpected error: {type(exc).__name__}", 0
                    )

        try:
            outcomes = await asyncio.gather(*(worker(u) for u in pending_users))
        finally:
            await client.aclose()
            self.manifest.finish_run(run_id)

        self._accumulate(outcomes)
        self._write_reports(config.output_dir)
        self.manifest.close()
        return self.stats

    def has_failures(self) -> bool:
        return getattr(self, "_failures_present", False)

    # -- user selection -----------------------------------------------------
    def _select_users(
        self, users: list[InputUser], retry_failed: bool, force: bool
    ) -> list[InputUser]:
        if force:
            return list(users)

        errored = self.manifest.user_ids_with_status({US_ERROR})
        incomplete = {
            row["user_id"]
            for row in self.manifest.statements_with_status({ST_PENDING, *RETRYABLE})
        }
        known = self.manifest.all_user_ids()

        if retry_failed:
            selected = errored | incomplete
        else:
            # Default resume: process users never attempted, errored, or with
            # unfinished statements.
            selected = errored | incomplete | ({u.user_id for u in users} - known)
        return [u for u in users if u.user_id in selected]

    # -- per-user processing ------------------------------------------------
    async def _process_user(
        self, client: MyPaisaaClient, downloader: Downloader, user: InputUser, force: bool
    ) -> UserOutcome:
        user_id = user.user_id
        logger.info("processing user", user_id=user_id)
        try:
            response = await client.fetch_user_statements(user_id)
        except ApiPermanentError as exc:
            return self._record_user_error(user, exc.reason, 0)
        except ApiRetryError as exc:
            return self._record_user_error(user, exc.reason, exc.attempts - 1)

        records = extract_statements(user_id, response.payload)
        self.manifest.upsert_user(
            user_id,
            statements_found=len(records),
            api_status=US_SUCCESS if records else US_NO_STATEMENTS,
            error_message=None,
            goalids=user.extra.get("goalid"),
            ps_date=user.extra.get("ps_date"),
            ps_month=user.extra.get("ps_month"),
        )

        if not records:
            logger.info("no statements found", user_id=user_id)
            return UserOutcome(user_id=user_id, status=US_NO_STATEMENTS)

        logger.info("statements returned", user_id=user_id, count=len(records))

        # Deterministic ordering so restarts produce identical filenames.
        records.sort(
            key=lambda r: (
                r.pulled_at or "",
                r.statement_id or "",
                r.source_url or "",
            )
        )
        outcomes: list[StatementOutcome] = []
        known_hashes = {
            row["sha256"]
            for row in self.manifest.statements_for_user(user_id)
            if row["sha256"]
        }
        user_dir = Path(self.config.output_dir) / _safe_dir(user_id)

        for index, record in enumerate(records, start=1):
            logger.info(
                "downloading statement", user_id=user_id, position=f"{index}/{len(records)}"
            )
            outcome = await self._process_statement(
                downloader, record, user_dir, index, known_hashes, force
            )
            outcomes.append(outcome)
            if outcome.sha256:
                known_hashes.add(outcome.sha256)

        status = US_SUCCESS if all(o.status in TERMINAL_OK for o in outcomes) else US_ERROR
        error_message = None
        if status == US_ERROR:
            failed = [o for o in outcomes if o.status not in TERMINAL_OK]
            reasons = sorted({o.status for o in failed})
            error_message = f"{len(failed)} statement(s) not completed: {', '.join(reasons)}"
        self.manifest.upsert_user(
            user_id,
            api_status=status,
            error_message=error_message,
        )
        logger.info("user completed", user_id=user_id, status=status)
        return UserOutcome(
            user_id=user_id,
            status=status,
            statements_found=len(records),
            outcomes=outcomes,
        )

    def _record_user_error(self, user: InputUser, reason: str, retry_count: int) -> UserOutcome:
        user_id = user.user_id
        logger.error("user failed", user_id=user_id, error=reason)
        self.manifest.upsert_user(
            user_id,
            api_status=US_ERROR,
            error_message=reason,
            retry_count=retry_count,
            goalids=user.extra.get("goalid"),
            ps_date=user.extra.get("ps_date"),
            ps_month=user.extra.get("ps_month"),
        )
        return UserOutcome(user_id=user_id, status=US_ERROR, error=reason, retry_count=retry_count)

    async def _process_statement(
        self,
        downloader: Downloader,
        record,
        user_dir: Path,
        index: int,
        known_hashes: set[str],
        force: bool,
    ) -> StatementOutcome:
        existing = self.manifest.get_statement(record.user_id, record.dedup_key)
        if existing and not force and existing["download_status"] in TERMINAL_OK:
            logger.info(
                "statement already complete; skipping",
                user_id=record.user_id,
                filename=existing["filename"],
            )
            return StatementOutcome(
                statement_id=record.statement_id,
                source_url=record.source_url,
                filename=existing["filename"],
                status=existing["download_status"],
                password_available=bool(record.password),
                statement_index=existing["statement_index"],
            )

        row_id = self.manifest.upsert_statement(
            record.user_id,
            record.dedup_key,
            statement_id=record.statement_id,
            source_url=record.source_url,
            filename=record.filename_hint,
            original_filename=record.filename_hint,
            statement_index=index,
            statement_date=record.statement_date,
            pulled_at=record.pulled_at,
            bank_name=record.bank_name,
            account_type=record.account_type,
            password_available=1 if record.password else 0,
            password=record.password,
            api_fetched_at=datetime.now(timezone.utc).isoformat(),
        )

        if not record.source_url:
            reason = "no downloadable URL in API response"
            self.manifest.update_statement(
                row_id,
                download_status="no_url",
                error_message=reason,
                retry_count=(existing["retry_count"] + 1) if existing else 1,
            )
            logger.warning("statement has no URL", user_id=record.user_id)
            return StatementOutcome(
                statement_id=record.statement_id,
                source_url=None,
                filename=record.filename_hint,
                status="no_url",
                error=reason,
                password_available=bool(record.password),
                statement_index=index,
            )

        existing_path = existing["local_path"] if existing else None
        if existing_path and Path(existing_path).exists():
            # File already on disk (e.g. saved despite a password failure):
            # re-verify instead of re-downloading the same bytes.
            verdict = downloader.reverify(existing_path, record)
            retry_count = existing["retry_count"] + 1
        else:
            verdict = await downloader.download(record, user_dir, index, known_hashes)
            retry_count = (existing["retry_count"] + 1) if existing else 1

        updates = dict(
            download_status=verdict.status,
            filename=verdict.filename,
            local_path=verdict.local_path,
            file_size=verdict.file_size,
            sha256=verdict.sha256,
            file_type=verdict.file_type,
            error_message=verdict.error,
            retry_count=retry_count,
        )
        if verdict.status in TERMINAL_OK or verdict.status in {
            "password_required", "password_invalid"
        }:
            updates["downloaded_at"] = datetime.now(timezone.utc).isoformat()
        if verdict.status == "downloaded":
            updates["password_verified"] = 1 if verdict.password_verified else 0
        self.manifest.update_statement(row_id, **updates)

        return StatementOutcome(
            statement_id=record.statement_id,
            source_url=record.source_url,
            filename=verdict.filename,
            status=verdict.status,
            error=verdict.error,
            retry_count=retry_count,
            password_available=bool(record.password),
            sha256=verdict.sha256,
            file_type=verdict.file_type,
            statement_index=index,
        )

    # -- aggregation + reports ----------------------------------------------
    def _accumulate(self, outcomes: list[UserOutcome]):
        for outcome in outcomes:
            self.stats.users_processed += 1
            if outcome.status == US_SUCCESS:
                self.stats.users_successful += 1
            elif outcome.status == US_NO_STATEMENTS:
                self.stats.users_no_statements += 1
            else:
                self.stats.users_with_errors += 1
            self.stats.statements_discovered += outcome.statements_found
            for st in outcome.outcomes:
                if st.status == "downloaded":
                    self.stats.statements_downloaded += 1
                    if st.password_available:
                        self.stats.password_protected += 1
                elif st.status == "duplicate":
                    self.stats.duplicates_skipped += 1
                elif st.status in {"password_required", "password_invalid"}:
                    self.stats.password_failures += 1
                elif st.status == "no_url":
                    self.stats.no_url_statements += 1
                elif st.status == "download_invalid":
                    self.stats.invalid_downloads += 1
                else:
                    self.stats.download_failures += 1

    def _write_reports(self, output_dir: Path):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        summary = render_summary(self.stats)
        write_summary_file(output_dir / f"summary_{stamp}.txt", summary)
        write_summary_json(output_dir / "summary.json", self.stats, stamp)
        write_users_report(self.manifest, output_dir / "users_report.csv")
        self.manifest.export_csv(output_dir / "statements_report.csv", include_password=False)
        failed_statements = self.manifest.statements_with_status(RETRYABLE - {"pending"})
        failed_users = [
            row
            for row in (
                self.manifest.get_user(uid)
                for uid in sorted(self.manifest.user_ids_with_status({US_ERROR}))
            )
            if row
        ]
        self._failures_present = bool(failed_statements or failed_users)
        write_failure_reports(
            output_dir,
            failed_statements,
            failed_users,
            stamp,
        )
        if self._failures_present:
            logger.warning(
                "failures recorded",
                failed_statements=len(failed_statements),
                failed_users=len(failed_users),
            )

    def summary_text(self) -> str:
        return render_summary(self.stats)


def _safe_dir(user_id: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in user_id)[:120]


async def run_pipeline(
    config: PipelineConfig,
    transport: httpx.BaseTransport | None = None,
    download_transport: httpx.BaseTransport | None = None,
    retry_failed: bool = False,
    force: bool = False,
    dry_run: bool = False,
    limit: int | None = None,
) -> tuple[Pipeline, RunStats]:
    pipeline = Pipeline(config, transport=transport, download_transport=download_transport)
    stats = await pipeline.run(
        retry_failed=retry_failed, force=force, dry_run=dry_run, limit=limit
    )
    return pipeline, stats
