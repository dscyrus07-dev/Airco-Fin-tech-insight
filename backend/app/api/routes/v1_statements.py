"""
Versioned public API (/api/v1) for platform API keys and JWT principals.
Thin wrappers around existing upload/job services — no pipeline duplication.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response

from ...core.config import settings as app_settings
from ...dependencies.auth import require_scope
from ...models.job import Job, JobStatus, JobType
from ...services.event_publisher import event_publisher
from ...services.file_history_service import file_history_service
from ...services.redis_job_store import redis_job_store
from ...services.task_processor import task_processor
from ...utils.correlation import generate_job_id, get_correlation_id
from ...utils.file_handler import get_temp_dir, storage_user_folder, upload_to_storage
from ...utils.logging import get_logger
from .jobs import _download_from_storage, _get_job_or_history
from .upload_async import _prepare_pdf_for_processing, _safe_object_name, _save_upload_file



logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["v1-statements"])


def _ensure_owner(job: Job, principal: dict) -> None:
    if (job.user_id or "") != (principal.get("id") or ""):
        raise HTTPException(status_code=404, detail="Job not found")


@router.post("/statements")
async def create_statement(
    request: Request,
    principal: dict = Depends(require_scope("upload")),
    file: UploadFile = File(...),
    bank_name: str = Form(...),
    full_name: str = Form(default=""),
    account_type: str = Form(default=""),
    mode: str = Form(default="free"),
    pdf_password: Optional[str] = Form(None),
    batch_id: Optional[str] = Form(None),
    statement_label: Optional[str] = Form(None),
):
    if (mode or "").strip().lower() == "hybrid":
        raise HTTPException(
            status_code=400,
            detail="Hybrid mode is not available via API. Use mode=free.",
        )

    mode = (mode or "free").strip().lower() or "free"
    account_type = (account_type or "").strip().lower()
    user_id = principal["id"]
    user_email = principal.get("email") or ""
    user_name = principal.get("name") or principal.get("preferred_username") or ""
    full_name = full_name or user_name or "api-user"

    logger.info(
        "V1 statement upload",
        bank_name=bank_name,
        filename=file.filename,
        user_id=user_id,
        auth_type=principal.get("auth_type"),
    )

    file_path = await _save_upload_file(file)
    processing_file_path = _prepare_pdf_for_processing(file_path, pdf_password)
    output_dir = get_temp_dir()
    original_filename = _safe_object_name(file.filename or "statement.pdf")
    storage_folder = storage_user_folder(
        user_email=user_email, user_name=user_name, user_id=user_id
    )
    upload_object_key = (
        f"users/{storage_folder}/uploads/"
        f"{Path(original_filename).stem}_{Path(file_path).name}"
    )
    if not upload_to_storage(
        file_path,
        bucket=app_settings.S3_BUCKET_UPLOADS,
        object_key=upload_object_key,
    ):
        for candidate in (file_path, processing_file_path):
            if candidate and os.path.exists(candidate):
                try:
                    os.unlink(candidate)
                except Exception:
                    pass
        raise HTTPException(
            status_code=503,
            detail={
                "error": "Failed to upload source PDF to object storage.",
                "stage": "upload",
                "code": "STORAGE_UPLOAD_FAILED",
            },
        )

    if processing_file_path != file_path:
        try:
            os.unlink(file_path)
        except Exception:
            pass

    user_info = {
        "full_name": full_name,
        "account_type": account_type,
        "bank_name": bank_name,
        "batch_id": batch_id,
        "statement_label": statement_label,
    }

    job = Job(
        id=generate_job_id(),
        type=JobType.PDF_PROCESSING,
        correlation_id=get_correlation_id(),
        user_id=user_id,
        bank_name=bank_name,
        input_data={
            "file_path": processing_file_path,
            "user_info": user_info,
            "mode": mode,
            "api_key": None,
            "output_dir": output_dir,
            "original_filename": file.filename,
            "upload_object_key": upload_object_key,
            "batch_id": batch_id,
            "statement_label": statement_label,
            "pdf_password": pdf_password,
            "auth_type": principal.get("auth_type"),
            "platform_api_key_id": principal.get("api_key_id"),
        },
    )

    job = await redis_job_store.create_job(job)
    file_history_service.upsert_upload(
        job_id=job.id,
        user_id=user_id,
        user_email=user_email or None,
        user_name=user_name or None,
        full_name=full_name or None,
        account_type=account_type or None,
        bank_name=bank_name or None,
        batch_id=batch_id,
        statement_label=statement_label,
        mode=mode or None,
        original_filename=file.filename or "statement.pdf",
        upload_object_key=upload_object_key,
        api_key_id=principal.get("api_key_id") if principal.get("auth_type") == "api_key" else None,
    )

    published = await event_publisher.publish_file_processing_request(
        job_id=job.id,
        file_path=processing_file_path,
        user_info=user_info,
        mode=mode,
        correlation_id=job.correlation_id,
        api_key=None,
        bank_name=bank_name,
        user_id=user_id,
        user_email=user_email,
        user_name=user_name,
        original_filename=file.filename,
        upload_object_key=upload_object_key,
        output_dir=output_dir,
        pdf_password=None if processing_file_path != file_path else pdf_password,
        platform_api_key_id=principal.get("api_key_id"),
    )

    if not published:
        logger.warning("RabbitMQ publish failed; falling back to local task processor", job_id=job.id)
        job = await task_processor.submit_existing_job(job)

    return JSONResponse(
        {
            "job_id": job.id,
            "status": "submitted",
            "message": "Processing started. Check job status with /api/v1/jobs/{job_id}",
        }
    )


@router.get("/jobs/{job_id}")
async def get_job_status(
    job_id: str,
    principal: dict = Depends(require_scope("jobs:read")),
):
    job = await _get_job_or_history(job_id)
    _ensure_owner(job, principal)
    return job


@router.get("/jobs/{job_id}/download")
async def download_job(
    job_id: str,
    principal: dict = Depends(require_scope("download")),
):
    job = await _get_job_or_history(job_id)
    _ensure_owner(job, principal)

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job not completed yet")

    original_filename = job.input_data.get("original_filename", "statement.pdf")
    bank_name = (job.bank_name or "report").replace(" ", "_")
    download_name = f"{Path(original_filename).stem}_{bank_name}_report.xlsx"

    excel_path = job.result_data.get("excel_path")
    if excel_path and os.path.isfile(excel_path):
        return FileResponse(
            path=excel_path,
            filename=download_name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    excel_object_key = job.result_data.get("excel_object_key")
    if excel_object_key:
        try:
            content = _download_from_storage(app_settings.S3_BUCKET_REPORTS, excel_object_key)
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
            )
        except Exception as e:
            logger.error(
                "Storage download failed",
                job_id=job_id,
                object_key=excel_object_key,
                error=str(e),
            )

    raise HTTPException(status_code=404, detail="Result file not found")


@router.get("/jobs")
async def list_jobs(
    principal: dict = Depends(require_scope("jobs:read")),
    status: Optional[JobStatus] = None,
):
    user_id = principal["id"]
    jobs = await redis_job_store.list_jobs(user_id=user_id, status=status)
    if not jobs:
        from .jobs import _job_from_file_record

        records = [
            r
            for r in file_history_service.list_all()
            if (r.user_id or "") == user_id
        ]
        jobs = [_job_from_file_record(r) for r in records]
        if status is not None:
            jobs = [j for j in jobs if j.status == status]
    return jobs


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    principal: dict = Depends(require_scope("jobs:delete")),
):
    job = await _get_job_or_history(job_id)
    _ensure_owner(job, principal)

    if job.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
        raise HTTPException(
            status_code=400,
            detail="Can only delete completed or failed jobs",
        )

    if await redis_job_store.get_job(job_id):
        await redis_job_store.delete_job(job_id)
    if not file_history_service.delete_file(job.user_id or "", job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"message": "Job deleted successfully"}
