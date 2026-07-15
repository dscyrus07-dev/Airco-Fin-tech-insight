"""
Background task processor for async PDF and AI processing.
Phase 1: Redis-backed processor (will be enhanced with RabbitMQ).
"""

import asyncio
from typing import Dict, Any, Callable
from datetime import datetime

from ..models.job import Job, JobType, JobStatus, JobUpdate
from ..services.redis_job_store import redis_job_store
from ..services.file_history_service import file_history_service
from ..utils.correlation import get_correlation_id, set_correlation_id
from ..utils.logging import get_logger

logger = get_logger(__name__)

class TaskProcessor:
    """Redis-backed task processor for Phase 1."""
    
    def __init__(self):
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}
        self._processors: Dict[JobType, Callable] = {}
        self._job_store = redis_job_store
    
    def register_processor(self, job_type: JobType, processor: Callable):
        """Register a processor function for a job type."""
        self._processors[job_type] = processor
        logger.info("Processor registered", job_type=job_type)
    
    async def submit_job(self, job: Job) -> Job:
        """Submit a job for processing."""
        # Set correlation ID for this job
        set_correlation_id(job.correlation_id)
        
        # Create job in Redis
        job = await self._job_store.create_job(job)
        
        # Start processing task
        task = asyncio.create_task(self._process_job(job))
        self._tasks[job.id] = task
        
        logger.info("Job submitted", job_id=job.id, job_type=job.type)
        return job

    async def submit_existing_job(self, job: Job) -> Job:
        """Schedule an already-created job for processing without recreating it in Redis."""
        set_correlation_id(job.correlation_id)

        task = asyncio.create_task(self._process_job(job))
        self._tasks[job.id] = task

        logger.info("Existing job scheduled", job_id=job.id, job_type=job.type)
        return job
    
    async def _process_job(self, job: Job):
        """Process a single job."""
        try:
            # Set correlation ID for this context
            set_correlation_id(job.correlation_id)
            
            # Update to running
            await self._job_store.update_job(job.id, JobUpdate(status=JobStatus.RUNNING))
            
            # Update file history service
            try:
                file_history_service.mark_running(job.id)
            except Exception as e:
                logger.warning("Failed to update file history service for running status", job_id=job.id, error=str(e))
            
            # Get processor
            processor = self._processors.get(job.type)
            if not processor:
                raise ValueError(f"No processor registered for job type: {job.type}")
            
            # Process the job
            logger.info("Processing job", job_id=job.id, job_type=job.type)
            result = await processor(job)

            if isinstance(result, dict) and result.get("status") == "failed":
                error_payload = result.get("error") or {}
                error_message = (
                    error_payload.get("message")
                    if isinstance(error_payload, dict)
                    else str(error_payload)
                ) or "Processing failed"
                raise RuntimeError(error_message)
            
            # Update with results
            await self._job_store.update_job(job.id, JobUpdate(
                status=JobStatus.COMPLETED,
                result_data=result
            ))
            
            # Update file history service
            try:
                file_history_service.mark_completed(job.id, result)
            except Exception as e:
                logger.warning("Failed to update file history service for completed status", job_id=job.id, error=str(e))
            
            logger.info("Job completed", job_id=job.id, job_type=job.type)
            
        except Exception as e:
            logger.error("Job failed", job_id=job.id, error=str(e))
            await self._job_store.update_job(job.id, JobUpdate(
                status=JobStatus.FAILED,
                error_message=str(e)
            ))
            
            # Update file history service
            try:
                file_history_service.mark_failed(job.id, str(e))
            except Exception as fe:
                logger.warning("Failed to update file history service for failed status", job_id=job.id, error=str(fe))
        
        finally:
            # Clean up task reference
            self._tasks.pop(job.id, None)
    
    async def start(self):
        """Start the task processor."""
        self._running = True
        logger.info("Task processor started")
    
    async def stop(self):
        """Stop the task processor."""
        self._running = False
        
        # Cancel all running tasks
        for task in self._tasks.values():
            task.cancel()
        
        # Wait for tasks to finish
        if self._tasks:
            await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        
        logger.info("Task processor stopped")

# Global instance
task_processor = TaskProcessor()
