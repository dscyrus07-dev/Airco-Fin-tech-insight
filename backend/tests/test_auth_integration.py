"""
Test Auth Service integration with monolith.
"""

import pytest
import httpx
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_auth_service_health():
    """Test Auth Service health check."""
    # This would test the actual Auth Service
    # For now, just test that the monolith can handle auth headers
    response = client.get("/health", headers={"X-Correlation-ID": "test-123"})
    assert response.status_code == 200
    assert "X-Correlation-ID" in response.headers

def test_job_endpoint_without_auth():
    """Test job endpoint without authentication (should work)."""
    response = client.get("/api/jobs/")
    # Should work because we're using optional auth
    assert response.status_code == 200

def test_job_endpoint_with_invalid_auth():
    """Test job endpoint with invalid authentication."""
    response = client.get(
        "/api/jobs/",
        headers={"Authorization": "Bearer invalid-token"}
    )
    # Should return empty list (auth service not available)
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_auth_client_fallback():
    """Test auth client fallback behavior."""
    from app.services.auth_client import auth_client
    
    # Test with invalid token (should fallback gracefully)
    result = await auth_client.verify_token("invalid-token")
    assert result is None or result.get("valid") is False

def test_optional_auth_dependency():
    """Test optional authentication dependency."""
    from app.dependencies.auth import get_current_user_optional
    
    # This would need more complex testing setup
    # For now, just ensure the dependency exists
    assert callable(get_current_user_optional)

if __name__ == "__main__":
    pytest.main([__file__])
