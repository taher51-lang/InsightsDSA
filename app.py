from flask import Flask, render_template, request, jsonify,session,redirect,url_for,flash
from aiBotBackend import chatbot
from datetime import date, timedelta 
from werkzeug.security import generate_password_hash, check_password_hash
from psycopg.rows import dict_row
from psycopg import errors
from authlib.integrations.flask_client import OAuth
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
from langchain_core.messages import AIMessage,HumanMessage
import os
from datetime import datetime
import traceback
from psycopg_pool import ConnectionPool 
import logging
from logging.handlers import RotatingFileHandler 
import json
from werkzeug.middleware.proxy_fix import ProxyFix
from analystBot import Analyst,InsightCoach
from cryptography.fernet import Fernet
import redis
from db import pool , getDBConnection
MASTER_KEY = os.getenv("ENCRYPTION_KEY")
Redis = redis.Redis(
    host=os.getenv('REDIS_HOST', 'localhost'),
    port=int(os.getenv('REDIS_PORT', 6379)),
    password=None,
    # ssl=True,             # 🔒 Add this for encrypted transit
    ssl_cert_reqs=None,   # Often required for cloud providers
    decode_responses=True
)
cipher_suite = Fernet(MASTER_KEY)
load_dotenv()
app = Flask(__name__)
app.secret_key=os.getenv("app_secret_key")

# Setup Production Logging
if not os.path.exists('logs'):
    os.mkdir('logs')
file_handler = RotatingFileHandler('logs/logiclens.log', maxBytes=102400, backupCount=10)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('LogicLens startup')

@app.after_request
def add_header(response):
    """
    Tells the browser: 'Do not save a photo of this page. 
    Ask the server for a fresh copy every single time.'
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
csrf = CSRFProtect(app) # This locks down all your POST routes
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
def sm2_algorithm(quality, current_interval, current_ease, repetitions):
    """
    Inputs:
        quality: 0 (Forgot), 3 (Hard), 4 (Good), 5 (Easy)
        current_interval: Days since last review
        current_ease: Difficulty multiplier (default 2.5)
        repetitions: How many times successfully reviewed in a row
    
    Returns:
        (new_interval, new_ease, new_repetitions, next_review_date)
    """
    # 1. HANDLE "FORGOT" (Reset Logic)
    if quality < 3:
        new_reps = 0
        new_interval = 1  # Reset to 1 day (Review tomorrow)
        new_ease = current_ease # Keep ease factor same (or could decrease it)
        
    # 2. HANDLE SUCCESS (Growth Logic)
    else:
        new_reps = repetitions + 1
        
        # Standard SM-2 Intervals
        if new_reps == 1:
            new_interval = 1
        elif new_reps == 2:
            new_interval = 6
        else:
            # The Magic Formula: Previous Interval * Ease Factor
            new_interval = int(current_interval * current_ease)

        # Update Ease Factor (Math to adjust difficulty)
        # If user found it hard, Ease Factor drops. If easy, it rises.
        new_ease = current_ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        
        # Cap the Ease Factor (Don't let it get too low, or intervals will never grow)
        if new_ease < 1.3:
            new_ease = 1.3

    # 3. CALCULATE DATE
    next_review_date = date.today() + timedelta(days=new_interval)

    return new_interval, new_ease, new_reps, next_review_date
@app.route("/")
def homePage():
    return render_template("landing.html")
@app.route("/loginpage")
def LoginPage():
    return render_template("regAndLogin.html")

# def getDBConnection():
#     """
#     Acquires a connection from the valet (the pool).
#     When you call .close() on this, it goes back to the pool 
#     instead of being destroyed.
#     """
#     return pool.connection()
def encrypt_key(plain_text):
    return cipher_suite.encrypt(plain_text.encode()).decode()
def decrypt_key(encrypted_text):
    return cipher_suite.decrypt(encrypted_text.encode()).decode()
# Configure Google OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

# 1. THE TRIGGER: Send user to Google
@app.route('/login/google')
def login_google():
    # This must match the URI you added in Google Console exactly
    redirect_uri = url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

