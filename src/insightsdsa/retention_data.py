"""Retention / memory review payload for SPA."""

from __future__ import annotations

from sqlalchemy import and_, func, select

from .models import Concept, Question, UserProgress


def build_retention_payload(user_id: int, s) -> dict:
    review_stmt = (
        select(
            Question.id.label("question_id"),
            Question.title.label("question_title"),
            Question.link.label("question_link"),
            Concept.title.label("concept_title"),
            UserProgress.interval_days.label("days_interval"),
        )
        .select_from(Question)
        .join(UserProgress, Question.id == UserProgress.question_id)
        .join(Concept, Question.concept_id == Concept.id)
        .where(
            and_(
                UserProgress.user_id == user_id,
                UserProgress.next_review <= func.current_date(),
            )
        )
        .order_by(UserProgress.next_review.asc())
    )
    queue = [dict(r) for r in s.execute(review_stmt).mappings().all()]

    stats_stmt = (
        select(
            Concept.title.label("concept_title"),
            func.count(UserProgress.question_id).label("solved_count"),
            func.coalesce(func.avg(UserProgress.ease_factor), 0).label("avg_ease"),
        )
        .select_from(Concept)
        .outerjoin(Question, Concept.id == Question.concept_id)
        .outerjoin(
            UserProgress,
            and_(
                Question.id == UserProgress.question_id,
                UserProgress.user_id == user_id,
            ),
        )
        .group_by(Concept.id, Concept.title)
    )
    stats_raw = s.execute(stats_stmt).mappings().all()
    stats = []
    for row in stats_raw:
        name = row["concept_title"]
        solved = row["solved_count"]
        ease = float(row["avg_ease"])
        if solved == 0:
            signal = 0
        elif ease >= 2.6:
            signal = 4
        elif ease >= 2.1:
            signal = 3
        elif ease >= 1.5:
            signal = 2
        else:
            signal = 1
        stats.append({"name": name, "solved": solved, "signal": signal})
    return {"queue": queue, "stats": stats}
