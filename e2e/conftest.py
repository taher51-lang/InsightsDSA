"""
Playwright E2E: isolated env + embedded Flask server (no external Postgres/Redis).

Run from repo root::

    pip install -e ".[dev]"
    playwright install chromium
    pytest e2e -v
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

_fd, _SQLITE_PATH = tempfile.mkstemp(prefix="insightsdsa-e2e-", suffix=".sqlite")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_SQLITE_PATH.replace(chr(92), '/')}"
os.environ["ENCRYPTION_KEY"] = Fernet.generate_key().decode()
os.environ.setdefault("FLASK_SECRET_KEY", "e2e-flask-secret")
os.environ.setdefault("INSIGHTSDSA_USE_MEMORY_CHECKPOINTER", "1")
os.environ.setdefault("GOOGLE_CLIENT_ID", "e2e-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "e2e-google-client-secret")

import fakeredis  # noqa: E402
import redis as redis_lib  # noqa: E402


def _fake_from_url(url, **kwargs):
    return fakeredis.FakeStrictRedis(decode_responses=kwargs.get("decode_responses", True))


def _fake_redis(*args, **kwargs):
    return fakeredis.FakeStrictRedis(decode_responses=kwargs.get("decode_responses", True))


redis_lib.from_url = _fake_from_url
redis_lib.Redis = _fake_redis

E2E_PORT = int(os.environ.get("INSIGHTSDSA_E2E_PORT", "18765"))


@pytest.fixture(scope="session")
def playwright_session():
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    yield pw
    pw.stop()


@pytest.fixture(scope="session")
def e2e_base_url() -> str:
    from werkzeug.serving import make_server

    from insightsdsa.app import app
    from insightsdsa.init_db import init_schema
    from insightsdsa.seed_e2e_user import ensure_local_e2e_user, ensure_minimal_curriculum

    init_schema()
    ensure_minimal_curriculum()
    ensure_local_e2e_user()

    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    server = make_server("127.0.0.1", E2E_PORT, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{E2E_PORT}"
    for _ in range(50):
        try:
            import urllib.request

            urllib.request.urlopen(url + "/", timeout=0.5)
            break
        except OSError:
            time.sleep(0.1)
    else:
        pytest.fail("Flask E2E server did not become ready")

    yield url

    server.shutdown()
    try:
        os.remove(_SQLITE_PATH)
    except OSError:
        pass


@pytest.fixture(scope="session")
def browser(playwright_session):
    br = playwright_session.chromium.launch(headless=True)
    yield br
    br.close()


@pytest.fixture
def page(browser, e2e_base_url):
    ctx = browser.new_context(base_url=e2e_base_url)
    pg = ctx.new_page()
    pg.set_default_timeout(30_000)
    yield pg
    ctx.close()
