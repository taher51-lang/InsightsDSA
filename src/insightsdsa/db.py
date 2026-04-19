import re
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from psycopg_pool import ConnectionPool

from sqlalchemy.pool import StaticPool

from .config import settings

DATABASE_URL = settings.database_url

# Postgres DSN for LangGraph checkpointing (psycopg / libpq style, not SQLAlchemy URL).
DB_URI = settings.checkpoint_postgres_uri

_engine_kwargs = {
    "echo": settings.sqlalchemy_echo,
    "pool_pre_ping": settings.sqlalchemy_pool_pre_ping,
    "future": True,
}
if DATABASE_URL.startswith("sqlite"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    _engine_kwargs["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
_checkpoint_pool = None


def get_dialect_name() -> str:
    return engine.dialect.name


def _convert_placeholders(sql: str, params):
    """Convert psycopg-style %s placeholders into SQLAlchemy named binds."""
    if not params:
        return sql, {}
    values = list(params) if isinstance(params, (list, tuple)) else [params]
    bind_params = {}
    idx = 0

    def repl(_):
        nonlocal idx
        key = f"p{idx}"
        bind_params[key] = values[idx]
        idx += 1
        return f":{key}"

    converted = re.sub(r"%s", repl, sql)
    return converted, bind_params


class DBCursor:
    def __init__(self, conn, dict_rows=False):
        self.conn = conn
        self.dict_rows = dict_rows
        self._result = None

    def execute(self, sql, params=None):
        normalized_sql = sql.strip()
        # MySQL has no INSERT ... RETURNING in common setups; emulate with last_insert_id().
        if (
            get_dialect_name() == "mysql"
            and normalized_sql.lower().startswith("insert")
            and "returning" in normalized_sql.lower()
        ):
            ret_match = re.search(
                r"\bRETURNING\s+(.+?)\s*;?\s*$",
                normalized_sql,
                flags=re.IGNORECASE | re.DOTALL,
            )
            returning_clause = ret_match.group(1).strip().rstrip(";").strip() if ret_match else ""
            table_match = re.search(
                r"INSERT\s+INTO\s+([`\"]?\w+[`\"]?)",
                normalized_sql,
                flags=re.IGNORECASE,
            )
            table_name = table_match.group(1) if table_match else None

            rewritten_sql = re.sub(
                r"\bRETURNING\b[\s\S]*$",
                "",
                normalized_sql,
                flags=re.IGNORECASE,
            ).strip()
            converted_sql, bind_params = _convert_placeholders(rewritten_sql, params)
            self._result = self.conn.execute(text(converted_sql), bind_params)
            inserted_id = self._result.lastrowid
            if not returning_clause or inserted_id is None:
                self._result = _SyntheticResult((inserted_id,))
                return self._result

            cols = [c.strip() for c in returning_clause.split(",") if c.strip()]
            if len(cols) == 1:
                self._result = _SyntheticResult((inserted_id,))
                return self._result

            if not table_name:
                self._result = _SyntheticResult((inserted_id,))
                return self._result

            tbl = table_name.strip("`\"")
            sel_sql, sel_binds = _convert_placeholders(
                f"SELECT {returning_clause} FROM {tbl} WHERE id = %s",
                (inserted_id,),
            )
            self._result = self.conn.execute(text(sel_sql), sel_binds)
            return self._result

        converted_sql, bind_params = _convert_placeholders(sql, params)
        self._result = self.conn.execute(text(converted_sql), bind_params)
        return self._result

    def fetchone(self):
        if self._result is None:
            return None
        row = self._result.fetchone()
        if row is None:
            return None
        if self.dict_rows:
            return dict(row._mapping)
        return tuple(row)

    def fetchall(self):
        if self._result is None:
            return []
        rows = self._result.fetchall()
        if self.dict_rows:
            return [dict(r._mapping) for r in rows]
        return [tuple(r) for r in rows]

    def __iter__(self):
        if self._result is None:
            return iter([])
        if self.dict_rows:
            return (dict(r._mapping) for r in self._result)
        return (tuple(r) for r in self._result)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DBConnection:
    def __init__(self):
        self.conn = None
        self.txn = None

    def __enter__(self):
        self.conn = engine.connect()
        self.txn = self.conn.begin()
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.conn.close()
        return False

    def cursor(self, row_factory=None):
        return DBCursor(self.conn, dict_rows=row_factory is not None)

    def commit(self):
        if self.txn and self.txn.is_active:
            self.txn.commit()

    def rollback(self):
        if self.txn and self.txn.is_active:
            self.txn.rollback()


def get_pool():
    """Postgres pool used by LangGraph checkpointing."""
    global _checkpoint_pool
    if get_dialect_name() != "postgresql":
        raise RuntimeError("LangGraph PostgresSaver requires a PostgreSQL DATABASE_URL.")
    if _checkpoint_pool is None:
        _checkpoint_pool = ConnectionPool(
            conninfo=DB_URI,
            min_size=settings.checkpoint_pool_min_size,
            max_size=settings.checkpoint_pool_max_size,
            kwargs={
                "autocommit": False,
                "connect_timeout": settings.checkpoint_connect_timeout,
            },
        )
    return _checkpoint_pool


class _SyntheticResult:
    def __init__(self, row):
        self._row = row
        self._consumed = False

    def fetchone(self):
        if self._consumed:
            return None
        self._consumed = True
        return self._row

    def fetchall(self):
        if self._consumed:
            return []
        self._consumed = True
        return [self._row]


def getDBConnection():
    return DBConnection()


@contextmanager
def get_session():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