# 2. THE RECEIVER: Catch the data coming back
@app.route('/login/callback')
def google_callback():
    token = google.authorize_access_token()
    user_info = token.get('userinfo')
    email = user_info['email']
    g_id = user_info['sub'] # This is the permanent unique ID from Google
    full_name = user_info.get('name', 'Explorer')
    print(full_name)
    first_name = full_name.split()[0]
    pic = user_info['picture']

    with getDBConnection() as con:
        with con.cursor() as cur:
    # 1. Check if user already exists (by email)
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cur.fetchone()

            if user:
        # 2. LINKING: Update existing user
                cur.execute("""
            UPDATE users 
            SET google_id = %s, profile_pic = %s 
            WHERE email = %s
        """, (g_id, pic, email))
                user_id = user[0] 
            else:
        # 3. REGISTRATION: Added 'RETURNING id' to the SQL string
                cur.execute("""
            INSERT INTO users (username, name, email, google_id, profile_pic) 
            VALUES (%s, %s, %s, %s, %s) 
            RETURNING id
                """, (first_name, full_name, email, g_id, pic))
        
        # Now fetchone() actually has the new ID to grab!
                result = cur.fetchone()
                user_id = result[0]

    # 4. Commit and set session
        con.commit()
        session["user_id"] = user_id
        session["user_id"] = user_id
    # Set session data for the UI
        session['user_email'] = email
        session['user_name'] = first_name
        session['profile_pic'] = pic
    return redirect(url_for('dashboard'))
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    userpass = data.get("userpass")
    if not username or not userpass:
        return jsonify({"error": "Missing credentials"}), 400
    # Initialize these as None so the 'finally' block doesn't crash if connection fails early
    con = None
    cur = None
    try:
        with getDBConnection() as con:
            # con = getDBConnection()
            with con.cursor(row_factory=dict_row) as cur:
                cur.execute("SELECT id, username, name, userpassword ,google_id FROM users WHERE username = %s", (username,))
                result = cur.fetchone()
                if not result:
                    return jsonify({"error": "Invalid Credentials"}), 401
                if result['userpassword'] is None and result['google_id'] is not None:
                    return jsonify({
                    "error": "This account is linked with Google. Please use the 'Continue with Google' button."
                }), 403
            # If no user is found with that username
                \
                current_db_password = result['userpassword']
                is_valid = False
                needs_upgrade = False
            # 2. THE BILINGUAL CHECK
                if current_db_password.startswith('scrypt:') or current_db_password.startswith('pbkdf2:'):
                # It's a secure hash!
                    is_valid = check_password_hash(current_db_password, userpass)
                else:
                # It's an old plaintext demo password!
                    is_valid = (current_db_password == userpass)
                    if is_valid:
                        needs_upgrade = True # Flag them for an upgrade!
            # If the password didn't match either way, kick them out
                if not is_valid:
                    return jsonify({"error": "Invalid Credentials"}), 401
            # 3. AUTO-UPGRADE OLD ACCOUNTS (The Self-Cleaning Magic)
                if needs_upgrade:
                    new_hashed_password = generate_password_hash(userpass)
                    cur.execute("UPDATE users SET userpassword = %s WHERE id = %s", (new_hashed_password, result['id']))
                    con.commit()
                    print(f"Security Upgrade Complete: Hashed password for user '{username}'")
            # 4. Set Session and Log Them In
                session['user_id'] = result['id'] 
                session['user_name'] = result['username']  
                if result["name"]:  
                    return jsonify({"message": "Login successful", "name": result['name']}), 200
                else:
                    return jsonify({"message": "Login successful"}), 200



    except Exception as e:
        print("Database Error in login:", e)
        return jsonify({"error": "Server error"}), 500
        
   

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    userpass = data.get("userpass")
    useremail = data.get("email")
    name = data.get("name")
    print("Debugged")
    # 1. HASH THE PASSWORD! (This turns "password123" into "scrypt:32768:8:1$...")
    hashed_password = generate_password_hash(userpass)
    print("Heloo")
    try:
        with getDBConnection() as con:
            with con.cursor(row_factory=dict_row) as cur:
        # 2. SAVE THE HASHED PASSWORD to the database, not the raw one
                cur.execute('''
            INSERT INTO users (name, username, email, userpassword)
            VALUES (%s, %s, %s, %s)
            RETURNING id, username; 
                ''', (name, username, useremail, hashed_password)) # <-- Swapped userpass for hashed_password
    
                new_user = cur.fetchone() 
    
                con.commit() 

                if new_user:
                    session['user_id'] = new_user['id']
                    session['username'] = new_user['username']
                    return jsonify({"message": "Registration Successful!"}), 201

    except errors.UniqueViolation:
        # This catches BOTH duplicate Email and duplicate Username
            return jsonify({"error": "Username or Email already exists!"}), 409 

    except Exception as e:
            print("Database Error:", e)
            return jsonify({"error": "Server error. Please try again."}), 500
@app.route("/dashboard")
def dashboard():
    user_id = session.get('user_id')
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    with getDBConnection() as con:
        with con.cursor(row_factory=dict_row) as cur:    
    # 1. Fetch Concepts
            cur.execute("SELECT * FROM concepts") 
            concepts = cur.fetchall()

            cur.execute("""
        SELECT 
            COUNT(*) FILTER (WHERE "interval" <= 3) as short,
            COUNT(*) FILTER (WHERE "interval" > 3 AND "interval" <= 14) as medium,
            COUNT(*) FILTER (WHERE "interval" > 14) as long
        FROM user_progress 
        WHERE user_id = %s
            """, (user_id,))
    
            counts = cur.fetchone()
            short_term = counts['short']
            medium_term = counts['medium']
            long_term = counts['long']
            total_solved = short_term + medium_term + long_term
            chart_data = [short_term, medium_term, long_term]

    # 2. RETENTION LOGIC 
            if total_solved == 0:
        # NEWBIE STATE: Force retention to 0 if no data
                retention_pct = 0
                days_label = "Start Now"
                days_color = "text-primary"
            else:
        # EXPERT STATE: Calculate real stats
                cur.execute("""
                SELECT 
                    AVG(ease_factor) as avg_ease, 
                    MIN(next_review) as next_date
                FROM user_progress 
                WHERE user_id = %s AND is_solved = TRUE
            """, (user_id,))
                rev_stats = cur.fetchone()

                if rev_stats and rev_stats['avg_ease']:
                    avg_ease = float(rev_stats['avg_ease'])
                    next_date = rev_stats['next_date']
                else:
                    avg_ease = 2.5
                    next_date = None
        # Calculate Percenta
                retention_pct = int(min(100, (avg_ease / 3.0) * 100))
        # Calculate Days Label
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
    # cur.close()
    # con.close()
    # print(f"DEBUG: Total Solved: {total_solved}, Retention: {retention_pct}%")
            return render_template('dashboard.html', 
                           name=session.get("user_name"),
                           retention_pct=retention_pct,
                           days_label=days_label,
                           days_color=days_color,
                           concepts=concepts,
                           chart_data=chart_data,
                           total_solved=total_solved 
                           )
def getStreak(user_id,con,cur):
    cur.execute("""
        SELECT COUNT(*) as solved_count 
        FROM user_progress 
        WHERE user_id = %s AND is_solved = TRUE
    """, (user_id,))
    total_result = cur.fetchone()
    total_solved = total_result['solved_count'] if total_result else 0
    
    # 2. Get Streak (THE FIX)
    cur.execute("""
        SELECT DISTINCT DATE(solved_at) as activity_date
        FROM user_progress
        WHERE user_id = %s AND solved_at IS NOT NULL
        ORDER BY activity_date DESC
    """, (user_id,))
    
    # Converting list of dicts to a Set of date objects for easy lookup
    rows = cur.fetchall()
    active_dates = {row['activity_date'] for row in rows}
    

    # PYTHON STREAK ALGORITHM 
    streak = 0
    today = date.today()
    
    # Checking if the streak is alive (Active Today OR Yesterday)
    if today in active_dates:
        streak = 1
        check_date = today - timedelta(days=1) # Start checking from Yesterday
    elif (today - timedelta(days=1)) in active_dates:
        streak = 1
        check_date = today - timedelta(days=2) # Start checking from Day Before Yesterday
    else:
        streak = 0 # Streak is broken
        check_date = None

    # Count backwards as long as there is no gap
    while check_date and check_date in active_dates:
        streak += 1
        check_date -= timedelta(days=1)
    return total_solved,streak

