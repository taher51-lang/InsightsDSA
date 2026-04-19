import logging

from sqlalchemy import inspect, text
from sqlalchemy.exc import ProgrammingError

from .db import engine
from .models import Base

logger = logging.getLogger(__name__)


def ensure_user_progress_sm2_columns() -> None:
    """Add spaced-repetition columns to ``user_progress`` if missing.

    ``Base.metadata.create_all()`` does not alter existing tables, so legacy
    databases can miss columns that newer code expects (e.g. dashboard queries).

    Uses explicit ``public`` schema on PostgreSQL and tolerates duplicate-column
    errors from races or partial past migrations.
    """
    insp = inspect(engine)
    dialect = engine.dialect.name

    if dialect == "postgresql":
        if not insp.has_table("user_progress", schema="public"):
            return
        existing = {
            c["name"].lower()
            for c in insp.get_columns("user_progress", schema="public")
        }
        table_sql = "public.user_progress"
    else:
        if not insp.has_table("user_progress"):
            return
        existing = {c["name"].lower() for c in insp.get_columns("user_progress")}
        table_sql = "user_progress"

    def add_column(name: str, ddl_type: str) -> None:
        if name.lower() in existing:
            return
        stmt = text(f"ALTER TABLE {table_sql} ADD COLUMN {name} {ddl_type}")
        try:
            with engine.begin() as conn:
                conn.execute(stmt)
        except ProgrammingError as exc:
            msg = str(exc).lower()
            if "already exists" in msg or "duplicate" in msg:
                logger.info("user_progress.%s: already present, skipping", name)
            else:
                raise
        else:
            logger.info("user_progress: added column %s", name)
        existing.add(name.lower())

    add_column("interval_days", "INTEGER")
    if dialect == "postgresql":
        add_column("ease_factor", "DOUBLE PRECISION")
    elif dialect in ("mysql", "mariadb"):
        add_column("ease_factor", "FLOAT")
    else:
        add_column("ease_factor", "REAL")
    add_column("repetitions", "INTEGER")
    add_column("next_review", "DATE")


def init_schema():
    Base.metadata.create_all(bind=engine)
    ensure_user_progress_sm2_columns()


if __name__ == "__main__":
    init_schema()
    print("Schema created/verified successfully.")
