"""Redis worker: consume ``ai_analysis_queue`` and enrich ``ActivityLog`` rows."""

from __future__ import annotations

import json
import logging
import traceback

from sqlalchemy import select, update

from .analyst_bot import Analyst
from .app import (
    Redis as r,
    StoredApiKeyDecryptError,
    decrypt_key,
    fetch_session_transcript,
)

_log = logging.getLogger(__name__)
from .db import SessionLocal
from .models import ActivityLog, Question


def run_once() -> None:
    """Block on one queue item and process it (same behavior as the original script loop body)."""
    _, task_json = r.brpop("ai_analysis_queue")
    task = json.loads(task_json)
    user_id = task["user_id"]
    q_id = task["q_id"]
    api_key = None
    ai_score = None
    clarity = None
    try:
        transcript = fetch_session_transcript(
            user_id, q_id, task.get("thread_id")
        )
        encrypted_key = r.hget(f"user:{user_id}", "api_key")
        if encrypted_key:
            try:
                api_key = decrypt_key(encrypted_key)
            except StoredApiKeyDecryptError:
                _log.warning(
                    "Could not decrypt stored API key for user_id=%s (wrong ENCRYPTION_KEY or corrupt data)",
                    user_id,
                )
                api_key = None
        if transcript and api_key:
            analyst = Analyst(api_key, task["provider"])
            s = SessionLocal()
            try:
                analysis = None
                q_details = s.scalar(
                    select(Question.description).where(Question.id == q_id)
                )
                if not q_details:
                    print("question details not found")
                else:
                    analysis = analyst.get_response(q_details, transcript)
                    if analysis:
                        ai_score = analysis.mastery_score
                        clarity = analysis.clarity_score
                        print(analysis.reasoning)
                s.execute(
                    update(ActivityLog)
                    .where(ActivityLog.id == task["activity_id"])
                    .values(
                        ai_bifurcated_score=ai_score,
                        clarity_of_thought=clarity,
                    )
                )
                s.commit()
                print(f"✨ Row {task['activity_id']} enriched with AI scores!")
            finally:
                s.close()
    except Exception:
        print("Worker Error:")
        traceback.print_exc()


def main() -> None:
    while True:
        run_once()


if __name__ == "__main__":
    main()
