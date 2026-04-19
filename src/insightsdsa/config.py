"""
Application configuration loaded from environment variables (and optional ``.env``).

Import ``settings`` after this module is loaded; ``load_dotenv()`` runs once here.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Final

from dotenv import load_dotenv

from .constants import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")


def _env(key: str, default: str | None = None) -> str | None:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return default
    return str(v).strip()


def _env_bool(key: str, default: bool = False) -> bool:
    v = os.getenv(key)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    v = os.getenv(key)
    if v is None or str(v).strip() == "":
        return default
    return int(v.strip())


def _build_sqlalchemy_database_url(
    *,
    explicit_url: str | None,
    db_backend: str,
    db_host: str | None,
    db_port: str | None,
    db_name: str | None,
    db_user: str | None,
    db_pass: str | None,
    mysql_driver: str,
) -> str:
    if explicit_url:
        return explicit_url
    backend = (db_backend or "postgresql").lower()
    auth = f"{db_user}:{db_pass}@" if db_user else ""
    host_port = f"{db_host}:{db_port}" if db_port else (db_host or "")
    if backend in ("mysql", "mariadb"):
        return f"mysql+{mysql_driver}://{auth}{host_port}/{db_name or ''}"
    return f"postgresql+psycopg://{auth}{host_port}/{db_name or ''}"


def _build_checkpoint_psycopg_uri(
    *,
    explicit: str | None,
    db_user: str | None,
    db_pass: str | None,
    db_host: str | None,
    db_port: str | None,
    db_name: str | None,
) -> str:
    if explicit:
        return explicit
    host_part = f"{db_host}:{db_port}" if db_port else (db_host or "")
    return f"postgresql://{db_user}:{db_pass}@{host_part}/{db_name or ''}"


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of configuration."""

    # --- Database (SQLAlchemy app DB) ---
    database_url: str
    db_backend: str
    mysql_driver: str

    # --- LangGraph Postgres checkpoint DSN (psycopg / libpq style) ---
    checkpoint_postgres_uri: str
    checkpoint_pool_min_size: int
    checkpoint_pool_max_size: int
    checkpoint_connect_timeout: int

    # --- SQLAlchemy engine ---
    sqlalchemy_echo: bool
    sqlalchemy_pool_pre_ping: bool

    # --- Flask ---
    flask_secret_key: str
    session_cookie_samesite: str
    session_cookie_secure: bool
    session_cookie_httponly: bool
    session_cookie_name: str

    # --- Security (required to run the Flask app; optional for DB-only scripts) ---
    encryption_key: str | None

    # --- Redis ---
    # When True, use in-process fakeredis (no server). Good for local dev; not for multi-process prod.
    use_memory_redis: bool
    redis_url: str | None
    redis_host: str
    redis_port: int
    redis_db: int
    redis_password: str | None

    # --- Google OAuth ---
    google_client_id: str | None
    google_client_secret: str | None
    google_openid_metadata_url: str
    # Optional: must match an "Authorized redirect URI" in Google Cloud Console exactly
    # (use when ``url_for(..., _external=True)`` does not match your public URL, e.g. behind a proxy).
    google_redirect_uri: str | None

    # --- Logging ---
    log_dir: str
    log_file: str
    log_max_bytes: int
    log_backup_count: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    explicit_db = _env("DATABASE_URL")
    db_backend = (_env("DB_BACKEND", "postgresql") or "postgresql").lower()
    db_host = _env("DB_HOST")
    db_port = _env("DB_PORT")
    db_name = _env("DB_NAME")
    db_user = _env("DB_USER")
    db_pass = _env("DB_PASS")
    mysql_driver = _env("MYSQL_DRIVER", "pymysql") or "pymysql"

    database_url = _build_sqlalchemy_database_url(
        explicit_url=explicit_db,
        db_backend=db_backend,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
        db_user=db_user,
        db_pass=db_pass,
        mysql_driver=mysql_driver,
    )

    checkpoint_uri = _build_checkpoint_psycopg_uri(
        explicit=_env("CHECKPOINT_DATABASE_URL"),
        db_user=db_user,
        db_pass=db_pass,
        db_host=db_host,
        db_port=db_port,
        db_name=db_name,
    )

    flask_secret = (
        _env("FLASK_SECRET_KEY")
        or _env("APP_SECRET_KEY")
        or _env("app_secret_key")
        or "dev-insecure-change-me"
    )

    enc = _env("ENCRYPTION_KEY")

    return Settings(
        database_url=database_url,
        db_backend=db_backend,
        mysql_driver=mysql_driver,
        checkpoint_postgres_uri=checkpoint_uri,
        checkpoint_pool_min_size=_env_int("CHECKPOINT_POOL_MIN_SIZE", 1),
        checkpoint_pool_max_size=_env_int("CHECKPOINT_POOL_MAX_SIZE", 4),
        checkpoint_connect_timeout=_env_int("CHECKPOINT_DB_CONNECT_TIMEOUT", 10),
        sqlalchemy_echo=_env_bool("SQLALCHEMY_ECHO", False),
        sqlalchemy_pool_pre_ping=_env_bool("SQLALCHEMY_POOL_PRE_PING", True),
        flask_secret_key=flask_secret,
        session_cookie_samesite=_env("SESSION_COOKIE_SAMESITE", "Lax") or "Lax",
        session_cookie_secure=_env_bool("SESSION_COOKIE_SECURE", False),
        session_cookie_httponly=_env_bool("SESSION_COOKIE_HTTPONLY", True),
        session_cookie_name=_env("SESSION_COOKIE_NAME", "flask_session") or "flask_session",
        encryption_key=enc,  # set ENCRYPTION_KEY before running the web app
        use_memory_redis=_env_bool("INSIGHTSDSA_USE_MEMORY_REDIS", False),
        redis_url=_env("REDIS_URL"),
        redis_host=_env("REDIS_HOST", "localhost") or "localhost",
        redis_port=_env_int("REDIS_PORT", 6379),
        redis_db=_env_int("REDIS_DB", 0),
        redis_password=_env("REDIS_PASSWORD"),
        google_client_id=_env("GOOGLE_CLIENT_ID"),
        google_client_secret=_env("GOOGLE_CLIENT_SECRET"),
        google_openid_metadata_url=_env(
            "GOOGLE_OPENID_METADATA_URL",
            "https://accounts.google.com/.well-known/openid-configuration",
        )
        or "https://accounts.google.com/.well-known/openid-configuration",
        google_redirect_uri=_env("GOOGLE_REDIRECT_URI"),
        log_dir=_env("LOG_DIR", "logs") or "logs",
        log_file=_env("LOG_FILE", "logiclens.log") or "logiclens.log",
        log_max_bytes=_env_int("LOG_MAX_BYTES", 102400),
        log_backup_count=_env_int("LOG_BACKUP_COUNT", 10),
    )


settings: Final[Settings] = get_settings()
