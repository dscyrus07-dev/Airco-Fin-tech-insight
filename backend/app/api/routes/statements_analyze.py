"""Analyze-first endpoints (Slice 2C).

POST /api/statements/analyze                          upload 1..N PDFs, get per-document bank/layout/evidence. No processing.
GET  /api/statements/banks                            banks the user can pick when correcting a detection
GET  /api/statements/{analysis_id}                    re-read an analysis (owner only)
POST /api/statements/{analysis_id}/documents/{id}/unlock   supply a PDF password for one locked file
POST /api/statements/{analysis_id}/confirm            CONFIRM / OVERRIDE per document (or confirm_all_detected)
POST /api/statements/{analysis_id}/process            start the existing pipeline for CONFIRMED documents only

Every route requires a verified user (no anonymous fallback) and only ever sees that user's analyses.
"""
import json
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile

from ...core.config import settings
from ...dependencies.auth import get_current_user
from ...services.analysis_service import (
    ANALYZE_MAX_FILES,
    PIPELINE_BANK_NAME,
    AnalysisError,
    UploadedPdf,
    analysis_service,
)
from ...services.statement_engine import default_registry

router = APIRouter(prefix="/statements", tags=["statements-analyze"])

_MAX_TOTAL_BYTES = int(os.getenv("ANALYZE_MAX_TOTAL_MB", "200")) * 1024 * 1024


def _http(exc: AnalysisError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail={"code": exc.code, "error": exc.message})


@router.post("/analyze")
async def analyze_statements(
    files: List[UploadFile] = File(...),
    bank_hint: Optional[str] = Form(None),
    passwords: Optional[str] = Form(None, description="JSON object {filename: password}; used in memory only"),
    user: Dict[str, Any] = Depends(get_current_user),
):
    if not files:
        raise HTTPException(status_code=400, detail={"code": "NO_FILES", "error": "Upload at least one PDF"})
    if len(files) > ANALYZE_MAX_FILES:
        raise HTTPException(status_code=400, detail={"code": "TOO_MANY_FILES", "error": f"At most {ANALYZE_MAX_FILES} files per analysis"})
    pw_map: Dict[str, str] = {}
    if passwords:
        try:
            parsed = json.loads(passwords)
            if isinstance(parsed, dict):
                pw_map = {str(k): str(v) for k, v in parsed.items()}
        except ValueError:
            raise HTTPException(status_code=400, detail={"code": "BAD_PASSWORDS", "error": "passwords must be a JSON object"})

    uploads: List[UploadedPdf] = []
    total = 0
    for f in files:
        # read at most one byte past the per-file limit so an oversized file is flagged without loading all of it
        content = await f.read(settings.MAX_FILE_SIZE_BYTES + 1)
        total += len(content)
        if total > _MAX_TOTAL_BYTES:
            raise HTTPException(status_code=413, detail={"code": "BATCH_TOO_LARGE", "error": "The upload is too large"})
        uploads.append(UploadedPdf(filename=f.filename or "statement.pdf", content=content))
    try:
        return await analysis_service.analyze(user, uploads, passwords=pw_map, bank_hint=bank_hint)
    except AnalysisError as exc:
        raise _http(exc)


@router.get("/banks")
async def list_banks(user: Dict[str, Any] = Depends(get_current_user)):
    reg = default_registry()
    return {
        "banks": [
            {"id": bid, "name": reg.get(bid).display_name if reg.get(bid) else name, "pipeline_name": name}
            for bid, name in PIPELINE_BANK_NAME.items()
        ]
    }


@router.get("/{analysis_id}")
async def get_analysis(analysis_id: str, user: Dict[str, Any] = Depends(get_current_user)):
    try:
        return await analysis_service.get(analysis_id, user)
    except AnalysisError as exc:
        raise _http(exc)


@router.post("/{analysis_id}/documents/{document_id}/unlock")
async def unlock_document(
    analysis_id: str,
    document_id: str,
    payload: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(get_current_user),
):
    password = payload.get("password")
    if not isinstance(password, str) or not password:
        raise HTTPException(status_code=400, detail={"code": "PASSWORD_REQUIRED", "error": "password is required"})
    try:
        return await analysis_service.unlock(analysis_id, document_id, user, password)
    except AnalysisError as exc:
        raise _http(exc)


@router.post("/{analysis_id}/confirm")
async def confirm_documents(
    analysis_id: str,
    payload: Dict[str, Any] = Body(...),
    user: Dict[str, Any] = Depends(get_current_user),
):
    decisions = payload.get("documents") or []
    if not isinstance(decisions, list) or any(not isinstance(d, dict) for d in decisions):
        raise HTTPException(status_code=400, detail={"code": "BAD_REQUEST", "error": "documents must be a list of objects"})
    try:
        return await analysis_service.confirm(
            analysis_id, user, decisions, confirm_all_detected=bool(payload.get("confirm_all_detected"))
        )
    except AnalysisError as exc:
        raise _http(exc)


@router.post("/{analysis_id}/process")
async def process_confirmed(
    analysis_id: str,
    payload: Optional[Dict[str, Any]] = Body(default=None),
    user: Dict[str, Any] = Depends(get_current_user),
):
    ids = (payload or {}).get("document_ids")
    try:
        return await analysis_service.process_confirmed(analysis_id, user, ids if isinstance(ids, list) else None)
    except AnalysisError as exc:
        raise _http(exc)
