import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "Airco Insights Engine"
    VERSION: str = "2.0.0"
    API_PREFIX: str = ""

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Anthropic
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "") or os.getenv("CLAUDE_API_KEY", "")

    # File handling
    MAX_FILE_SIZE_MB: int = 20
    MAX_FILE_SIZE_BYTES: int = MAX_FILE_SIZE_MB * 1024 * 1024
    ALLOWED_MIME_TYPES: list = ["application/pdf"]
    TEMP_DIR: str = os.getenv("TEMP_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "tmp"))

    # Data retention
    DATA_RETENTION_DAYS: int = int(os.getenv("DATA_RETENTION_DAYS", "7"))
    RETENTION_ENABLED: bool = os.getenv("RETENTION_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
    RETENTION_SWEEP_INTERVAL_MINUTES: int = int(os.getenv("RETENTION_SWEEP_INTERVAL_MINUTES", "60"))

    # PDF detection
    PDF_TEXT_THRESHOLD: int = 500
    PDF_SCAN_PAGES: int = 3

    # AI classification
    AI_BATCH_SIZE: int = 25

    # Processing
    CORS_ORIGINS: list = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,https://insights.theairco.ai,https://test.theairco.ai,https://theairco.ai",
        ).split(",")
        if origin.strip()
    ]
    
    # Auth Service (for microservices migration)
    AUTH_SERVICE_URL: str = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
    FILE_SERVICE_URL: str = os.getenv("FILE_SERVICE_URL", "http://localhost:8002")
    PDF_SERVICE_URL: str = os.getenv("PDF_SERVICE_URL", "http://localhost:8003")
    AI_SERVICE_URL: str = os.getenv("AI_SERVICE_URL", "http://localhost:8004")
    REPORT_SERVICE_URL: str = os.getenv("REPORT_SERVICE_URL", "http://localhost:8005")
    
    # Redis (for job storage in Phase 1)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # RabbitMQ (for message queuing in Phase 1)
    RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "amqp://change-me-rabbitmq-user:change-me-rabbitmq-pass@localhost:5672/")

    # Object Storage — Supabase S3-compatible only
    S3_ENDPOINT: str = os.getenv("S3_ENDPOINT", "")
    S3_ACCESS_KEY: str = os.getenv("S3_ACCESS_KEY", "")
    S3_SECRET_KEY: str = os.getenv("S3_SECRET_KEY", "")
    S3_BUCKET_UPLOADS: str = (
        os.getenv("S3_BUCKET")
        or os.getenv("S3_BUCKET_UPLOADS")
        or "airco-files"
    )
    S3_BUCKET_REPORTS: str = os.getenv("S3_BUCKET_REPORTS", "airco-reports")

    S3_REGION: str = os.getenv("S3_REGION", "ap-southeast-2")
    # path-style is required for Supabase S3 protocol
    S3_ADDRESSING_STYLE: str = os.getenv("S3_ADDRESSING_STYLE", "path")
    # Supabase buckets are pre-created — never auto-create by default
    S3_SKIP_CREATE_BUCKET: bool = os.getenv(
        "S3_SKIP_CREATE_BUCKET",
        "true",
    ).lower() in {"1", "true", "yes", "on"}
    STORAGE_TYPE: str = os.getenv("STORAGE_TYPE", "supabase-s3")



    # Keycloak / JWT verification
    # Public issuer base (must match the 'iss' claim in tokens the frontend receives)
    KEYCLOAK_URL: str = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
    # Internal URL used to fetch JWKS from inside the cluster (defaults to public URL)
    KEYCLOAK_INTERNAL_URL: str = os.getenv("KEYCLOAK_INTERNAL_URL", "") or os.getenv("KEYCLOAK_URL", "http://localhost:8080")
    KEYCLOAK_REALM: str = os.getenv("KEYCLOAK_REALM", "airco-insights")
    # Optional audience enforcement (comma-separated). Empty disables the aud check.
    KEYCLOAK_AUDIENCE: str = os.getenv("KEYCLOAK_AUDIENCE", "")
    # Optional authorized-party (client id) allow-list (comma-separated).
    KEYCLOAK_ALLOWED_AZP: str = os.getenv("KEYCLOAK_ALLOWED_AZP", "frontend-app")
    # JWKS cache lifetime in seconds.
    JWKS_CACHE_TTL_SECONDS: int = int(os.getenv("JWKS_CACHE_TTL_SECONDS", "3600"))
    # Emergency-only: allow unverified token decode if JWKS is unreachable.
    # NEVER enable in production; defaults to off so unsigned tokens are rejected.
    AUTH_ALLOW_INSECURE_FALLBACK: bool = os.getenv("AUTH_ALLOW_INSECURE_FALLBACK", "false").lower() in {"1", "true", "yes", "on"}

    # Platform API keys
    API_KEY_RATE_LIMIT_DEFAULT: int = int(os.getenv("API_KEY_RATE_LIMIT_DEFAULT", "60"))
    API_KEY_ENVIRONMENT: str = os.getenv("API_KEY_ENVIRONMENT", "live")  # live | test
    API_KEY_DAILY_QUOTA_DEFAULT: int = int(os.getenv("API_KEY_DAILY_QUOTA_DEFAULT", "0"))  # 0 = unlimited

    @property
    def keycloak_issuer(self) -> str:
        return f"{self.KEYCLOAK_URL.rstrip('/')}/realms/{self.KEYCLOAK_REALM}"

    @property
    def keycloak_jwks_url(self) -> str:
        base = (self.KEYCLOAK_INTERNAL_URL or self.KEYCLOAK_URL).rstrip("/")
        return f"{base}/realms/{self.KEYCLOAK_REALM}/protocol/openid-connect/certs"


settings = Settings()
