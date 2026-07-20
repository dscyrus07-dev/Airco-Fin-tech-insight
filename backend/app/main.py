import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.routes import upload as upload_api
from app.api.routes import download as download_api
from app.api.routes import upload_async as upload_async_api
from app.api.routes import sync as sync_api
from app.api.routes import feedback as feedback_api
from app.api.routes import jobs as jobs_api
from app.api.routes import profile as profile_api
from app.api.routes import auth as auth_api
from app.api.routes import audit_admin as audit_admin_api
from app.api.routes import v1_statements as v1_statements_api
from app.api.routes import v1_api_keys as v1_api_keys_api
from app.services.retention_service import retention_service
from app.middleware.correlation import CorrelationMiddleware
from app.middleware.auth_middleware import AuthMiddleware
from app.middleware.audit_context import AuditContextMiddleware
from app.middleware.request_logger import RequestLoggerMiddleware
from app.utils.logging import get_logger
from contextlib import asynccontextmanager
from app.database.session import initialize_database
from app.database import models as _database_models

logger = get_logger(__name__)

# Log to stdout so container platforms don't treat every line as severity=error (stderr).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    stream=sys.stdout,
    force=True,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    initialize_database()

    # Startup
    from app.services.task_processor import task_processor
    from app.services.pdf_processor import register_pdf_processor
    from app.services.message_queue import message_queue
    from app.services.event_consumer import event_consumer
    
    # Register processors
    register_pdf_processor()
    
    # Start RabbitMQ queue bridge
    await message_queue.connect()
    await event_consumer.start_consuming()

    # Start retention sweep worker
    await retention_service.start()

    # Start system health monitor
    from app.services.monitoring import health_monitor
    await health_monitor.start()

    # Start task processor as a fallback path after RabbitMQ is ready
    await task_processor.start()
    
    logger.info("Application started successfully")
    
    yield
    
    # Shutdown
    from app.services.monitoring import health_monitor
    await health_monitor.stop()
    await retention_service.stop()
    await message_queue.close()
    await task_processor.stop()
    logger.info("Application shutdown complete")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add correlation ID middleware
app.add_middleware(CorrelationMiddleware)

# Add auth middleware (sets user context headers before audit context)
app.add_middleware(AuthMiddleware)

# Add audit context middleware (extracts context from headers)
app.add_middleware(AuditContextMiddleware)

# Add request logger middleware (logs every request to api_request_logs)
app.add_middleware(RequestLoggerMiddleware)

# API Routes
app.include_router(upload_api.router, prefix="/api", tags=["Processing"])
app.include_router(download_api.router, tags=["Download"])
app.include_router(upload_async_api.router, prefix="/api", tags=["Upload Async"])
app.include_router(sync_api.router, prefix="/api", tags=["Sync"])
app.include_router(feedback_api.router, prefix="/api", tags=["Feedback"])
app.include_router(jobs_api.router, prefix="/api", tags=["Jobs"])
app.include_router(profile_api.router, prefix="/api", tags=["Profile"])
app.include_router(auth_api.router, prefix="/api", tags=["Authentication"])
app.include_router(audit_admin_api.router, prefix="/api", tags=["Audit Admin"])
app.include_router(v1_statements_api.router, tags=["V1 Statements"])
app.include_router(v1_api_keys_api.router, tags=["V1 API Keys"])


@app.get("/health")
async def health():
    return {"status": "ok", "engine": "airco-insights", "version": settings.VERSION}
