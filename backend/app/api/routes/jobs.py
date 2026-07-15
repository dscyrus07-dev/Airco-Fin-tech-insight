import os
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse, Response

from ...models.job import Job, JobStatus, JobUpdate, JobType
from ...services.file_history_service import file_history_service
from ...services.redis_job_store import redis_job_store
from ...utils.correlation import get_correlation_id
from ...utils.logging import get_logger
from ...dependencies.auth import get_current_user, get_current_user_optional, get_admin_user, check_user_ownership

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_from_file_record(record) -> Job:
    status_value = (record.status or "pending").upper()
    try:
        status = JobStatus(status_value.lower())
    except Exception:
        status = JobStatus.PENDING

    result_data = {}
    if record.report_object_key:
        result_data["excel_object_key"] = record.report_object_key
    if record.report_filename:
        result_data["report_filename"] = record.report_filename
    if record.total_transactions is not None:
        result_data["total_transactions"] = record.total_transactions

    return Job(
        id=record.job_id,
        type=JobType.PDF_PROCESSING,
        status=status,
        correlation_id=record.job_id,
        user_id=record.user_id,
        bank_name=record.bank_name,
        input_data={
            "original_filename": record.original_filename,
            "batch_id": record.batch_id,
            "statement_label": record.statement_label,
            "mode": record.mode,
            "upload_object_key": record.upload_object_key,
        },
        result_data=result_data,
        error_message=record.error_message,
        created_at=record.created_at,
        completed_at=record.completed_at,
    )


async def _get_job_or_history(job_id: str) -> Job:
    job = await redis_job_store.get_job(job_id)
    if job:
        return job

    record = file_history_service.get_by_job_id(job_id)
    if record:
        return _job_from_file_record(record)

    raise HTTPException(status_code=404, detail="Job not found")


def _ensure_job_access(job: Job, current_user: Optional[dict]) -> None:
    if current_user and not check_user_ownership(job.user_id or "", current_user):
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only view your own jobs"
        )


def _download_from_storage(bucket: str, object_key: str) -> bytes:
    from ...utils.file_handler import download_bytes_from_storage

    content = download_bytes_from_storage(bucket, object_key)
    if content is None:
        raise HTTPException(
            status_code=503,
            detail="Object storage download is unavailable or the object was not found.",
        )
    return content


@router.get("/{job_id}", response_model=Job)
async def get_job(
    job_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Get job status and details."""
    job = await _get_job_or_history(job_id)
    
    _ensure_job_access(job, current_user)
    
    return job


@router.get("/{job_id}/download")
async def download_job_result(
    job_id: str,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """Download the Excel generated for a completed async job."""
    job = await _get_job_or_history(job_id)

    _ensure_job_access(job, current_user)

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
            from ...core.config import settings as _settings
            content = _download_from_storage(_settings.S3_BUCKET_REPORTS, excel_object_key)
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
            )
        except Exception as e:
            logger.error("Storage download failed", job_id=job_id, object_key=excel_object_key, error=str(e))


    raise HTTPException(status_code=404, detail="Result file not found")

@router.get("/", response_model=List[Job])
async def list_jobs(
    current_user: dict = Depends(get_current_user),
    status: Optional[JobStatus] = None
):
    """List jobs for the current user."""
    jobs = []
    
    # Get all jobs and filter by user ownership
    all_jobs = await redis_job_store.list_jobs()
    if not all_jobs:
        all_records = file_history_service.list_all()
        all_jobs = [_job_from_file_record(record) for record in all_records]
    
    for job in all_jobs:
        # Admin can see all jobs, users can only see their own
        if check_user_ownership(job.user_id or "", current_user):
            if status is None or job.status == status:
                jobs.append(job)
    
    return jobs

# Admin-only endpoints
@router.get("/admin/all", response_model=List[Job])
async def list_all_jobs(
    current_user: dict = Depends(get_admin_user),
    status: Optional[JobStatus] = None
):
    """List all jobs (admin only)."""
    jobs = await redis_job_store.list_jobs()
    if not jobs:
        jobs = [_job_from_file_record(record) for record in file_history_service.list_all()]
    
    if status is not None:
        jobs = [job for job in jobs if job.status == status]
    
    return jobs

@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a job."""
    job = await _get_job_or_history(job_id)
    
    # Check ownership
    if not check_user_ownership(job.user_id or "", current_user):
        raise HTTPException(
            status_code=403, 
            detail="Access denied: You can only delete your own jobs"
        )
    
    # Only allow deletion of completed or failed jobs
    if job.status not in [JobStatus.COMPLETED, JobStatus.FAILED]:
        raise HTTPException(
            status_code=400, 
            detail="Can only delete completed or failed jobs"
        )
    
    if await redis_job_store.get_job(job_id):
        await redis_job_store.delete_job(job_id)
    if not file_history_service.delete_file(job.user_id or "", job_id):
        raise HTTPException(status_code=404, detail="File not found or access denied")
    return {"message": "Job deleted successfully"}

@router.post("/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Cancel a running job."""
    job = await _get_job_or_history(job_id)
    
    # Check ownership
    if not check_user_ownership(job.user_id or "", current_user):
        raise HTTPException(
            status_code=403, 
            detail="Access denied: You can only cancel your own jobs"
        )
    
    # Only allow cancellation of running jobs
    if job.status != JobStatus.RUNNING:
        raise HTTPException(
            status_code=400, 
            detail="Can only cancel running jobs"
        )
    
    if await redis_job_store.get_job(job_id):
        await redis_job_store.update_job_status(job_id, JobStatus.CANCELLED)
    else:
        file_history_service.mark_cancelled(job_id)
    logger.info("Job cancelled", job_id=job_id, correlation_id=get_correlation_id())
    return {"message": "Job cancelled successfully"}
