"""Background worker — processes AI analysis tasks from the Redis queue."""

import json
from .analyst_bot import Analyst
from .app import Redis as r, decrypt_key, fetch_session_transcript
from .db import get_session
from .models import ActivityLog, Question
from sqlalchemy import select, update

while True:
    _, task_json = r.brpop("ai_analysis_queue")
    task = json.loads(task_json)
    user_id = task['user_id']
    q_id = task['q_id']
    api_key = None
    ai_score = None
    clarity = None
    try:
        transcript = fetch_session_transcript(user_id, q_id)
        encrypted_key = r.hget(f"user:{user_id}", "api_key")
        if encrypted_key:
            api_key = decrypt_key(encrypted_key)
        if transcript and api_key:
            analyst = Analyst(api_key, task['provider'])
            with get_session() as s:
                q_details = s.scalar(select(Question.description).where(Question.id == q_id))
                if not q_details:
                    print("question details not found")
                else:
                    analysis = analyst.get_response(q_details, transcript)
                    if analysis:
                        ai_score = analysis.mastery_score
                        clarity = analysis.clarity_score
                        print(analysis.reasoning)
                        s.execute(update(ActivityLog).where(ActivityLog.id == task['activity_id']).values(
                            ai_bifurcated_score=ai_score, clarity_of_thought=clarity))
            print(f"✨ Row {task['activity_id']} enriched with AI scores!")
    except Exception as e:
        print(f"Worker Error: {e}")
