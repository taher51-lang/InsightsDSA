"""
Create a deterministic local account for QA and Playwright E2E.

Default credentials (override with env vars if needed)::

    INSIGHTSDSA_E2E_USERNAME   default: local_e2e_user
    INSIGHTSDSA_E2E_PASSWORD   default: LocalE2e_Pass1
    INSIGHTSDSA_E2E_EMAIL      default: local_e2e_user@example.invalid
    INSIGHTSDSA_E2E_NAME       default: Local E2E User
"""

from __future__ import annotations

import os

from sqlalchemy import select
from werkzeug.security import generate_password_hash

from .db import get_session
from .models import Concept, Question, User

E2E_USERNAME = os.environ.get("INSIGHTSDSA_E2E_USERNAME", "local_e2e_user")
E2E_PASSWORD = os.environ.get("INSIGHTSDSA_E2E_PASSWORD", "LocalE2e_Pass1")
E2E_EMAIL = os.environ.get("INSIGHTSDSA_E2E_EMAIL", "local_e2e_user@example.invalid")
E2E_NAME = os.environ.get("INSIGHTSDSA_E2E_NAME", "Local E2E User")


def ensure_minimal_curriculum() -> None:
    """Ensure at least one concept and question exist (for /questions/1 and /question/1)."""
    with get_session() as s:
        if s.get(Concept, 1) is None:
            s.add(Concept(id=1, title="E2E Concept", icon="📌"))
        if s.get(Question, 1) is None:
            s.add(
                Question(
                    id=1,
                    title="E2E Sample Question",
                    difficulty="Easy",
                    link=None,
                    concept_id=1,
                    description="Sample description for UI tests.",
                )
            )


def ensure_local_e2e_user() -> int:
    """Insert or reuse the E2E user; return user id."""
    with get_session() as s:
        uid = s.scalar(select(User.id).where(User.username == E2E_USERNAME))
        if uid is not None:
            return int(uid)
        u = User(
            username=E2E_USERNAME,
            userpassword=generate_password_hash(E2E_PASSWORD),
            name=E2E_NAME,
            email=E2E_EMAIL,
        )
        s.add(u)
        s.flush()
        return int(u.id)


def main() -> None:
    from .init_db import init_schema

    init_schema()
    ensure_minimal_curriculum()
    uid = ensure_local_e2e_user()
    print(
        f"E2E user ready: username={E2E_USERNAME!r} password={E2E_PASSWORD!r} id={uid}\n"
        f"Minimal curriculum: concept_id=1, question_id=1"
    )


if __name__ == "__main__":
    main()
