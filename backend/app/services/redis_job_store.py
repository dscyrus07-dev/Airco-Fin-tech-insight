"""
Redis-based job store for Phase 1.
Replaces in-memory job store with Redis for persistence.
"""

import asyncio
import json
from typing import Dict, Optional, List
from datetime import datetime, timezone
import redis.asyncio as redis

from ..models.job import Job, JobStatus, JobUpdate
from ..core.config import settings
from ..utils.logging import get_logger
from .job_store import job_store as fallback_job_store

logger = get_logger(__name__)


def serialize_job(job: Job) -> str:
    """Serialize Job object to JSON string."""
    if hasattr(job, "model_dump_json"):
        return job.model_dump_json()
    else:
        return job.json()


def deserialize_job(job_json: str) -> Job:
    """Deserialize JSON string to Job object."""
    if hasattr(Job, "model_validate_json"):
        return Job.model_validate_json(job_json)
    else:
        return Job.parse_raw(job_json)


class RedisJobStore:
    """Redis-based job storage with connection pooling and JSON serialization."""

    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.key_prefix = "airco:job:"
        # Clients are created lazily per event-loop to avoid "Future attached to a
        # different loop" errors when the module is imported before uvicorn starts.
        self._loop_clients: Dict[int, redis.Redis] = {}

    @property
    def _redis_client(self) -> redis.Redis:
        """Return the Redis client for the currently running event loop."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()
        loop_id = id(loop)
        if loop_id not in self._loop_clients:
            self._loop_clients[loop_id] = redis.from_url(
                self.redis_url, decode_responses=True
            )
        return self._loop_clients[loop_id]
    
    async def disconnect(self):
        """Disconnect from Redis."""
        try:
            await self._redis_client.aclose()
        except Exception:
            pass

    async def create_job(self, job: Job) -> Job:
        """Create a new job in Redis."""
        try:
            job_data = serialize_job(job)

            # Store in Redis with TTL (24 hours)
            await self._redis_client.setex(
                f"{self.key_prefix}{job.id}",
                86400,  # 24 hours TTL
                job_data
            )

            # Add to user's job list
            if job.user_id:
                await self._redis_client.sadd(f"{self.key_prefix}user:{job.user_id}", job.id)

            # Add to status index
            await self._redis_client.sadd(f"{self.key_prefix}status:{job.status.value}", job.id)

            logger.info("Job created in Redis", job_id=job.id, job_type=job.type)
            return job
        except redis.RedisError as exc:
            logger.warning("Redis error in create_job; using in-memory job store fallback", error=str(exc))
            return await fallback_job_store.create_job(job)
    
    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID from Redis."""
        try:
            job_data = await self._redis_client.get(f"{self.key_prefix}{job_id}")
            if not job_data:
                # If not found in Redis, check fallback store just in case
                return await fallback_job_store.get_job(job_id)

            try:
                return deserialize_job(job_data)
            except Exception as e:
                logger.error("Failed to deserialize job", job_id=job_id, error=str(e))
                return None
        except redis.RedisError as exc:
            logger.warning("Redis error in get_job; using in-memory job store fallback", error=str(exc))
            return await fallback_job_store.get_job(job_id)
    
    async def update_job(self, job_id: str, update: JobUpdate) -> Optional[Job]:
        """Update a job in Redis."""
        try:
            # Get existing job
            job = await self.get_job(job_id)
            if not job:
                logger.warning("Job not found for update", job_id=job_id)
                return None

            # Check if this job exists in Redis vs fallback
            is_redis_job = await self._redis_client.exists(f"{self.key_prefix}{job_id}")

            if not is_redis_job:
                # Update fallback job
                return await fallback_job_store.update_job(job_id, update)

            # Remove from old status index
            await self._redis_client.srem(f"{self.key_prefix}status:{job.status.value}", job_id)

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

            # Save updated job
            job_data = serialize_job(job)
            await self._redis_client.setex(f"{self.key_prefix}{job.id}", 86400, job_data)

            # Add to indexes
            if job.user_id:
                await self._redis_client.sadd(f"{self.key_prefix}user:{job.user_id}", job.id)
            await self._redis_client.sadd(f"{self.key_prefix}status:{job.status.value}", job_id)

            logger.info("Job updated in Redis", job_id=job_id, status=job.status)
            return job
        except redis.RedisError as exc:
            logger.warning("Redis error in update_job; using in-memory job store fallback", error=str(exc))
            return await fallback_job_store.update_job(job_id, update)
    
    async def list_jobs(self, user_id: Optional[str] = None, status: Optional[JobStatus] = None) -> List[Job]:
        """List jobs with optional filters."""
        try:
            job_ids = set()

            # Get job IDs based on filters
            if user_id:
                user_jobs = await self._redis_client.smembers(f"{self.key_prefix}user:{user_id}")
                if user_jobs:
                    job_ids.update(user_jobs)

            if status:
                status_jobs = await self._redis_client.smembers(f"{self.key_prefix}status:{status.value}")
                if status_jobs:
                    if job_ids or user_id:
                        job_ids.intersection_update(status_jobs)
                    else:
                        job_ids.update(status_jobs)

            # If no filters, get all jobs (limit to 1000 for performance)
            if not user_id and not status:
                pattern = f"{self.key_prefix}*"
                keys = await self._redis_client.keys(pattern)
                # Filter out the indices
                job_ids = [
                    key.split(":")[-1] 
                    for key in keys 
                    if not key.startswith(f"{self.key_prefix}user:") and not key.startswith(f"{self.key_prefix}status:")
                ][:1000]

            # Fetch jobs
            jobs = []
            for job_id in job_ids:
                job = await self.get_job(job_id)
                if job:
                    jobs.append(job)

            # Also fetch any fallback jobs to merge them
            fallback_jobs = await fallback_job_store.list_jobs(user_id=user_id, status=status)
            # Avoid duplicates if any
            existing_ids = {j.id for j in jobs}
            for fb_job in fallback_jobs:
                if fb_job.id not in existing_ids:
                    jobs.append(fb_job)

            return sorted(jobs, key=lambda j: j.created_at, reverse=True)
        except redis.RedisError as exc:
            logger.warning("Redis error in list_jobs; using in-memory job store fallback", error=str(exc))
            return await fallback_job_store.list_jobs(user_id=user_id, status=status)
    
    async def delete_job(self, job_id: str) -> bool:
        """Delete a job from Redis."""
        try:
            job = await self.get_job(job_id)
            if not job:
                return False

            pipe = self._redis_client.pipeline()
            pipe.delete(f"{self.key_prefix}{job_id}")
            if job.user_id:
                pipe.srem(f"{self.key_prefix}user:{job.user_id}", job_id)
            pipe.srem(f"{self.key_prefix}status:{job.status.value}", job_id)
            await pipe.execute()

            logger.info("Job deleted from Redis", job_id=job_id)
            return True
        except redis.RedisError as exc:
            logger.warning("Redis error in delete_job; using in-memory job store fallback", error=str(exc))
            return False

    async def update_job_status(self, job_id: str, status: JobStatus) -> Optional[Job]:
        """Update only the status of a job — convenience wrapper around update_job."""
        return await self.update_job(job_id, JobUpdate(status=status))

    async def cleanup_old_jobs(self, max_age_hours: int = 24):
        """Clean up old jobs."""
        pass


# Global Redis job store instance
redis_job_store = RedisJobStore()
