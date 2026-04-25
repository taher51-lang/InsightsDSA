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


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of configuration."""

    # --- Database ---
    database_url: str
    checkpoint_postgres_uri: str

    # --- Flask ---
    flask_secret_key: str
    session_cookie_samesite: str
    session_cookie_secure: bool
    session_cookie_httponly: bool
    session_cookie_name: str

    # --- Security ---
    encryption_key: str | None

    # --- Redis ---
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
    google_redirect_uri: str | None

    # --- Logging ---
    log_dir: str
    log_file: str
    log_max_bytes: int
    log_backup_count: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    db_host = _env("DB_HOST", "localhost")
    db_port = _env("DB_PORT", "5432")
    db_name = _env("DB_NAME")
    db_user = _env("DB_USER")
    db_pass = _env("DB_PASS")

    explicit_db = _env("DATABASE_URL")
    if explicit_db:
        database_url = explicit_db
    else:
        database_url = f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    explicit_cp = _env("CHECKPOINT_DATABASE_URL")
    if explicit_cp:
        checkpoint_uri = explicit_cp
    else:
        checkpoint_uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"

    flask_secret = (
        _env("FLASK_SECRET_KEY")
        or _env("APP_SECRET_KEY")
        or _env("app_secret_key")
        or "dev-insecure-change-me"
    )

    return Settings(
        database_url=database_url,
        checkpoint_postgres_uri=checkpoint_uri,
        flask_secret_key=flask_secret,
        session_cookie_samesite=_env("SESSION_COOKIE_SAMESITE", "Lax") or "Lax",
        session_cookie_secure=_env_bool("SESSION_COOKIE_SECURE", False),
        session_cookie_httponly=_env_bool("SESSION_COOKIE_HTTPONLY", True),
        session_cookie_name=_env("SESSION_COOKIE_NAME", "flask_session") or "flask_session",
        encryption_key=_env("ENCRYPTION_KEY"),
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
        ) or "https://accounts.google.com/.well-known/openid-configuration",
        google_redirect_uri=_env("GOOGLE_REDIRECT_URI"),
        log_dir=_env("LOG_DIR", "logs") or "logs",
        log_file=_env("LOG_FILE", "logiclens.log") or "logiclens.log",
        log_max_bytes=_env_int("LOG_MAX_BYTES", 102400),
        log_backup_count=_env_int("LOG_BACKUP_COUNT", 10),
    )


settings: Final[Settings] = get_settings()
