"""Database layer smoke tests."""

from sqlalchemy import text

from insightsdsa.db import engine, get_session


def test_engine_sqlite():
    assert engine.dialect.name == "sqlite"


def test_get_session_commit():
    with get_session() as s:
        row = s.execute(text("SELECT 1")).scalar_one()
        assert row == 1
