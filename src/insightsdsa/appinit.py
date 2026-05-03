"""
Bootstrap curriculum tables (``concepts``, ``questions``) from embedded SQL.

Run after schema exists::

    python -m insightsdsa.init_db   # create tables if needed
    python -m insightsdsa.appinit   # load concepts + questions

The INSERT statements live in :mod:`insightsdsa.curriculum_sql` (migrated from
the former ``data/*.dat`` dumps). Pass ``curriculum_sql=...`` to :func:`bootstrap`
for tests or custom seeds.
"""

from __future__ import annotations

import re
import sys
from typing import Any, Iterator

from sqlalchemy import inspect, text
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .curriculum_sql import CURRICULUM_SQL
from .db import engine, get_session
from .init_db import init_schema
from .models import Concept, Question

BOOTSTRAP_TABLES = frozenset({"concepts", "questions"})


def _values_paren_content(insert_sql: str) -> str:
    """Return the inner text of the first VALUES (...) for a single-row INSERT."""
    m = re.search(r"\bVALUES\s*\(", insert_sql, re.IGNORECASE)
    if not m:
        raise ValueError("VALUES ( not found")
    i = m.end()
    depth = 1
    in_quote = False
    n = len(insert_sql)
    while i < n:
        ch = insert_sql[i]
        if in_quote:
            if ch == "'":
                if i + 1 < n and insert_sql[i + 1] == "'":
                    i += 2
                    continue
                in_quote = False
            i += 1
            continue
        if ch == "'":
            in_quote = True
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return insert_sql[m.end() : i]
        i += 1
    raise ValueError("Unbalanced parentheses in INSERT")


def _parse_sql_value_list(inner: str) -> list[Any]:
    """Parse a PostgreSQL VALUES tuple body (no outer parens)."""
    out: list[Any] = []
    i = 0
    n = len(inner)

    def _is_ident_boundary(idx: int, kw: str) -> bool:
        if not inner.startswith(kw, idx):
            return False
        j = idx + len(kw)
        return j >= n or not (inner[j].isalnum() or inner[j] == "_")

    while i < n:
        while i < n and inner[i] in " \t\n\r":
            i += 1
        if i >= n:
            break
        if inner[i] == "'":
            i += 1
            parts: list[str] = []
            while i < n:
                if inner[i] == "'":
                    if i + 1 < n and inner[i + 1] == "'":
                        parts.append("'")
                        i += 2
                    else:
                        i += 1
                        break
                parts.append(inner[i])
                i += 1
            out.append("".join(parts))
        elif _is_ident_boundary(i, "NULL"):
            out.append(None)
            i += 4
        elif _is_ident_boundary(i, "true"):
            out.append(True)
            i += 4
        elif _is_ident_boundary(i, "false"):
            out.append(False)
            i += 5
        else:
            j = i
            while j < n and inner[j] not in ",)":
                j += 1
            token = inner[i:j].strip()
            if not token:
                raise ValueError(f"Bad VALUES token near position {i}")
            if "." in token:
                out.append(float(token))
            else:
                out.append(int(token))
            i = j
        while i < n and inner[i] in " \t\n\r":
            i += 1
        if i < n and inner[i] == ",":
            i += 1
    return out


