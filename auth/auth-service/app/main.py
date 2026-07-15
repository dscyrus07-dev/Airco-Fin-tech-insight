"""
Auth Service - Standalone authentication microservice
Handles JWT tokens, user authentication, and authorization.
"""

import logging
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .routes.auth import router as auth_router
from .utils.jwt_utils import JWTManager
from .utils.logging import get_logger
from .middleware.correlation import CorrelationMiddleware

logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Auth Service starting...")
    yield
    logger.info("Auth Service shutdown complete")

app = FastAPI(
    title="Airco Auth Service",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add correlation ID middleware
app.add_middleware(CorrelationMiddleware)

# Include routes
app.include_router(auth_router, prefix="/auth", tags=["authentication"])

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "auth-service", "version": "1.0.0"}

@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Airco Auth Service", "version": "1.0.0"}
