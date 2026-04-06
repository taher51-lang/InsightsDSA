import redis
import json
from app import Analyst, fetch_session_transcript,Redis as r,decrypt_key
from db import getDBConnection,pool
while True:
    _, task_json = r.brpop("ai_analysis_queue")
    task = json.loads(task_json)
    user_id = task['user_id']
    q_id = task['q_id']
    api_key = None
    ai_score=None
    clarity=None
    # 1. Grab the REAL API Key from Redis (where we vaulted it earlier)
    # 2. Replicate your log_to_activity logic here
    try:
        # Fetch question details and transcript...
        transcript = fetch_session_transcript(user_id, q_id)
        encrypted_key = r.hget(f"user:{user_id}","api_key" )
        if encrypted_key:
            api_key = decrypt_key(encrypted_key)
        if transcript and api_key:
            analyst = Analyst(api_key, task['provider'])
            with getDBConnection() as con:
                cur = con.cursor()
                cur.execute("SELECT description FROM questions WHERE id = %s", (q_id,))
                row = cur.fetchone()
                if not row:
                    print("question details not found")
                else:
                    q_details = row[0]
                    analysis = analyst.get_response(q_details, transcript)
            
            # 3. NOW update the database with the AI's findings
            
                if analysis:
                    ai_score = analysis.mastery_score
                    clarity = analysis.clarity_score
                    print(analysis.reasoning)
        # 3. Use UPDATE instead of INSERT
        # con = getDBConnection()
        # cur = con.cursor()
                    cur.execute("""
                        UPDATE activity_log 
                    SET ai_bifurcated_score = %s, 
                    clarity_of_thought = %s 
                    WHERE id = %s
                """, (ai_score, clarity, task['activity_id']))
        
            con.commit()
            print(f"✨ Row {task['activity_id']} enriched with AI scores!")
    except Exception as e:
        print(f"Worker Error: {e}")
