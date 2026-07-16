"""
Event consumer for processing domain events.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from .message_queue import message_queue
from .pipeline_orchestrator import process_statement
from .redis_job_store import redis_job_store
from .file_history_service import file_history_service
from .frontend_result_builder import build_frontend_processing_result
from ..utils.file_handler import cleanup_file, upload_to_storage, download_from_storage
from ..core.config import settings as app_settings

from ..models.job import JobStatus, JobUpdate
from ..utils.correlation import set_correlation_id
from ..utils.logging import get_logger
from ..database.session import get_db
from .audit.audit_service import AuditService
from ..database.audit_models import ProcessingJob

logger = get_logger(__name__)


def _safe_object_name(filename: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_", ".") else "_" for ch in filename)
    return cleaned.strip("._") or "statement.pdf"


def _compute_file_hash(file_path: str) -> str:
    """Compute SHA-256 hash of a file by streaming it in chunks to save memory."""
    import hashlib
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


def _decrypt_pdf_for_processing(file_path: str, password: str | None) -> str:
    """Decrypt a PDF into a sibling temp file when a password is provided."""
    if not password:
        return file_path

    try:
        import pikepdf
    except ImportError as exc:
        raise ValueError("PDF password support is unavailable because pikepdf is not installed") from exc

    try:
        with pikepdf.open(file_path, password=password) as pdf:
            decrypted_path = f"{os.path.splitext(file_path)[0]}_decrypted.pdf"
            pdf.save(decrypted_path)
            return decrypted_path
    except pikepdf.PasswordError as exc:
        raise ValueError("Incorrect PDF password") from exc


class EventConsumer:
    """Consumes RabbitMQ events and bridges them into the existing bank pipeline."""

    def __init__(self):
        self._register_handlers()

    def _register_handlers(self):
        message_queue.register_consumer("file_upload_queue", self._handle_file_uploaded)

    async def _mark_job(self, job_id: str, status: JobStatus, result_data: Dict[str, Any] | None = None, error_message: str | None = None):
        update = JobUpdate(status=status, result_data=result_data, error_message=error_message)
        await redis_job_store.update_job(job_id, update)

    async def _handle_file_uploaded(self, payload: Dict[str, Any]):
        """Process a file upload event using the existing deterministic bank pipeline."""
        job_id = payload.get("job_id")
        correlation_id = payload.get("correlation_id")
        if correlation_id:
            set_correlation_id(correlation_id)

        upload_object_key = payload.get("upload_object_key")
        user_info = payload.get("user_info", {})
        mode = payload.get("mode", "free")
        api_key = payload.get("api_key")
        user_id = payload.get("user_id") or "anonymous"
        original_filename = payload.get("original_filename") or "statement.pdf"
        output_dir = payload.get("output_dir")
        pdf_password = payload.get("pdf_password")

        if not job_id:
            logger.warning("file_upload event missing job_id; skipping job update")
            return True

        # Prefer local temp path from upload (same host) — skip S3 round-trip when possible
        local_path = payload.get("file_path")
        file_path = None
        if local_path and os.path.isfile(local_path):
            file_path = local_path
            logger.info("Using local upload path (skip storage download)", job_id=job_id)
        elif upload_object_key:
            file_path = download_from_storage(
                bucket=app_settings.S3_BUCKET_UPLOADS,
                object_key=upload_object_key,
            )
        else:
            raise ValueError("upload_object_key or local file_path is required in queue payload")

        if not file_path or not os.path.isfile(file_path):
            raise ValueError(
                f"Failed to resolve source PDF (local={local_path}, key={upload_object_key})"
            )

        processing_file_path = file_path

        # Bootstrap audit service for Supabase logging
        audit_service = None
        audit_db = None
        try:
            from ..database.session import SessionLocal
            audit_db = SessionLocal()
            audit_service = AuditService(audit_db)
            file_hash = _compute_file_hash(file_path)
            file_size = os.path.getsize(file_path)
            audit_service.create_processing_job(
                tenant_id="default",
                user_id=user_id,
                job_id=job_id,
                original_filename=original_filename,
                file_hash=file_hash,
                file_size_bytes=file_size,
                processing_mode=mode.upper(),
            )
        except Exception as ae:
            logger.warning("Audit job creation failed (non-fatal)", job_id=job_id, error=str(ae))
            # Keep audit_service alive even if job creation failed — finalize_job_audit uses its own fresh session
            if audit_db is None:
                try:
                    from ..database.session import SessionLocal
                    audit_db = SessionLocal()
                    audit_service = AuditService(audit_db)
                except Exception:
                    audit_service = None
                    audit_db = None

        try:
            processing_file_path = _decrypt_pdf_for_processing(file_path, pdf_password)

            if not output_dir:
                output_dir = os.path.dirname(processing_file_path)

            await self._mark_job(job_id, JobStatus.RUNNING)
            try:
                file_history_service.mark_running(job_id)
            except Exception as e:
                logger.warning("Failed to update file history service for running status", job_id=job_id, error=str(e))

            # Early hygiene so UI advances before full parse (result is cached for parsers)
            hygiene_payload = None
            try:
                from .banks._shared.hygiene_check import HygieneCheck
                from .job_progress import hygiene_result_to_progress, publish_job_progress

                await publish_job_progress(
                    job_id,
                    stage="hygiene",
                    message="Running PDF hygiene check…",
                )
                checker = HygieneCheck(
                    pdf_directory=Path(processing_file_path).parent,
                    audit_service=audit_service,
                    job_id=job_id,
                )
                hygiene_result = checker.validate_single_pdf(
                    Path(processing_file_path),
                    user_id=str(user_id),
                    goal_id="GENERAL",
                    original_filename=original_filename,
                    bank_hint=(user_info or {}).get("bank_name") or payload.get("bank_name"),
                )
                checker.log_hygiene_check_result(hygiene_result)

                hygiene_payload = hygiene_result_to_progress(hygiene_result)
                await publish_job_progress(
                    job_id,
                    stage="hygiene_complete",
                    message=(
                        "Hygiene check passed"
                        if hygiene_result.is_healthy
                        else "Hygiene check completed with warnings"
                    ),
                    hygiene=hygiene_payload,
                )
            except Exception as he:
                logger.warning("Early hygiene failed (non-fatal)", job_id=job_id, error=str(he))
                try:
                    from .job_progress import publish_job_progress
                    await publish_job_progress(
                        job_id,
                        stage="hygiene_complete",
                        message="Hygiene skipped — continuing with parsing",
                        hygiene={
                            "is_healthy": True,
                            "file_name": original_filename,
                            "page_count": 0,
                            "bank_name": (user_info or {}).get("bank_name") or "unknown",
                            "format_id": "",
                            "transaction_count": 0,
                            "start_date": "N/A",
                            "end_date": "N/A",
                            "issues": [],
                            "warnings": [f"Hygiene pre-check unavailable: {he}"],
                        },
                    )
                except Exception:
                    pass

            try:
                from .job_progress import publish_job_progress
                await publish_job_progress(
                    job_id,
                    stage="parsing",
                    message="Extracting transactions and generating report…",
                    hygiene=hygiene_payload,
                )
            except Exception:
                pass

            result = process_statement(
                file_path=processing_file_path,
                user_info=user_info,
                mode=mode,
                api_key=api_key,
                output_dir=output_dir,
                audit_service=audit_service,
                job_id=job_id,
            )


            if result.get("status") != "success":
                error_payload = result.get("error") or {}
                if isinstance(error_payload, dict):
                    error_message = error_payload.get("message") or "Processing failed"
                else:
                    error_message = str(error_payload) or "Processing failed"
                raise RuntimeError(error_message)

            excel_path = result.get("excel_path")
            if excel_path and os.path.isfile(excel_path):
                safe_original = _safe_object_name(original_filename)
                excel_object_key = f"users/{user_id}/reports/{Path(excel_path).name}"
                upload_to_storage(
                    excel_path,
                    bucket=app_settings.S3_BUCKET_REPORTS,
                    object_key=excel_object_key,
                )

                result["excel_object_key"] = excel_object_key
                result["source_pdf_object_key"] = upload_object_key
            frontend_result = build_frontend_processing_result(
                result,
                mode=mode,
                excel_url=f"/api/jobs/{job_id}/download",
            )
            await self._mark_job(job_id, JobStatus.COMPLETED, result_data=frontend_result)
            # Always use a fresh session for audit status update to avoid poisoned transactions
            try:
                from ..database.session import SessionLocal
                fresh_db = SessionLocal()
                fresh_audit = AuditService(fresh_db)
                txn_count = result.get("stats", {}).get("total_transactions", 0)
                parser_used = result.get("performance", {}).get("parser_used", "unknown")
                processing_ms = int(result.get("performance", {}).get("total_time_ms", 0))
                fresh_audit.update_processing_job(
                    job_id=job_id,
                    status="COMPLETED",
                    bank_name=user_info.get("bank_name", ""),
                    transaction_count=txn_count,
                    parser_used=parser_used,
                    processing_time_ms=processing_ms,
                )
                fresh_db.close()
                logger.info("Audit job updated to COMPLETED", job_id=job_id, bank_name=user_info.get("bank_name", ""))
            except Exception as ue:
                logger.error("Audit job update failed", job_id=job_id, error=str(ue))
            try:
                file_history_service.mark_completed(job_id, frontend_result)
            except Exception as e:
                logger.warning("Failed to update file history service for completed status", job_id=job_id, error=str(e))
            logger.info("Queued statement processed", job_id=job_id, bank_name=user_info.get("bank_name"))
            return True
        except Exception as e:
            logger.error("Queued statement processing failed", job_id=job_id, error=str(e))
            # Always use a fresh session for audit status update
            try:
                from ..database.session import SessionLocal
                fresh_db = SessionLocal()
                fresh_audit = AuditService(fresh_db)
                fresh_audit.update_processing_job(job_id=job_id, status="FAILED", error_message=str(e))
                fresh_db.close()
                logger.info("Audit job updated to FAILED", job_id=job_id)
            except Exception as fe:
                logger.error("Failed to update audit job to FAILED status", job_id=job_id, error=str(fe))
            await self._mark_job(job_id, JobStatus.FAILED, error_message=str(e))
            try:
                file_history_service.mark_failed(job_id, str(e))
            except Exception as fe:
                logger.warning("Failed to update file history service for failed status", job_id=job_id, error=str(fe))
            return False
        finally:
            cleanup_file(file_path)
            if processing_file_path != file_path:
                cleanup_file(processing_file_path)
            # Clean up audit database session
            if audit_db:
                try:
                    audit_db.close()
                except Exception:
                    pass

    async def start_consuming(self):
        await message_queue.start_consuming()


event_consumer = EventConsumer()
