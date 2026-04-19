"""Server-side dashboard payload for API consumers (SPA)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, case, func, select

from .models import Concept, UserProgress


def build_dashboard_payload(user_id: int, s) -> dict:
    """Return the same data the legacy Jinja dashboard used, as JSON-serializable dicts."""
    concepts: list[dict] = []
    for row in s.execute(
        select(Concept.id, Concept.title, Concept.icon).order_by(Concept.id)
    ).all():
        cid = int(row[0])
        concepts.append(
            {
                "id": cid,
                "title": str(row[1] or ""),
                "icon": str(row[2] or ""),
                "questions_path": f"/questions/{cid}",
            }
        )

    _interval = func.coalesce(UserProgress.interval_days, 0)
    counts = s.execute(
        select(
            func.coalesce(
                func.sum(case((_interval <= 3, 1), else_=0)),
                0,
            ).label("short"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(_interval > 3, _interval <= 14),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("medium"),
            func.coalesce(
                func.sum(case((_interval > 14, 1), else_=0)),
                0,
            ).label("long"),
        ).where(UserProgress.user_id == user_id)
    ).mappings().first()
    short_term = counts["short"] or 0
    medium_term = counts["medium"] or 0
    long_term = counts["long"] or 0
    total_solved = short_term + medium_term + long_term
    chart_data = [short_term, medium_term, long_term]

    if total_solved == 0:
        retention_pct = 0
        days_label = "Start Now"
        days_color = "text-primary"
    else:
        rev_stats = s.execute(
            select(
                func.avg(UserProgress.ease_factor).label("avg_ease"),
                func.min(UserProgress.next_review).label("next_date"),
            ).where(
                and_(
                    UserProgress.user_id == user_id,
                    UserProgress.is_solved.is_(True),
                )
            )
        ).mappings().first()

        if rev_stats and rev_stats["avg_ease"] is not None:
            avg_ease = float(rev_stats["avg_ease"])
            next_date = rev_stats["next_date"]
        else:
            avg_ease = 2.5
            next_date = None
        retention_pct = int(min(100, (avg_ease / 3.0) * 100))
        if next_date:
            delta = (next_date - date.today()).days
            if delta < 0:
                days_label = "Overdue!"
                days_color = "text-danger"
            elif delta == 0:
                days_label = "Due Today"
                days_color = "text-warning"
            else:
                days_label = f"{delta} Days Left"
                days_color = "text-success"
        else:
            days_label = "No Reviews"
            days_color = "text-muted"

    return {
        "concepts": concepts,
        "chart_data": chart_data,
        "total_solved": total_solved,
        "retention_pct": retention_pct,
        "days_label": days_label,
        "days_color": days_color,
        "memory_path": "/memory",
    }
