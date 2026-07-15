import pytest
import asyncio
from fastapi.testclient import TestClient
from app.main import app
from app.services.job_store import job_store
from app.models.job import JobStatus
from app.dependencies.auth import get_current_user, get_current_user_optional

def mock_get_current_user():
    return {
        "id": "test-user",
        "email": "test@example.com",
        "name": "Test User",
        "roles": ["user"]
    }

def mock_get_current_user_optional():
    return {
        "id": "test-user",
        "email": "test@example.com",
        "name": "Test User",
        "roles": ["user"]
    }

app.dependency_overrides[get_current_user] = mock_get_current_user
app.dependency_overrides[get_current_user_optional] = mock_get_current_user_optional

client = TestClient(app)

def test_health_check():
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "engine" in data
    assert "version" in data

def test_correlation_id_header():
    """Test correlation ID is added to responses."""
    response = client.get("/health")
    assert "X-Correlation-ID" in response.headers
    assert len(response.headers["X-Correlation-ID"]) > 0

def test_job_list_empty():
    """Test job listing when no jobs exist."""
    response = client.get("/api/jobs/")
    assert response.status_code == 200
    assert response.json() == []

def test_async_upload_missing_file():
    """Test async upload without file."""
    response = client.post("/api/upload/bank-statement-async", data={
        "bank_name": "HDFC"
    })
    assert response.status_code == 422  # Validation error

def test_async_upload_invalid_bank():
    """Test async upload with unsupported bank."""
    response = client.post("/api/upload/bank-statement-async", data={
        "bank_name": "UnknownBank"
    })
    assert response.status_code == 422  # Validation error

def test_job_not_found():
    """Test getting non-existent job."""
    response = client.get("/api/jobs/non-existent-job-id")
    assert response.status_code == 404

def test_download_non_existent_job():
    """Test downloading result for non-existent job."""
    response = client.get("/api/upload/download/non-existent-job-id")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_job_lifecycle():
    """Test complete job lifecycle."""
    # This would require a real PDF file to test end-to-end
    # For now, just test the job store directly
    
    from app.models.job import Job, JobType
    from app.utils.correlation import generate_job_id
    
    job = Job(
        id=generate_job_id(),
        type=JobType.PDF_PROCESSING,
        correlation_id="test-correlation",
        user_id="test-user",
        bank_name="HDFC",
        input_data={"test": "data"}
    )
    
    # Create job
    created_job = await job_store.create_job(job)
    assert created_job.id == job.id
    assert created_job.status == JobStatus.PENDING
    
    # Get job
    retrieved_job = await job_store.get_job(job.id)
    assert retrieved_job is not None
    assert retrieved_job.id == job.id
    
    # Update job
    from app.models.job import JobUpdate
    updated_job = await job_store.update_job(job.id, JobUpdate(
        status=JobStatus.COMPLETED,
        result_data={"test": "result"}
    ))
    assert updated_job is not None
    assert updated_job.status == JobStatus.COMPLETED
    assert updated_job.result_data["test"] == "result"

if __name__ == "__main__":
    pytest.main([__file__])
