"""
Airco Insights — Download Route
==================================
GET /download/{file_id} endpoint.
Serves generated Excel/PDF files from the application temp directory.
"""

import os
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.utils.file_handler import get_temp_dir
from app.services.audit import AuditService, get_audit_context
from app.database.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EXTENSIONS = {".xlsx", ".pdf"}


@router.get("/download/{file_id}")
async def download_file(request: Request, file_id: str):
    """
    Download a generated report file by its ID (filename).

    Only serves files from the application temp directory with allowed extensions.
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