def _table_name(insert_sql: str) -> str:
    m = re.match(
        r"INSERT\s+INTO\s+public\.(\w+)\s+VALUES",
        insert_sql.strip(),
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        m = re.match(
            r"INSERT\s+INTO\s+(\w+)\s+VALUES",
            insert_sql.strip(),
            re.IGNORECASE | re.DOTALL,
        )
    if not m:
        raise ValueError("Could not parse INSERT table name")
    return m.group(1).lower()


def iter_inserts_from_text(body: str) -> Iterator[str]:
    """Yield full ``INSERT ... ON CONFLICT DO NOTHING;`` statements (possibly multi-line)."""
    buf: list[str] = []
    for line in body.splitlines(keepends=True):
        if not line.strip() and not buf:
            continue
        buf.append(line)
        if re.search(r"ON\s+CONFLICT\s+DO\s+NOTHING\s*;\s*$", line, re.IGNORECASE):
            stmt = "".join(buf).strip()
            if stmt:
                yield stmt
            buf = []
    if buf:
        tail = "".join(buf).strip()
        if tail:
            raise ValueError(f"Unterminated SQL in curriculum text: {tail[:120]}...")


def _row_concept(vals: list[Any]) -> dict[str, Any]:
    if len(vals) != 3:
        raise ValueError(f"concepts row expected 3 fields, got {len(vals)}")
    return {"id": vals[0], "title": vals[1], "icon": vals[2]}


def _row_question(vals: list[Any]) -> dict[str, Any]:
    if len(vals) != 7:
        raise ValueError(f"questions row expected 7 fields, got {len(vals)}")
    # vals[4] historically stored is_solved on questions; persisted state lives on user_progress now.
    return {
        "id": vals[0],
        "title": vals[1],
        "difficulty": vals[2],
        "link": vals[3],
        "concept_id": vals[5],
        "description": vals[6],
    }


def _bulk_upsert_noop(session: Session, model, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    dialect = inspect(engine).dialect.name
    if dialect == "postgresql":
        stmt = pg_insert(model)
        stmt = stmt.on_conflict_do_nothing(index_elements=["id"])
        session.execute(stmt, rows)
    elif dialect in ("mysql", "mariadb"):
        stmt = mysql_insert(model).prefix_with("IGNORE")
        session.execute(stmt, rows)
    else:
        for row in rows:
            pk = row.get("id")
            if pk is not None and session.get(model, pk) is None:
                session.add(model(**row))


def _sync_postgres_sequences(session: Session) -> None:
    if inspect(engine).dialect.name != "postgresql":
        return
    for tbl in ("concepts", "questions"):
        session.execute(
            text(
                f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), "
                f"(SELECT COALESCE(MAX(id), 1) FROM {tbl}))"
            )
        )


def load_curriculum_sql(session: Session, sql_text: str) -> tuple[int, int]:
    """Parse INSERT statements; return (concept rows processed, question rows processed)."""
    c_count = 0
    q_count = 0
    concept_batch: list[dict[str, Any]] = []
    question_batch: list[dict[str, Any]] = []
    batch_size = 200

    for stmt in iter_inserts_from_text(sql_text):
        try:
            table = _table_name(stmt)
        except ValueError:
            continue
        if table not in BOOTSTRAP_TABLES:
            continue
        inner = _values_paren_content(stmt)
        vals = _parse_sql_value_list(inner)
        if table == "concepts":
            concept_batch.append(_row_concept(vals))
            if len(concept_batch) >= batch_size:
                _bulk_upsert_noop(session, Concept, concept_batch)
                c_count += len(concept_batch)
                concept_batch.clear()
        elif table == "questions":
            # Questions reference concepts FK: flush pending concepts before any question inserts.
            if concept_batch:
                _bulk_upsert_noop(session, Concept, concept_batch)
                c_count += len(concept_batch)
                concept_batch.clear()
            question_batch.append(_row_question(vals))
            if len(question_batch) >= batch_size:
                _bulk_upsert_noop(session, Question, question_batch)
                q_count += len(question_batch)
                question_batch.clear()

    if concept_batch:
        _bulk_upsert_noop(session, Concept, concept_batch)
        c_count += len(concept_batch)
    if question_batch:
        _bulk_upsert_noop(session, Question, question_batch)
        q_count += len(question_batch)

    return c_count, q_count


def bootstrap(curriculum_sql: str | None = None) -> None:
    """Create schema if missing, then load concepts/questions from embedded SQL."""
    init_schema()
    sql = curriculum_sql if curriculum_sql is not None else CURRICULUM_SQL
    if not sql.strip():
        print("Empty curriculum SQL; skipping seed.", file=sys.stderr)
        return

    total_c = 0
    total_q = 0
    with get_session() as session:
        total_c, total_q = load_curriculum_sql(session, sql)
        _sync_postgres_sequences(session)

    print(
        f"Bootstrap complete: ~{total_c} concept row(s) and ~{total_q} question row(s) "
        f"processed (conflicts skipped where applicable)."
    )


if __name__ == "__main__":
    bootstrap()