@app.route("/api/user_stats")

def get_user_stats():
    user_id = session.get('user_id')
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    with getDBConnection() as con:
            with con.cursor(row_factory=dict_row) as cur:
            # 1. Get Total Solved 
                total_solved,streak=getStreak(user_id,con,cur)
            
                return jsonify({
                "total_solved": total_solved,
                "streak": streak
        })

@app.route("/questions/<int:concept_id>")
def questions_page(concept_id):
    user_id = session.get('user_id')
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    # This just renders the blank page with the concept_id passed to the template
    return render_template("questions.html", concept_id=concept_id)
@app.route("/api/get_questions/<int:concept_id>")
def get_questions_api(concept_id):
    user_id = session.get('user_id')
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    with getDBConnection() as con:
            with con.cursor(row_factory=dict_row) as cur:
                query = """
                SELECT q.id, q.title, q.difficulty, q.link,
                    CASE WHEN up.question_id IS NOT NULL THEN TRUE ELSE FALSE END as is_solved
                FROM questions q
                LEFT JOIN user_progress up ON q.id = up.question_id AND up.user_id = %s
                WHERE q.concept_id = %s
            """
                cur.execute(query, (user_id, concept_id))

                questions = cur.fetchall()
                difficulty_map = {"Easy": 1, "Medium": 2, "Hard": 3}
                questions.sort(key=lambda x: difficulty_map.get(x['difficulty'], 4))
            
    return jsonify(questions)

@app.route("/api/get_question_details/<int:q_id>")
def get_question_details(q_id):
    user_id = session.get("user_id")
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    with getDBConnection() as con:
            with con.cursor(row_factory=dict_row) as cur:
                try:
                    query = """
                        SELECT q.id, q.title, q.description, q.difficulty, q.link,
                        CASE WHEN up.question_id IS NOT NULL THEN TRUE ELSE FALSE END as is_solved
                    FROM questions q
                    LEFT JOIN user_progress up ON q.id = up.question_id AND up.user_id = %s
                    WHERE q.id = %s
                """
                    cur.execute(query, (user_id, q_id))
                    data = cur.fetchone()
                    print(data)
                    if not data:
                        return jsonify({"error": "Question not found"}), 404   
                    return jsonify(data)
                
                except Exception as e:
                        return jsonify({"error": "Server error"}), 500

# def log_to_activity(user_id, q_id, action_type, confidence, time_seconds,api_key,provider):
#     """The Single Source of Truth for Dojo Data."""
#     # 1. Background AI Analysis (Silent)
#     ai_score = None
#     clarity=None
    
#     try:
#         # 1. Fetch Question Details (for the AI context)
#         # Assuming you have a function to get title/desc from DB
#         con = getDBConnection()        
#         cur = con.cursor()
#         cur.execute("SELECT description FROM questions WHERE id = %s", (q_id,))
#         row = cur.fetchone()
#         if not row:
#             print("question details not found")
#         else:
#             q_details = row[0]
#         # 2. Fetch Chat History (Transcript)
#         # Using the retriever we built earlier
#         print("Good")
#         transcript = fetch_session_transcript(user_id, q_id)
        
#         # 3. Only analyze if the user actually engaged (Filter)
#         if transcript and len(transcript) >= 4 and api_key:
#             analyst = Analyst(Redis.hget(f"user:{session["user_id"]}", "api_key"), provider)
#             # Invoke the logic
#             analysis = analyst.get_response(q_details, transcript)
#             print("HOOOOOO")
#             print(analysis)
#             if analysis:
#                 ai_score = analysis.mastery_score
#                 clarity = analysis.clarity_score
#         con = getDBConnection()
#         cur = con.cursor()
#         cur.execute("""
#             INSERT INTO activity_log 
#             (user_id, question_id, action, confidence_level, time_spent_seconds, ai_bifurcated_score,clarity_of_thought) 
#             VALUES (%s, %s, %s, %s, %s, %s,%s)
#         """, (user_id, q_id, action_type, confidence, time_seconds, ai_score,clarity))
#         # con.commit()
#     except Exception as e:
#         print(f"activity table Log Error: {e}")

