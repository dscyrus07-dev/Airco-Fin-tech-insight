"""
Event publisher for emitting domain events.
"""

from typing import Dict, Any, Optional
from datetime import datetime

from .message_queue import message_queue
from ..utils.correlation import get_correlation_id
from ..utils.logging import get_logger

logger = get_logger(__name__)

class EventPublisher:
    """Service for publishing domain events."""

    async def publish_file_processing_request(
        self,
        job_id: str,
        file_path: str,
        user_info: Dict[str, Any],
        mode: str,
        correlation_id: Optional[str] = None,
        api_key: Optional[str] = None,
        bank_name: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        user_name: Optional[str] = None,
        original_filename: Optional[str] = None,
        upload_object_key: Optional[str] = None,
        output_dir: Optional[str] = None,
        pdf_password: Optional[str] = None,
    ) -> bool:
        """Publish the initial file-processing request event."""
        event = {
            "job_id": job_id,
            "correlation_id": correlation_id or get_correlation_id(),
            "file_path": file_path,
            "user_info": user_info,
            "mode": mode,
            "api_key": api_key,
            "bank_name": bank_name,
            "user_id": user_id,
            "user_email": user_email,
            "user_name": user_name,
            "original_filename": original_filename,
            "upload_object_key": upload_object_key,
            "output_dir": output_dir,
            "pdf_password": pdf_password,
        }

        success = await message_queue.publish_message(
            exchange="file_processing",
            routing_key="file.uploaded",
            message=event,
        )

        if success:
            logger.info("File processing request published", job_id=job_id)
        else:
            logger.error("Failed to publish file processing request", job_id=job_id)

        return success

# Global event publisher instance
event_publisher = EventPublisher()
