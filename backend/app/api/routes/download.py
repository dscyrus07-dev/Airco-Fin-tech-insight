"""
Airco Insights — Download Route
==================================
GET /download/{file_id} endpoint.
Serves generated Excel/PDF files from the application temp directory.
"""

import os
import logging

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse

from app.utils.file_handler import get_temp_dir
from app.services.audit import AuditService, get_audit_context
from app.database.session import get_db
from app.dependencies.auth import check_user_ownership, get_current_user_optional
from app.services.download_tokens import verify_download_token

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".xlsx", ".pdf"}


def _authorise_file_download(job_id: str, current_user: Optional[dict], token: Optional[str]) -> None:
    """Gate a temp-dir file. Files not tied to a job id are admin-only."""
    if job_id and verify_download_token(token, job_id):
        return
    if not current_user:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if "admin" in (current_user.get("roles") or []):
        return
    if not job_id:
        raise HTTPException(status_code=403, detail="Access denied")
    from app.services.file_history_service import file_history_service

    record = file_history_service.get_by_job_id(job_id)
    owner = getattr(record, "user_id", None) if record else None
    if not owner or not check_user_ownership(owner, current_user):
        raise HTTPException(status_code=403, detail="Access denied")


@router.get("/download/{file_id}")
async def download_file(
    request: Request,
    file_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional),
    t: Optional[str] = Query(default=None),
):
    """
    Download a generated report file by its ID (filename).

    Only serves files from the application temp directory with allowed extensions,
    and only to the job's owner / an admin (bearer) or the holder of a signed
    download token issued for that job.
    """
    audit_context = get_audit_context(request)
    db = next(get_db())
    audit_service = AuditService(db)

    safe_name = os.path.basename(file_id)
    if safe_name != file_id:
        raise HTTPException(status_code=400, detail="Invalid file ID.")

    _, ext = os.path.splitext(safe_name)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type.")

    name_job_id = safe_name.split("_")[0] if "_" in safe_name else ""
    if not name_job_id.startswith("JOB"):
        name_job_id = ""
    _authorise_file_download(name_job_id, current_user, t)

    temp_dir = get_temp_dir()
    file_path = os.path.join(temp_dir, safe_name)

    logger.info("Download requested: %s → %s (exists=%s) user=%s", file_id, file_path, os.path.isfile(file_path), audit_context.user_id)

    if not os.path.isfile(file_path):
        audit_service.create_audit_log(
            tenant_id=audit_context.tenant_id,
            event_type="DOWNLOAD",
            event_name="FILE_NOT_FOUND",
            user_id=audit_context.user_id,
            session_id=audit_context.session_id,
            ip_address=audit_context.ip_address,
            user_agent=audit_context.user_agent,
            status='FAILED',
            severity='WARNING',
            metadata={"filename": safe_name, "file_id": file_id}
        )
        raise HTTPException(status_code=404, detail="File not found or expired.")

    file_size = os.path.getsize(file_path)
    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if ext.lower() == ".xlsx"
        else "application/pdf"
    )

    job_id = None
    if "_" in safe_name:
        possible_job_id = safe_name.split("_")[0]
        if possible_job_id.startswith("JOB"):
            job_id = possible_job_id

    if job_id:
        from app.database.audit_models import DownloadLog
        existing_downloads = db.query(DownloadLog).filter(
            DownloadLog.job_id == audit_service.get_processing_job(job_id).id if audit_service.get_processing_job(job_id) else None
        ).count()
        download_number = existing_downloads + 1
        audit_service.create_download_log(
            job_id=job_id,
            user_id=audit_context.user_id,
            filename=safe_name,
            ip_address=audit_context.ip_address,
            download_number=download_number,
            file_size_bytes=file_size,
            user_agent=audit_context.user_agent,
            browser=audit_context.browser,
            os=audit_context.os
        )

    audit_service.create_audit_log(
        tenant_id=audit_context.tenant_id,
        event_type="DOWNLOAD",
        event_name="FILE_DOWNLOADED",
        user_id=audit_context.user_id,
        session_id=audit_context.session_id,
        ip_address=audit_context.ip_address,
        user_agent=audit_context.user_agent,
        metadata={
            "filename": safe_name,
            "file_size_bytes": file_size,
            "file_type": ext.lower(),
            "job_id": job_id
        }
    )

    return FileResponse(
        path=file_path,
        filename=safe_name,
        media_type=media_type,
    )
