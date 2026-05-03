"""Pytest bootstrap: test environment and Redis stubs before importing the application."""

from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ.setdefault("FLASK_SECRET_KEY", "pytest-flask-secret")
os.environ.setdefault("INSIGHTSDSA_USE_MEMORY_CHECKPOINTER", "1")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")

import fakeredis  # noqa: E402
import redis as redis_lib  # noqa: E402


def _fake_from_url(url, **kwargs):
    return fakeredis.FakeStrictRedis(decode_responses=kwargs.get("decode_responses", True))


def _fake_redis(*args, **kwargs):
    return fakeredis.FakeStrictRedis(decode_responses=kwargs.get("decode_responses", True))


redis_lib.from_url = _fake_from_url
redis_lib.Redis = _fake_redis


@pytest.fixture
def flask_app():
    from insightsdsa.app import app
    from insightsdsa.init_db import init_schema

    init_schema()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture
def client(flask_app):
    return flask_app.test_client()
