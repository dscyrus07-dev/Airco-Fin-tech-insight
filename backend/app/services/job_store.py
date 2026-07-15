"""
In-memory job store for Phase 1 async processing.
Will be replaced with Redis in later phases.
"""

from typing import Dict, Optional
from datetime import datetime, timezone
import asyncio

from ..models.job import Job, JobStatus, JobUpdate
from ..utils.logging import get_logger

logger = get_logger(__name__)

class JobStore:
    """In-memory job storage for development/testing."""
    
    def __init__(self):
        self._jobs: Dict[str, Job] = {}
        self._lock = asyncio.Lock()
    
    async def create_job(self, job: Job) -> Job:
        """Create a new job."""
        async with self._lock:
            self._jobs[job.id] = job
            logger.info("Job created", job_id=job.id, job_type=job.type, correlation_id=job.correlation_id)
            return job
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        async with self._lock:
            return self._jobs.get(job_id)
    
    async def update_job(self, job_id: str, update: JobUpdate) -> Optional[Job]:
        """Update a job."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                logger.warning("Job not found for update", job_id=job_id)
                return None
            
            # Update fields
            if update.status:
                job.status = update.status
                if update.status == JobStatus.RUNNING and not job.started_at:
                    job.started_at = datetime.now(timezone.utc)
                elif update.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                    job.completed_at = datetime.now(timezone.utc)
            
            if update.result_data:
                job.result_data.update(update.result_data)
            
            if update.error_message:
                job.error_message = update.error_message
            
            logger.info("Job updated", job_id=job_id, status=job.status)
            return job
    
    async def list_jobs(self, user_id: Optional[str] = None, status: Optional[JobStatus] = None) -> list[Job]:
        """List jobs with optional filters."""
        async with self._lock:
            jobs = list(self._jobs.values())
            
            if user_id:
                jobs = [j for j in jobs if j.user_id == user_id]
            
            if status:
                jobs = [j for j in jobs if j.status == status]
            
            return sorted(jobs, key=lambda j: j.created_at, reverse=True)

# Global instance
job_store = JobStore()
