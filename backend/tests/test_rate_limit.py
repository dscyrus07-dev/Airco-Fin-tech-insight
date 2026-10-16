import pytest
from fastapi import HTTPException

from app.services import rate_limit as rl


def test_rate_limit_blocks_after_limit_and_keys_are_independent():
    rl._hits.clear()
    for _ in range(3):
        rl.check_rate_limit("u1", limit=3)
    with pytest.raises(HTTPException) as e:
        rl.check_rate_limit("u1", limit=3)
    assert e.value.status_code == 429
    assert e.value.headers.get("Retry-After")
    rl.check_rate_limit("u2", limit=3)


def test_rate_limit_window_expires():
    rl._hits.clear()
    rl.check_rate_limit("w", limit=1, window_seconds=1)
    import time
    time.sleep(1.1)
    rl.check_rate_limit("w", limit=1, window_seconds=1)


def test_limit_zero_disables():
    rl._hits.clear()
    for _ in range(50):
        rl.check_rate_limit("z", limit=0)


def test_env_defaults(monkeypatch):
    monkeypatch.delenv("MAX_PDF_PAGES", raising=False)
    monkeypatch.delenv("UPLOAD_RATE_LIMIT_PER_MINUTE", raising=False)
    assert rl.max_pdf_pages() == 500 and rl.upload_limit_per_minute() == 30