@app.route("/api/toggle_solve", methods=["POST"])
def toggle_solve():
    user_id = session.get("user_id")
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
        
    data = request.get_json()
    q_id = data.get("question_id")
    confidence = data.get("confidence")
    time_spent = data.get("time_spent")
    # api_key = data.get("user_api_key")
    provider = data.get("provider")
    with getDBConnection() as con:
            with con.cursor() as cur:
                try:
                # 1. Check if it exists
                    cur.execute("SELECT 1 FROM user_progress WHERE user_id = %s AND question_id = %s", (user_id, q_id))
                    exists = cur.fetchone()
                    if exists:
                    # OPTION A: Reset (Delete row)
                        cur.execute("DELETE FROM user_progress WHERE user_id = %s AND question_id = %s", (user_id, q_id))
                    # NEW: Remove it from the activity log so they can't farm consistency points by toggling!
                        cur.execute("DELETE FROM activity_log WHERE user_id = %s AND question_id = %s AND action = 'solved'", (user_id, q_id))
                    
                        action = "reset"
                    
                    else:
                    # OPTION B: First Solve (Initialize SRS Defaults)
                        tomorrow = date.today() + timedelta(days=1)

                    # Note the double quotes around "interval" for Postgres!
                        query = """
                        INSERT INTO user_progress 
                        (user_id, question_id, solved_at, "interval", ease_factor, repetitions, next_review, is_solved) 
                        VALUES (%s, %s, NOW(), 1, 2.5, 1, %s, TRUE)
                    """
                        action="solved"
                        cur.execute(query, (user_id, q_id, tomorrow))
                    # NEW: Drop the 'solved' event into the Activity Log!
                    # log_to_activity(user_id,q_id,action,confidence,time_spent,api_key,provider)
                        cur.execute("""
                    INSERT INTO activity_log 
                    (user_id, question_id, action, confidence_level, time_spent_seconds) 
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """, (user_id, q_id, 'solved', confidence, time_spent))
                        activity_id = cur.fetchone()[0] # This is the unique ID for this specific solve
                    # 2. Tell the worker: "Hey, go find row ID X and add the AI scores to it"
                        task_payload = {
                    "activity_id": activity_id, # The key to the update
                    "user_id": user_id,
                    "q_id": q_id,
                    "provider": provider
                    }
                        Redis.lpush("ai_analysis_queue", json.dumps(task_payload))
                    con.commit() 
                    return jsonify({"status": "success", "action": action})
                except Exception as e:
                    print(f"Error: Server error") # Good for debugging
                    return jsonify({"error": str(e)}), 500

