# ocr-service

Separate GPU service for scanned statements (PaddleOCR-VL-1.6 + PP-OCRv5). The backend never loads a model.
Status: **not yet run on a GPU**. Unit tests cover the pure helpers only (`python -m pytest tests`).

Local GPU run (when a CUDA GPU with >= 8 GB is available):

    docker compose -f infra/docker/docker-compose.yml -f infra/docker/docker-compose.ocr.yml up --build ocr-service
    # backend side (off by default):
    STATEMENT_ENGINE_OCR_MODE=shadow  STATEMENT_ENGINE_OCR_URL=http://ocr-service:8090

No GPU: develop against fixtures instead: `STATEMENT_ENGINE_OCR_URL=mock:<dir>` (see backend/app/services/statement_engine/ocr/client.py).
