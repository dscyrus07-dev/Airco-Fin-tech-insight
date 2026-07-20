"""
JWT-protected platform API key management endpoints.
"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...database.session import get_db
from ...dependencies.auth import get_current_user
from ...services.api_key_service import (
    ALL_SCOPES,
    DEFAULT_SCOPES,
    create_key,
    list_keys,
    reset_stale_pdf_counts,
    revoke_key,
)
from ...utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/api-keys", tags=["v1-api-keys"])


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    scopes: Optional[List[str]] = None
    environment: str = Field(default="test")


def _serialize_key(k, include_full: Optional[str] = None) -> dict:
    data = {
        "id": str(k.id),
        "name": k.name,
        "key_prefix": k.key_prefix,
        "scopes": k.scopes or [],
        "environment": k.environment,
        "is_active": k.is_active,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "usage_count": k.usage_count or 0,
        "processed_pdf_count": k.processed_pdf_count or 0,
        "rate_limit_per_minute": k.rate_limit_per_minute,
        "created_at": k.created_at.isoformat() if k.created_at else None,
        "revoked_at": k.revoked_at.isoformat() if k.revoked_at else None,
    }
    if include_full is not None:
        data["full_key"] = include_full
    return data


@router.post("")
async def create_api_key(
    body: ApiKeyCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    env = (body.environment or "test").strip().lower()
    if env not in ("live", "test"):
        raise HTTPException(status_code=400, detail="environment must be 'live' or 'test'")

    scopes = body.scopes if body.scopes is not None else list(DEFAULT_SCOPES)
    for scope in scopes:
        if scope not in ALL_SCOPES:
            raise HTTPException(status_code=400, detail=f"Invalid scope: {scope}")

    try:
        raw_key, record = create_key(
            user_id=current_user["id"],
            tenant_id="default",
            name=body.name,
            scopes=scopes,
            environment=env,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _serialize_key(record, include_full=raw_key)


@router.get("")
async def list_api_keys(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Clear impossible leftover counters from earlier bugs (PDFs > Usage)
    try:
        reset_stale_pdf_counts(db)
    except Exception:
        pass
    keys = list_keys(current_user["id"], db)
    return [_serialize_key(k) for k in keys]


@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    success = revoke_key(key_id, current_user["id"], db)
    if not success:
        raise HTTPException(status_code=404, detail="Key not found or already revoked")
    return {"message": "Key revoked successfully"}
