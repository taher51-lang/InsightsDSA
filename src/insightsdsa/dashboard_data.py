"""Build the JSON payload that the dashboard API endpoint returns.

This extracts the logic that was previously inline in the Jinja render_template() call.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from .models import Concept, Question, UserProgress


def build_dashboard_payload(user_id: int, s: Session) -> dict:
    # 1. Fetch Concepts
    concepts_rows = s.execute(select(Concept).order_by(Concept.id)).scalars().all()
    concepts = [
        {"id": c.id, "title": c.title, "icon": c.icon or ""}
        for c in concepts_rows
    ]

    # 2. Retention memory counts (short / medium / long term)
    counts = s.execute(
        select(
            func.count().filter(UserProgress.interval_days <= 3).label("short"),
            func.count().filter(
                and_(UserProgress.interval_days > 3, UserProgress.interval_days <= 14)
            ).label("medium"),
            func.count().filter(UserProgress.interval_days > 14).label("long"),
        ).where(UserProgress.user_id == user_id)
    ).first()

    short_term = counts.short or 0
    medium_term = counts.medium or 0
    long_term = counts.long or 0
    total_solved = short_term + medium_term + long_term
    chart_data = [short_term, medium_term, long_term]

    # 3. Retention logic
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
        ).first()

        avg_ease = float(rev_stats.avg_ease) if rev_stats and rev_stats.avg_ease else 2.5
        next_date = rev_stats.next_date if rev_stats else None

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
    }
