"""
Unit tests for platform API key service (Commit 1).
Uses in-memory SQLite — no FastAPI routes.
"""

import asyncio
import os
import re
from unittest.mock import AsyncMock, MagicMock, patch

# session.py requires DATABASE_URL at import time
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.models import ApiKey
from app.database.session import Base
from app.services import api_key_service as svc


HEX32 = re.compile(r"^[0-9a-f]{32}$")


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine, tables=[ApiKey.__table__])
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


class TestGenerateAndHash:
    def test_generate_live_prefix_and_hex(self):
        key = svc.generate_api_key("live")
        assert key.startswith("airco_sk_live_")
        suffix = key[len("airco_sk_live_") :]
        assert HEX32.match(suffix)

    def test_generate_test_prefix(self):
        key = svc.generate_api_key("test")
        assert key.startswith("airco_sk_test_")
        assert HEX32.match(key[len("airco_sk_test_") :])

    def test_hash_key_deterministic(self):
        raw = "airco_sk_live_abc"
        assert svc.hash_key(raw) == svc.hash_key(raw)
        assert len(svc.hash_key(raw)) == 64

    def test_extract_prefix_first_20(self):
        raw = "airco_sk_live_a1b2c3d4e5f6g7h8"
        assert svc.extract_prefix(raw) == raw[:20]
        assert len(svc.extract_prefix(raw)) == 20


class TestVerifyAndLifecycle:
    def test_verify_succeeds_for_active_key(self, db_session, monkeypatch):
        monkeypatch.setattr(svc.settings, "API_KEY_ENVIRONMENT", "live")
        raw, record = svc.create_key(
            user_id="user-a",
            tenant_id="default",
            name="Test",
            scopes=svc.DEFAULT_SCOPES,
            environment="live",
            db=db_session,
        )
        assert record.usage_count == 0
        found = svc.verify_key(raw, db_session)
        assert found is not None
        assert found.id == record.id
        assert found.usage_count == 1
        assert found.last_used_at is not None

    def test_verify_increments_usage_once_per_call(self, db_session, monkeypatch):
        monkeypatch.setattr(svc.settings, "API_KEY_ENVIRONMENT", "live")
        raw, _ = svc.create_key(
            user_id="user-a",
            tenant_id="default",
            name="Test",
            scopes=None,
            environment="live",
            db=db_session,
        )
        svc.verify_key(raw, db_session)
        found = svc.verify_key(raw, db_session)
        assert found.usage_count == 2

    def test_verify_fails_wrong_key(self, db_session, monkeypatch):
        monkeypatch.setattr(svc.settings, "API_KEY_ENVIRONMENT", "live")
        svc.create_key(
            user_id="user-a",
            tenant_id="default",
            name="Test",
            scopes=None,
            environment="live",
            db=db_session,
        )
        assert svc.verify_key("airco_sk_live_" + "0" * 32, db_session) is None

    def test_verify_fails_revoked(self, db_session, monkeypatch):
        monkeypatch.setattr(svc.settings, "API_KEY_ENVIRONMENT", "live")
        raw, record = svc.create_key(
            user_id="user-a",
            tenant_id="default",
            name="Test",
            scopes=None,
            environment="live",
            db=db_session,
        )
        assert svc.revoke_key(str(record.id), "user-a", db_session) is True
        assert svc.verify_key(raw, db_session) is None

    def test_verify_fails_wrong_environment(self, db_session, monkeypatch):
        monkeypatch.setattr(svc.settings, "API_KEY_ENVIRONMENT", "live")
        raw, _ = svc.create_key(
            user_id="user-a",
            tenant_id="default",
            name="Test",
            scopes=None,
            environment="test",
            db=db_session,
        )
        assert svc.verify_key(raw, db_session) is None

    def test_revoke_sets_inactive_and_revoked_at(self, db_session, monkeypatch):
        monkeypatch.setattr(svc.settings, "API_KEY_ENVIRONMENT", "live")
        _, record = svc.create_key(
            user_id="user-a",
            tenant_id="default",
            name="Test",
            scopes=None,
            environment="live",
            db=db_session,
        )
        assert svc.revoke_key(str(record.id), "user-a", db_session) is True
        db_session.refresh(record)
        assert record.is_active is False
        assert record.revoked_at is not None

    def test_revoke_fails_wrong_owner(self, db_session, monkeypatch):
        monkeypatch.setattr(svc.settings, "API_KEY_ENVIRONMENT", "live")
        _, record = svc.create_key(
            user_id="user-a",
            tenant_id="default",
            name="Test",
            scopes=None,
            environment="live",
            db=db_session,
        )
        assert svc.revoke_key(str(record.id), "user-b", db_session) is False
        db_session.refresh(record)
        assert record.is_active is True

    def test_list_keys_for_user(self, db_session, monkeypatch):
        monkeypatch.setattr(svc.settings, "API_KEY_ENVIRONMENT", "live")
        svc.create_key("user-a", "default", "A1", None, "live", db_session)
        svc.create_key("user-b", "default", "B1", None, "live", db_session)
        keys = svc.list_keys("user-a", db_session)
        assert len(keys) == 1
        assert keys[0].name == "A1"

    def test_create_returns_raw_once_with_matching_prefix(self, db_session, monkeypatch):
        monkeypatch.setattr(svc.settings, "API_KEY_ENVIRONMENT", "live")
        raw, record = svc.create_key(
            "user-a", "default", "Partner", svc.DEFAULT_SCOPES, "live", db_session
        )
        assert raw.startswith("airco_sk_live_")
        assert record.key_prefix == raw[:20]
        assert record.key_hash == svc.hash_key(raw)
        assert "jobs:delete" not in record.scopes


class TestRateLimit:
    def test_rate_limit_allows_then_blocks(self):
        mock_client = MagicMock()
        counter = {"n": 0}

        async def incr(_key):
            counter["n"] += 1
            return counter["n"]

        mock_client.incr = AsyncMock(side_effect=incr)
        mock_client.expire = AsyncMock()

        with patch.object(svc._rate_limit_redis, "client", return_value=mock_client):
            limit = 60

            async def run():
                results = []
                for _ in range(61):
                    results.append(await svc.check_rate_limit("key-1", limit))
                return results

            results = asyncio.get_event_loop().run_until_complete(run())
            assert all(results[:60])
            assert results[60] is False
            assert mock_client.expire.await_count == 1
