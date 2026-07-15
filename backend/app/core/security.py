import logging
from fastapi import UploadFile, HTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


def validate_upload_file(file: UploadFile) -> None:
    """Validate uploaded file for security constraints."""

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    if file.content_type and file.content_type not in settings.ALLOWED_MIME_TYPES:
        logger.warning(f"Rejected file with MIME type: {file.content_type}")
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")


async def validate_file_size(file: UploadFile) -> bytes:
    """Read file content and validate size. Returns file bytes."""
    content = await file.read()

    if len(content) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {settings.MAX_FILE_SIZE_MB}MB.",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    return content