@app.route("/api/ask_ai", methods=["POST"])
def ask_AI():
    user_id = session.get("user_id")
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    with getDBConnection() as con:
        with con.cursor(row_factory=dict_row) as cur:
            data = request.get_json()
        # 1. Grab the variables from the frontend request
            query = data.get('query')
            question_id = data.get('question_id')
            thread_id = data.get('thread_id')
            safe_thread_id = f"user_{user_id}_{thread_id}"

            provider = data.get('provider')
        # user_api_key = data.get('api_key')
        # 2. Get user_id from Flask session! 
            query_db = "select description from questions where id = %s "
            cur.execute(query_db, (question_id,))
            row = cur.fetchone()
    question_description = row['description'] if row else "No description Provided"
            # Optional: If you haven't built the login system yet, uncomment the line below to test it safely:
            # user_id = 1 
    config = {"configurable": {"thread_id": safe_thread_id}}
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401
    try:
        # 3. Trigger LangGraph
        encrypted_key = Redis.hget(f"user:{session['user_id']}", "api_key")
        if not encrypted_key:
            print(True)
            return jsonify({
            "error": "API Key Required",
            "message": "Please go to Settings and add your API key first."
    }),401
        response = chatbot.invoke({
            'messages': [HumanMessage(content=query)],
            'question': question_description,
            'user_api_key': decrypt_key(encrypted_key), 
            'provider': provider          
        }, config=config)
        
        # 4. Extract the clean text response
        ai_response = response['messages'][-1].content

        # 5. Database Logging (Nested Try/Except)
        with getDBConnection() as con:
            with con.cursor(row_factory=dict_row) as cur:
                try:
                # Log the User's message
                    cur.execute("""
                    INSERT INTO chat_messages (user_id, question_id, thread_id, role, content)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, question_id, thread_id, 'user', query))

                # Log the AI's response
                    cur.execute("""
                    INSERT INTO chat_messages (user_id, question_id, thread_id, role, content)
                    VALUES (%s, %s, %s, %s, %s)
                """, (user_id, question_id, thread_id, 'assistant', ai_response))
                    con.commit() # Save the changes!
                except Exception as db_err:
                    print("Failed to save messages to DB:", db_err)    
        # 6. Return the answer to the frontend
            return jsonify({"answer": ai_response})
    except Exception as e:
        traceback.print_exc()
        error_msg = str(e).lower()
        # 1. THE "DEAD END": Quota/Billing Exhausted
        if "insufficient_quota" in error_msg or "billing" in error_msg or "quota_limit" in error_msg:
            return jsonify({
                "code": "API_EXHAUSTED",
                "error": "Your API provider quota is exhausted."
            }), 402 # 402 triggers the 'Reset Keys' Modal

        # 2. THE "SPEED BUMP": Rate Limiting
        elif "429" in error_msg or "rate_limit" in error_msg or "too many requests" in error_msg:
            return jsonify({
                "code": "RATE_LIMITED",
                "error": "You're moving too fast! Please wait a moment."
            }), 429 # 429 triggers a soft warning/toast

        # 3. THE "SECURITY GATE": Invalid/Auth Issues
        elif "invalid" in error_msg or "api_key" in error_msg or "auth" in error_msg:
            return jsonify({
                "code": "INVALID_KEY",
                "error": "Your API key is invalid or has been revoked."
            }), 401 # 401 triggers the login/re-entry lock

        # 4. THE "FALLBACK": Unknown Server Errors
        return jsonify({"error": "An unexpected AI error occurred."}), 500
@app.route('/memory')
def memory():
    user_id = session.get('user_id')
    with getDBConnection() as con:
        with con.cursor(row_factory=dict_row) as cur:
            try:
            # --- QUERY 1: FETCH REVIEW QUEUE ---
            # Changed c.name -> c.title
                cur.execute("""
                SELECT 
                    q.id as question_id, 
                    q.title as question_title, 
                    q.link as question_link, 
                    c.title as concept_title,   -- <--- FIXED: using c.title
                    up."interval" as days_interval
                FROM questions q
                JOIN user_progress up ON q.id = up.question_id
                JOIN concepts c ON q.concept_id = c.id
                WHERE up.user_id = %s AND up.next_review <= CURRENT_DATE
                ORDER BY up.next_review ASC
            """, (user_id,))
                review_queue = cur.fetchall()
            # --- QUERY 2: FETCH STATS ---
            # Changed c.name -> c.title here too
                cur.execute("""
                SELECT 
                    c.title as concept_title,   -- <--- FIXED
                    COUNT(up.question_id) as solved_count, 
                    COALESCE(AVG(up.ease_factor), 0) as avg_ease
                FROM concepts c
                LEFT JOIN questions q ON c.id = q.concept_id
                LEFT JOIN user_progress up ON q.id = up.question_id AND up.user_id = %s
                GROUP BY c.id, c.title          -- <--- FIXED: Group by title
            """, (user_id,))
                stats_raw = cur.fetchall()
                stats = []
        # Process Stats
                for row in stats_raw:
                    name = row['concept_title'] 
                    solved = row['solved_count']
                    ease = float(row['avg_ease'])
                    if solved == 0: signal = 0
                    elif ease >= 2.6: signal = 4
                    elif ease >= 2.1: signal = 3
                    elif ease >= 1.5: signal = 2
                    else: signal = 1
                    stats.append({"name": name, "solved": solved, "signal": signal})
                    # print(stats)
                return render_template('retention.html', queue=review_queue, stats=stats)
            except Exception as e:
                # print(f"Error: {e}")
                return "Database Error", 500

@app.route('/api/review', methods=['POST'])
def api_review():
    # 1. Security Check
    user_id = session.get('user_id')
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    # 2. Get Data from Frontend
    data = request.get_json()
    question_id = data.get('question_id')
    quality = int(data.get('quality', 0))  # 0, 3, 4, 5
    # Get time from 'time_spent' (matching the JS payload)
    time_seconds = int(data.get('time_spent', 0))
    provider = data.get("provider")
    with getDBConnection() as con:
        with con.cursor() as cur:
            try:
            # 3. Fetch Current Stats
                cur.execute("""
                SELECT "interval", ease_factor, repetitions 
                FROM user_progress 
                WHERE user_id = %s AND question_id = %s
            """, (user_id, question_id))
                record = cur.fetchone()
            # Defaults (Safety net if row exists but values are null)
                curr_ivl = record[0] if record and record[0] else 1
                curr_ease = record[1] if record and record[1] else 2.5
                curr_reps = record[2] if record and record[2] else 0
            # 4. Run the Algorithm
                new_ivl, new_ease, new_reps, new_date = sm2_algorithm(quality, curr_ivl, curr_ease, curr_reps)
            # 5. Update Database
                cur.execute("""
                UPDATE user_progress 
                SET 
                    "interval" = %s,
                    ease_factor = %s,
                    repetitions = %s,
                    next_review = %s,
                    solved_at = NOW()
                WHERE user_id = %s AND question_id = %s
            """, (new_ivl, new_ease, new_reps, new_date, user_id, question_id))
            # ... your existing code that updates user_progress ...

    # NEW: Drop a record into the activity log
                action = "reviewed"
            # log_to_activity(user_id,question_id,action,quality,time_seconds,api_key,provider=provider)
                cur.execute("""
                INSERT INTO activity_log 
                (user_id, question_id, action, confidence_level, time_spent_seconds) 
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """, (user_id, question_id, action, quality, time_seconds))
        
                activity_id = cur.fetchone()[0] # This is the unique ID for this specific solve

        # 2. Tell the worker: "Hey, go find row ID X and add the AI scores to it"
                task_payload = {
                "activity_id": activity_id, # The key to the update
                "user_id": user_id,
                "q_id": question_id,
                "provider": provider
                }
                Redis.lpush("ai_analysis_queue", json.dumps(task_payload))
            # Change 'solved' to 'reviewed' for your review route
    # Make sure you con.commit() after this!
                con.commit()
                return jsonify({"status": "success", "new_date": str(new_date)})

            except Exception as e:
                con.rollback()
                return jsonify({"error":"Server error! check again after few time"}), 500
        

@app.route('/api/roadmap-data')
def roadmap_data():
    user_id = session.get('user_id')
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    with getDBConnection() as con:
        with con.cursor(row_factory=dict_row) as cur:
        # --- FETCH CONCEPTS & PROGRESS ---
            cur.execute("""
            SELECT 
                c.id, 
                c.title, 
                COUNT(up.question_id) as solved_count
            FROM concepts c
            LEFT JOIN questions q ON c.id = q.concept_id
            LEFT JOIN user_progress up ON q.id = up.question_id 
                    AND up.user_id = %s AND up.is_solved = TRUE
            GROUP BY c.id, c.title
            ORDER BY c.id ASC
        """, (user_id,))
            concepts = cur.fetchall()
        # Return raw JSON data
            return jsonify(concepts)
@app.route('/roadmap')
def roadmap():
    user_id = session.get('user_id')
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    return render_template('roadmap.html')
@app.route('/resource')
def resource():
    user_id = session.get('user_id')
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    return render_template('resource.html')
@app.route('/profile')
def profile():
    user_id = session.get('user_id')
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    return render_template('profile.html')
def getUserInfo(user_id,cur):
    # print(user_id)
    # 1. Execute the query safely (the trailing comma in (user_id,) is required by psycopg2!)
    cur.execute("""
        SELECT id, name, username, phone_number, email 
        FROM users 
        WHERE id = %s
    """, (user_id,))
    # 2. Fetch the single row
    user_row = cur.fetchone()
    # 3. Safety check: if the user doesn't exist, return None
    if not user_row:
        return None
    # 4. Map the raw SQL tuple into a clean Python dictionary
    # (Matches the exact order of your SELECT statement above)
    user_data = {
        "id": user_row['id'],
        "name": user_row['name'],
        "username": user_row['username'],
        "phone_number": user_row['phone_number'],
        "email": user_row['email']
    }
    return user_data
def getLogs(user_id, cur):
    # Notice we removed TO_CHAR. We just want the raw timestamp now.
    cur.execute("""
        SELECT 
            q.title AS problem, 
            c.title AS concept, 
            q.difficulty, 
            up.solved_at 
        FROM user_progress up
        JOIN questions q ON up.question_id = q.id
        JOIN concepts c ON q.concept_id = c.id
        WHERE up.user_id = %s 
        ORDER BY up.solved_at DESC 
        LIMIT 15
    """, (user_id,))
    logs_data = cur.fetchall()
    # Get today's date to compare against
    today = datetime.now().date()
    for log in logs_data:
        # --- 1. Dynamic Colors ---
        difficulty = log.get('difficulty', '').lower()
        if difficulty == 'easy':
            log['color'] = 'success'
        elif difficulty == 'medium':
            log['color'] = 'warning'
        else:
            log['color'] = 'danger'
        # --- 2. Relative Time Math ---
        # Convert the SQL timestamp to a simple date
        solved_date = log['solved_at'].date()
        days_ago = (today - solved_date).days
        if days_ago == 0:
            log['date'] = "Today"
        elif days_ago == 1:
            log['date'] = "Yesterday"
        elif days_ago < 7:
            log['date'] = f"{days_ago} Days Ago"
        elif days_ago < 14:
            log['date'] = "1 Week Ago"
        elif days_ago < 30:
            log['date'] = f"{days_ago // 7} Weeks Ago"
        else:
            # If it's older than a month, just show the actual date (e.g., "Oct 24, 2023")
            log['date'] = solved_date.strftime("%b %d, %Y")
            
        # We don't need to send the raw timestamp to the frontend anymore
        del log['solved_at']
    return logs_data
@app.route('/api/profile')
def api_profile():
    # 1. Grab ID (fallback to 1 for testing if session expires)
    user_id = session.get('user_id')
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    
    # 2. Open Tools
    with getDBConnection() as con:
        with con.cursor(row_factory=dict_row) as cur:
    # 3. Fetch Data
            total_solved, streak = getStreak(user_id, con, cur)
            userinfo = getUserInfo(user_id, cur)
            userLogs = getLogs(user_id,cur)
    # Safety Check: If user isn't in the database, don't crash
        if not userinfo:
            return jsonify({"error": "User not found"}), 404
    
    data = {
        "user": {
            "name": userinfo['name'],
            "username": userinfo["username"],
            "email": userinfo["email"], # <-- Real data now!
            "streak": streak
        },
        "logs": userLogs
    }
    return jsonify(data)
@app.route('/api/change-password', methods=['POST'])
def change_password():
    # 1. Ensure the user is logged in
    user_id = session.get('user_id')
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    if not current_password or not new_password:
        return jsonify({"error": "Both fields are required."}), 400
    try:
        with getDBConnection() as con:
            with con.cursor(row_factory=dict_row) as cur:
        # 2. Get their current password from the DB
                cur.execute("SELECT userpassword FROM users WHERE id = %s", (user_id,))
                user = cur.fetchone()

                if not user:
                    return jsonify({"error": "User not found"}), 404

                current_db_password = user['userpassword']
                is_valid = False

            # 3. Bilingual Check (handles both hashed and old plaintext passwords)
                if current_db_password.startswith('scrypt:') or current_db_password.startswith('pbkdf2:'):
                    is_valid = check_password_hash(current_db_password, current_password)
                else:
                    is_valid = (current_db_password == current_password)

                if not is_valid:
                    return jsonify({"error": "Incorrect current password"}), 401

            # 4. Hash the NEW password and update the database
                hashed_new_password = generate_password_hash(new_password)
            
                cur.execute("UPDATE users SET userpassword = %s WHERE id = %s", (hashed_new_password, user_id))
                con.commit()
                return jsonify({"success": True, "message": "Password updated securely!"})

    except Exception as e:
        # if con: con.rollback()
        print(f"Database error during password change: {e}")
        return jsonify({"error": "Server error. Could not update password."}), 500
        

@app.route('/journey')
def journey():
    # Make sure they are logged in!
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('journey.html')
# @app.route('/api/journey')
# def api_journey():
#     user_id = session.get('user_id')
#     if not user_id:
#         return jsonify({"error": "Unauthorized"}), 401

#     con = None
#     cur = None
#     try:
#         con = getDBConnection()
#         cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
#         # The Ultimate SQL Query:
#         # Grabs all concepts, counts total available questions, 
#         # counts how many THIS user solved, and creates a comma-separated list of their solved question titles!
#         cur.execute("""
#     SELECT 
#         c.title AS concept_title,
#         COUNT(DISTINCT q.id) AS total_questions,
#         COUNT(DISTINCT CASE WHEN up.is_solved = TRUE THEN up.question_id ELSE NULL END) AS solved_questions,
#         STRING_AGG(DISTINCT CASE WHEN up.is_solved = TRUE THEN q.title ELSE NULL END, ', ') AS solved_list
#     FROM concepts c
#     LEFT JOIN questions q ON c.id = q.concept_id
#     LEFT JOIN user_progress up ON q.id = up.question_id AND up.user_id = %s
#     GROUP BY c.id, c.title
# """, (user_id,))
#         db_results = cur.fetchall()
#         # print(db_results)
#         journey_data = {}
#         for row in db_results:
#             title = row['concept_title']
#             # Format the text for the hover tooltip
#             details = "Locked. Solve previous concepts first."
#             if row['solved_questions'] > 0:
#                 details = f"Solved: {row['solved_list']}"
#             elif row['total_questions'] == 0:
#                 details = "Questions coming soon."
#             # Use the EXACT concept title from your database as the dictionary key
#             journey_data[title] = {
#                 "solved": row['solved_questions'],
#                 "total": row['total_questions'],
#                 "details": details
#             }

#         return jsonify(journey_data), 200

    # except Exception as e:
    #     print("Error fetching journey data:", e)
    #     return jsonify({"error": "Failed to load journey"}), 500
    # finally:
    #     if cur: cur.close()
    #     if con: con.close()
@app.route("/question/<int:q_id>")
def question_page(q_id):
    user_id = session.get("user_id")
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    if not user_id:
        return redirect("/login")
    
    # We don't need to fetch data here because our 
    # workspace.js fetches it via the API on load!
    return render_template("question.html")
@app.route("/api/get_similar/<int:q_id>")
def get_similar(q_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
        
    with getDBConnection() as con:
        with con.cursor(row_factory=dict_row) as cur:
            try:
            # 1. Get concept_id of current question 
            # 2. Find 3 other questions in that concept NOT solved by this user
            # 3. Exclude the current question itself
                query = """
                SELECT id, title, difficulty 
                FROM questions 
                WHERE concept_id = (SELECT concept_id FROM questions WHERE id = %s)
                AND id != %s
                AND id NOT IN (
                    SELECT question_id FROM user_progress 
                    WHERE user_id = %s AND is_solved = TRUE
                )
                ORDER BY RANDOM() 
                LIMIT 3
            """
                cur.execute(query, (q_id, q_id, user_id))
                similar_questions = cur.fetchall()
            
                return jsonify(similar_questions)

            except Exception as e:
                print(f"Error fetching similar: {e}")
                return jsonify({"error": "Could not fetch recommendations"}), 500

app.config.update(
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False, # ngrok uses HTTPS, so this must be True
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_NAME='flask_session' # Give it a specific name
)
@app.route('/api/consistency')
def api_consistency():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    with getDBConnection() as con:
        with con.cursor(row_factory=dict_row) as cur:
            try:
            # Grab the raw stats from the last 30 days
                cur.execute("""
                SELECT 
                    COUNT(DISTINCT DATE(created_at)) AS active_days,
                    COUNT(CASE WHEN action = 'solved' THEN 1 END) AS solves,
                    COUNT(CASE WHEN action = 'reviewed' THEN 1 END) AS reviews
                FROM activity_log
                WHERE user_id = %s AND created_at >= NOW() - INTERVAL '30 days'
            """, (user_id,))
                stats = cur.fetchone()

                active_days = stats['active_days'] or 0
                solves = stats['solves'] or 0
                reviews = stats['reviews'] or 0

            # --- THE MATH ---
            # 1. Habit (50 pts): Max points if active 20 out of the last 30 days
                habit_score = min(50, (active_days / 20.0) * 50)
            
            # 2. Discipline (50 pts): Max points if you do at least 1 review for every 2 new solves
                discipline_score = 0
                if solves > 0:
                    discipline_score = min(50, (reviews / (solves * 0.5)) * 50)
                elif solves == 0 and reviews > 0:
                    discipline_score = 50 # Reviewing without solving is still great discipline
                
                score = round(habit_score + discipline_score)
            
                return jsonify({
                "score": score,
                "active_days": active_days,
                "solves": solves,
                "reviews": reviews
            }), 200

            except Exception as e:
                # print(f"Consistency Error: {e}")
                return jsonify({"error": str(e)}), 500

@app.route('/api/chat_history/<int:question_id>', methods=['GET'])
def get_chat_history(question_id):
    # 1. Grab the user ID (Adjust this based on how your app handles logins!)
    user_id = session.get("user_id") 
    
    # If you don't have a login system yet for V1, you can temporarily hardcode this to test:
    # user_id = 1 

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    with getDBConnection() as con:
        with con.cursor(row_factory=dict_row) as cur:

            try:
            # 3. Fetch the messages in chronological order so the chat reads top-to-bottom
                cur.execute("""
                SELECT role, content, thread_id 
                FROM chat_messages 
                WHERE thread_id = (
                    SELECT thread_id 
                    FROM chat_messages 
                    WHERE user_id = %s AND question_id = %s 
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                ORDER BY created_at ASC
            """, (user_id, question_id))
            
                history = cur.fetchall()
            
            # 4. Return the data as a clean JSON package for the frontend
                return jsonify({"history": history}), 200

            except Exception as e:
                print("Chat History Error:", e)
                return jsonify({"error": "Failed to fetch history"}), 500

def fetch_session_transcript(user_id, q_id):
    """
    Pulls the full conversation for a specific user and question.
    Returns a list of HumanMessage and AIMessage objects.
    """
    try:
        with getDBConnection() as con:
            with con.cursor(row_factory=dict_row) as cur:
        # We grab all messages for this user/question pair
        # typically filtered by the most recent session window
                cur.execute("""
                SELECT role, content 
                FROM chat_messages 
                WHERE user_id = %s AND question_id = %s
                ORDER BY id ASC
            """, (user_id, q_id))
                rows = cur.fetchall()
        # Mapping to LangChain objects
            transcript = []
            for role, content in rows:
                if role == 'user':
                    transcript.append(HumanMessage(content=content))
                else:
                    transcript.append(AIMessage(content=content))
            return transcript
    except Exception as e:
        print(f"Database Retrieval Error: {e}")
        return []
def get_skill_matrix_stats(user_id):
    with getDBConnection() as con:
        with con.cursor() as cur:
    # 1. Pull the individual averages for ALL relevant columns
            cur.execute("""
            SELECT 
                c.title AS concept_title,
                COUNT(al.id) AS solved_count,
                AVG(al.ai_bifurcated_score) AS avg_logic,
                AVG(al.clarity_of_thought) AS avg_clarity,
                AVG(al.confidence_level) AS avg_confidence
            FROM activity_log al
            JOIN questions q ON al.question_id = q.id
            JOIN concepts c ON q.concept_id = c.id
            WHERE al.user_id = %s
            GROUP BY c.title
        """, (user_id,))
            rows = cur.fetchall()
    formatted_data = []
    for r in rows:
        label = r[0]
        count = r[1]
        
        # 2. Safely extract the data (default to 0 if NULL)
        avg_logic = float(r[2] or 0)
        avg_clarity = float(r[3] or 0)
        avg_confidence = float(r[4] or 0)
        
        # 3. Calculate the Composite Score (Average of the 3 metrics)
        # Since all three are on a 1-5 scale, their average is also 1-5.
        composite_score = (avg_logic + avg_clarity + avg_confidence) / 3
        
        # 4. Scale to 0-100% for the Radar Chart
        mastery_percentage = round(composite_score * 20, 1)
        clarity_percentage = round(avg_clarity * 20, 1) # Keeping this separate just in case your UI needs it

        formatted_data.append({
            "label": label,
            "count": count,
            "mastery": mastery_percentage,
            "clarity": clarity_percentage  
        })

    return formatted_data
def get_concept_breakdown(user_id):
    with getDBConnection() as con:
        with con.cursor() as cur:
            try:
                cur.execute("""
                SELECT 
                    c.title AS concept,
                    q.title AS q_title,
                    al.time_spent_seconds,
                    al.confidence_level
                FROM activity_log al
                JOIN questions q ON al.question_id = q.id
                JOIN concepts c ON q.concept_id = c.id
                WHERE al.user_id = %s
                ORDER BY c.title, al.created_at DESC
            """, (user_id,))
                rows = cur.fetchall()
                grouped = {}
                for concept, q_title, time_sec, conf in rows:
                # 1. Fallbacks for missing text data
                    concept_name = concept if concept else "Uncategorized"
                    question_name = q_title if q_title else "Unknown Question"
                # 2. NULL-Safety for Math (This stops the crashes!)
                    safe_time = int(time_sec) if time_sec is not None else 0
                    safe_conf = float(conf) if conf is not None else 0.0
                # Initialize the group
                    if concept_name not in grouped:
                        grouped[concept_name] = []
                # Format time nicely (Shows "< 1m" if they solved it super fast)
                    mins = safe_time // 60
                    time_display = f"{mins}m" if mins > 0 else "< 1m"
                    grouped[concept_name].append({
                    "title": question_name,
                    "time": time_display,
                    "autonomy": f"{int(safe_conf * 20)}%" 
                })
                return grouped
            except Exception as e:
            # If the SQL fails, print the exact error so you can debug it, 
            # but return an empty dictionary so the UI doesn't completely break!
                print(f"💥 Error in get_concept_breakdown: {e}")
                return {} 

@app.route('/api/insights/matrix', methods=['GET'])
def get_insights_data():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    # 1. Fetch the Radar Chart Data
    matrix_stats = get_skill_matrix_stats(user_id)
    # 2. Fetch the Accordion List Data
    concept_history = get_concept_breakdown(user_id)
    # (Optional) 3. Fetch the AI Diagnostic Summary from DB if you cached it
    # ai_summary = fetch_latest_diagnostic(user_id)

    return jsonify({
        "status": "success",
        "matrix_stats": matrix_stats,
        "concept_history": concept_history
    })
@app.route('/insights')
def insights_page():
    # Security: Kick them to login if they aren't logged in
    # Render the LogicLens page
    if 'user_id' not in session:
        # This "asks" them to login by sending them to the login page
        return redirect(url_for('LoginPage'))
    return render_template('insights.html', name=session.get('name', ''))
@app.route('/api/insights/ai-summary', methods=['POST'])
def get_ai_summary():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        # 1. Grab the exact same stats we use for the Radar Chart
        stats = get_skill_matrix_stats(user_id)
        data = request.get_json()

        api_key = Redis.hget(f"user:{session["user_id"]}", "api_key")
        provider = data.get("provider")
        decrypted_key = decrypt_key(api_key)
        # 2. If they haven't solved anything yet, skip the AI call to save tokens
        if not stats:
            return jsonify({
                "diagnostic": "You need to solve some problems before I can analyze your logic patterns.",
                "predictor": "Start your journey. Complete at least 3 problems to unlock your interview predictor."
            })

        # 3. Smash the stats into a compact string for the AI to read
        stats_str = ", ".join([f"{s['label']}: {s['mastery']}% Mastery ({s['count']} solved)" for s in stats])
        
        coach = InsightCoach(decrypted_key, provider)
        ai_result = coach.get_summary(stats_str)

        if ai_result:
            return jsonify({
                "diagnostic": ai_result.diagnostic,
                "predictor": ai_result.predictor
            })
        else:
            raise Exception("AI returned empty.")

    except Exception as e:
        print(f"💥 Error generating AI Summary: {e}")
        # Graceful fallback so the UI never breaks
        return jsonify({
            "diagnostic": "System currently analyzing your latest data structures. Check back soon.",
            "predictor": "Gathering more data points to formulate an accurate interview readiness score."
        })
@app.route('/api/set-key', methods=['POST'])
def set_api_key():
    
    data = request.json
    api_key = data.get('api_key')
    provider = data.get('provider')
    
    # For V1, we'll use a 'default_user' ID. 
    # Later, this would be the logged-in user's ID.
    user_id = session.get("user_id")
    
    if api_key:
        encrypted_val = encrypt_key(api_key)
        redis_key = f"user:{user_id}"
        Redis.hset(redis_key, mapping={
            "api_key": encrypted_val,
            "provider": provider
        })
        Redis.expire(redis_key, 86400) # Key expires after 24 hours
        return jsonify({"status": "success"}), 200
    
    return jsonify({"status": "error", "message": "No key provided"}), 400
@app.route('/api/user-journey', methods=['GET'])
def get_user_journey():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with getDBConnection() as con:
            with con.cursor() as cur:
        
            # JOINING user_progress -> questions -> concepts
                query = """
                SELECT 
                    c.title, 
                    c.icon, 
                    MIN(up.solved_at) AS achieved_at,
                    COUNT(up.question_id) AS questions_mastered
                FROM user_progress up
                JOIN questions q ON up.question_id = q.id
                JOIN concepts c ON q.concept_id = c.id
                WHERE up.user_id = %s
                GROUP BY c.id, c.title, c.icon
                ORDER BY achieved_at ASC;
            """
            
                cur.execute(query, (user_id,))
                rows = cur.fetchall()
        journey_data = []
        for row in rows:
            journey_data.append({
                "title": row[0],
                "icon": row[1],
                "achieved_at": row[2].isoformat() if row[2] else None,
                "count": row[3]
            })
        return jsonify(journey_data)
    except Exception as e:
        print(f"Journey API Error: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
@app.route('/about') # The URL
def aboutus():       # The FUNCTION NAME (This is what url_for looks for)
    return render_template('aboutus.html')
if __name__ == "__main__":
    app.run(debug=True)