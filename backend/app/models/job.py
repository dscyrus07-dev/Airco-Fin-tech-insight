"""
Job models for async processing tracking.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobType(str, Enum):
    PDF_PROCESSING = "pdf_processing"
    AI_ANALYSIS = "ai_analysis"
    REPORT_GENERATION = "report_generation"

class Job(BaseModel):
    """Job tracking model."""
    id: str = Field(..., description="Unique job identifier")
    type: JobType = Field(..., description="Type of job")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Current status")
    correlation_id: str = Field(..., description="Correlation ID for request tracking")
    user_id: Optional[str] = Field(None, description="User who initiated the job")
    bank_name: Optional[str] = Field(None, description="Bank name for processing")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Job input parameters")
    result_data: Dict[str, Any] = Field(default_factory=dict, description="Job results")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class JobUpdate(BaseModel):
    """Job update model."""
    status: Optional[JobStatus] = None
    result_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
