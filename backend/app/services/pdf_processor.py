"""
PDF processing task handler for async processing.
"""

import os
from typing import Dict, Any

from ..models.job import Job, JobType
from ..services.frontend_result_builder import build_frontend_processing_result
from ..services.job_progress import hygiene_result_to_progress, publish_job_progress
from ..services.pipeline_orchestrator import process_statement
from ..utils.file_handler import cleanup_file
from ..utils.logging import get_logger
from ..database.session import get_db
from ..services.audit.audit_service import AuditService

logger = get_logger(__name__)

async def process_pdf_job(job: Job) -> Dict[str, Any]:
    """Process a PDF job asynchronously."""
    logger.info("Starting PDF processing", job_id=job.id)
    file_path = None
    audit_service = None
    audit_job_id = job.id

    try:
        # Extract job parameters
        file_path = job.input_data.get("file_path")
        user_info = job.input_data.get("user_info", {})
        mode = job.input_data.get("mode", "free")
        api_key = job.input_data.get("api_key")
        output_dir = job.input_data.get("output_dir")
        
        if not file_path:
            raise ValueError("file_path is required")
        
        if not os.path.exists(file_path):
            raise ValueError(f"File not found: {file_path}")
        
        # Create output directory if not provided
        if not output_dir:
            output_dir = os.path.dirname(file_path)

        await publish_job_progress(
            job.id,
            stage="queued",
            message="Job accepted. Preparing PDF hygiene check…",
        )
        
        # Bootstrap audit service for this job
        try:

            db = next(get_db())
            audit_service = AuditService(db)
            # Auto-provision user/tenant and create a processing job row
            import hashlib, os as _os
            file_hash = hashlib.sha256(open(file_path, 'rb').read()).hexdigest()
            file_size = _os.path.getsize(file_path)
            original_filename = job.input_data.get("original_filename", _os.path.basename(file_path))
            user_id = job.user_id or "anonymous"
            tenant_id = "default"
            audit_service.create_processing_job(
                tenant_id=tenant_id,
                user_id=user_id,
                job_id=audit_job_id,
                original_filename=original_filename,
                file_hash=file_hash,
                file_size_bytes=file_size,
                processing_mode=mode.upper(),
            )
        except Exception as ae:
            logger.warning("Audit job creation failed (non-fatal)", job_id=job.id, error=str(ae))
            audit_service = None

        # Early hygiene check so UI can show details + green tick before full parse
        await publish_job_progress(
            job.id,
            stage="hygiene",
            message="Running PDF hygiene check…",
        )
        hygiene_payload = None
        try:
            from pathlib import Path as _Path
            from .banks._shared.hygiene_check import HygieneCheck

            checker = HygieneCheck(
                pdf_directory=_Path(file_path).parent,
                audit_service=audit_service,
                job_id=audit_job_id,
            )
            hygiene_result = checker.validate_single_pdf(
                _Path(file_path),
                user_id=str(job.user_id or "SYSTEM"),
                goal_id="GENERAL",
                original_filename=original_filename,
                bank_hint=user_info.get("bank_name"),
            )
            checker.log_hygiene_check_result(hygiene_result)

            hygiene_payload = hygiene_result_to_progress(hygiene_result)
            await publish_job_progress(
                job.id,
                stage="hygiene_complete",
                message=(
                    "Hygiene check passed"
                    if hygiene_result.is_healthy
                    else "Hygiene check completed with warnings"
                ),
                hygiene=hygiene_payload,
            )
        except Exception as he:
            logger.warning("Early hygiene check failed (non-fatal)", job_id=job.id, error=str(he))
            await publish_job_progress(
                job.id,
                stage="hygiene_complete",
                message="Hygiene check skipped — continuing with parsing",
                hygiene={
                    "is_healthy": True,
                    "file_name": os.path.basename(file_path),
                    "page_count": 0,
                    "bank_name": user_info.get("bank_name") or "unknown",
                    "format_id": "",
                    "transaction_count": 0,
                    "start_date": "N/A",
                    "end_date": "N/A",
                    "issues": [],
                    "warnings": [f"Hygiene pre-check unavailable: {he}"],
                },
            )

        await publish_job_progress(
            job.id,
            stage="parsing",
            message="Extracting transactions and generating report…",
            hygiene=hygiene_payload,
        )

        # Process the statement using existing pipeline
        logger.info("Processing statement", job_id=job.id, file_path=file_path)
        result = process_statement(
            file_path=file_path,
            user_info=user_info,
            mode=mode,
            api_key=api_key,
            output_dir=output_dir,
            audit_service=audit_service,
            job_id=audit_job_id,
        )

        if result.get("status") != "success":
            error_payload = result.get("error") or {}
            if isinstance(error_payload, dict):
                error_message = error_payload.get("message") or "PDF processing failed"
            else:
                error_message = str(error_payload) or "PDF processing failed"
            raise RuntimeError(error_message)

        await publish_job_progress(
            job.id,
            stage="report",
            message="Finalizing Excel report…",
            hygiene=hygiene_payload,
        )
        
        # Update processing job with success
        if audit_service:
            try:
                txn_count = result.get("stats", {}).get("total_transactions", 0)
                parser_used = result.get("performance", {}).get("parser_used", "unknown")
                processing_ms = int(result.get("performance", {}).get("total_time_ms", 0))
                audit_service.update_processing_job(
                    job_id=audit_job_id,
                    status="COMPLETED",
                    bank_name=user_info.get("bank_name", ""),
                    transaction_count=txn_count,
                    parser_used=parser_used,
                    processing_time_ms=processing_ms,
                )
            except Exception as ue:
                logger.warning("Audit job update failed (non-fatal)", job_id=job.id, error=str(ue))

        frontend_result = build_frontend_processing_result(
            result,
            mode=mode,
            excel_url=f"/api/jobs/{job.id}/download",
        )
        if hygiene_payload:
            frontend_result["hygiene"] = hygiene_payload
            frontend_result["progress"] = {
                "stage": "completed",
                "message": "Processing complete",
                "hygiene": hygiene_payload,
                "hygiene_complete": True,
            }
        return frontend_result

        
    except Exception as e:
        logger.error("PDF processing failed", job_id=job.id, error=str(e))
        if audit_service:
            try:
                audit_service.update_processing_job(
                    job_id=audit_job_id,
                    status="FAILED",
                    error_message=str(e),
                )
            except Exception:
                pass
        raise
    finally:
        try:
            if file_path:
                cleanup_file(file_path)
        except Exception:
            pass


def register_pdf_processor():
    """Register the PDF processor with the task processor."""
    from ..services.task_processor import task_processor
    
    task_processor.register_processor(JobType.PDF_PROCESSING, process_pdf_job)
    logger.info("PDF processor registered")
