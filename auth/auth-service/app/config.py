"""
Configuration settings for Auth Service.
"""

import os
from typing import List, Optional

class Settings:
    """Application settings."""
    
    # Keycloak Settings
    KEYCLOAK_URL: str = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
    KEYCLOAK_INTERNAL_URL: str = os.getenv("KEYCLOAK_INTERNAL_URL", os.getenv("KEYCLOAK_URL", "http://localhost:8080"))
    KEYCLOAK_REALM: str = os.getenv("KEYCLOAK_REALM", "airco-insights")
    KEYCLOAK_CLIENT_ID: str = os.getenv("KEYCLOAK_CLIENT_ID", "frontend-app")
    KEYCLOAK_CLIENT_SECRET: str = os.getenv("KEYCLOAK_CLIENT_SECRET", "airco-frontend-secret")
    
    # JWT Settings (for backward compatibility)
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Database Settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/auth_db"
    )
    
    # CORS Settings
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]
    
    # Redis Settings (for token blacklisting)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Service Settings
    SERVICE_NAME: str = "auth-service"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    
    @property
    def keycloak_oidc_url(self) -> str:
        """Get Keycloak OIDC endpoint URL (uses internal URL for container-to-container calls)."""
        return f"{self.KEYCLOAK_INTERNAL_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect"
    
    @property
    def keycloak_jwks_url(self) -> str:
        """Get Keycloak JWKS URL for token verification (uses internal URL for container-to-container calls)."""
        return f"{self.KEYCLOAK_INTERNAL_URL}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/certs"
    
    @property
    def keycloak_issuer(self) -> str:
        """Get Keycloak issuer URL."""
        return f"{self.KEYCLOAK_URL}/realms/{self.KEYCLOAK_REALM}"

settings = Settings()
