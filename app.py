from flask import Flask, render_template, request, jsonify,session,redirect,url_for,flash
from aiBotBackend import chatbot;
from datetime import date, timedelta 
import psycopg2.extras
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2 import errors
from dotenv import load_dotenv
import os
from datetime import datetime
load_dotenv()
app = Flask(__name__)
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
app.secret_key = os.getenv("FLASK_SECRET_KEY") 

def getDBConnection():
    # Pulling DB details from .env for security
    con = psycopg2.connect(
        host=os.getenv("DB_HOST"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS")
    )
    return con

from werkzeug.security import check_password_hash, generate_password_hash

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
        con = getDBConnection()
        cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # 1. Ask for the user by username ONLY
        cur.execute("SELECT id, username, name, userpassword FROM users WHERE username = %s", (username,))
        result = cur.fetchone()
        
        # If no user is found with that username
        if not result:
            return jsonify({"error": "Invalid Credentials"}), 401
            
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
        session['username'] = result['username']    
        
        return jsonify({"message": "Login successful", "name": result['name']}), 200

    except Exception as e:
        print("Database Error in login:", e)
        return jsonify({"error": "Server error"}), 500
        
    finally:
        # 5. Clean up tools safely
        if cur: cur.close()
        if con: con.close()

@app.route("/register_page")
def register_page():
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    userpass = data.get("userpass")
    useremail = data.get("email")
    name = data.get("name")
    
    # 1. HASH THE PASSWORD! (This turns "password123" into "scrypt:32768:8:1$...")
    hashed_password = generate_password_hash(userpass)
    
    try:
        con = getDBConnection()
        cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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
        con.rollback() 
        return jsonify({"error": "Username or Email already exists!"}), 409 

    except Exception as e:
        con.rollback()
        print("Database Error:", e)
        return jsonify({"error": "Server error. Please try again."}), 500
        
    finally:
        # Closing the cursor and connection properly!
        if 'cur' in locals(): cur.close()
        if con: con.close()

@app.route("/dashboard")
def dashboard():
    user_id = session.get('user_id')

    con = getDBConnection()
    cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
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
            
        # Calculate Percentage
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

    cur.close()
    con.close()
    
    print(f"DEBUG: Total Solved: {total_solved}, Retention: {retention_pct}%")
    
    return render_template('dashboard.html', 
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
    con = getDBConnection()
    cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # 1. Get Total Solved 
    total_solved,streak=getStreak(user_id,con,cur)
    cur.close()
    con.close()

    return jsonify({
        "total_solved": total_solved,
        "streak": streak
    })

@app.route("/questions/<int:concept_id>")
def questions_page(concept_id):
    # This just renders the blank page with the concept_id passed to the template
    return render_template("questions.html", concept_id=concept_id)
@app.route("/api/get_questions/<int:concept_id>")
def get_questions_api(concept_id):
    user_id = session.get('user_id')
    con = getDBConnection()
    cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
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
    cur.close()
    con.close()
    return jsonify(questions)

@app.route("/api/get_question_details/<int:q_id>")
def get_question_details(q_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    con = getDBConnection()
    cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
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
        if not data:
            return jsonify({"error": "Question not found"}), 404   
        return jsonify(data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        con.close()

@app.route("/api/toggle_solve", methods=["POST"])
def toggle_solve():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json()
    q_id = data.get("question_id")
    con = getDBConnection()
    cur = con.cursor()
    
    try:
        # 1. Check if it exists
        cur.execute("SELECT 1 FROM user_progress WHERE user_id = %s AND question_id = %s", (user_id, q_id))
        exists = cur.fetchone()
        
        if exists:
            # OPTION A: Reset (Delete row)
            cur.execute("DELETE FROM user_progress WHERE user_id = %s AND question_id = %s", (user_id, q_id))
            action = "reset"
            
        else:
            # OPTION B: First Solve (Initialize SRS Defaults)
            tomorrow = date.today() + timedelta(days=1)
            
            # Note the double quotes around "interval" for Postgres!
            query = """
                INSERT INTO user_progress 
                (user_id, question_id, solved_at, "interval", ease_factor, repetitions, next_review, is_solved) 
                VALUES (%s, %s, NOW(), 1, 2.5, 0, %s, TRUE)
            """
            cur.execute(query, (user_id, q_id, tomorrow))
            action = "solved"
            
        con.commit() 
        return jsonify({"status": "success", "action": action})
        
    except Exception as e:
        con.rollback() 
        print(f"Error: {e}") # Good for debugging
        return jsonify({"error": str(e)}), 500
        
    finally:
        cur.close()
        con.close()
@app.route("/api/ask_ai", methods=["POST"])
def ask_AI():
    data = request.get_json()
    con = getDBConnection()
    cur = con.cursor()

    question_id = data.get("question_id")
    query = data.get("query")
    query_db = "select description from questions where id = %s "
    cur.execute(query_db,(question_id,))
    question_description = cur.fetchone()
    thread_id = 1
    config = {"configurable": {"thread_id": thread_id}}
    response = chatbot.invoke({'user_input': query,'question': question_description},config=config)
    print(response['bot_response'])
    return jsonify({"answer": response['bot_response']})

@app.route('/memory')
def memory():
    user_id = session.get('user_id')
    
    con = getDBConnection()
    cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
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

        return render_template('retention.html', queue=review_queue, stats=stats)

    except Exception as e:
        print(f"Error: {e}")
        return "Database Error", 500
    finally:
        cur.close()
        con.close()

@app.route('/api/review', methods=['POST'])
def api_review():
    # 1. Security Check
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    # 2. Get Data from Frontend
    question_id = request.form.get('question_id')
    quality = int(request.form.get('quality')) # 0, 3, 4, 5

    con = getDBConnection()
    cur = con.cursor()

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
        
        con.commit()
        return jsonify({"status": "success", "new_date": str(new_date)})

    except Exception as e:
        con.rollback()
        print("Error in SRS update:", e)
        return jsonify({"error": str(e)}), 500
        
    finally:
        cur.close()
        con.close()

@app.route('/api/roadmap-data')
def roadmap_data():
    user_id = session.get('user_id')
    con = getDBConnection()
    cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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
    cur.close()
    con.close()
    
    # Return raw JSON data
    return jsonify(concepts)
@app.route('/roadmap')
def roadmap():
    return render_template('roadmap.html')
@app.route('/resource')
def resource():
    return render_template('resource.html')
@app.route('/profile')
def profile():
    return render_template('profile.html')
def getUserInfo(user_id,cur):
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
    print("hii")
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
    print("Hello")
    return logs_data
@app.route('/api/profile')
def api_profile():
    # 1. Grab ID (fallback to 1 for testing if session expires)
    user_id = session.get('user_id')
    
    # 2. Open Tools
    con = getDBConnection()
    cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    # 3. Fetch Data
    total_solved, streak = getStreak(user_id, con, cur)
    userinfo = getUserInfo(user_id, cur)
    userLogs = getLogs(user_id,cur)
    print(userLogs)
    print(userinfo)
    # 4. Close Tools (Faucet first, then Main!)
    cur.close()
    con.close()
    
    # Safety Check: If user isn't in the database, don't crash
    if not userinfo:
        return jsonify({"error": "User not found"}), 404
    # if not userLogs:
    #     return jsonify({"error": "User not found"}), 404


    # 5. Format Data
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
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401

    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return jsonify({"error": "Both fields are required."}), 400

    con = None
    cur = None
    
    try:
        con = getDBConnection()
        cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

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
        if con: con.rollback()
        print(f"Database error during password change: {e}")
        return jsonify({"error": "Server error. Could not update password."}), 500
        
    finally:
        if cur: cur.close()
        if con: con.close()
@app.route('/journey')
def journey():
    # Make sure they are logged in!
    if 'user_id' not in session:
        return redirect('/login')
    return render_template('journey.html')
@app.route('/api/journey')
def api_journey():
    user_id = session.get('user_id')
    if not user_id:
        print("Hii")
        return jsonify({"error": "Unauthorized"}), 401


    con = None
    cur = None
    try:
        con = getDBConnection()
        cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # The Ultimate SQL Query:
        # Grabs all concepts, counts total available questions, 
        # counts how many THIS user solved, and creates a comma-separated list of their solved question titles!
        cur.execute("""
            SELECT 
                c.title AS concept_title,
                COUNT(DISTINCT q.id) AS total_questions,
                COUNT(DISTINCT up.question_id) AS solved_questions,
                STRING_AGG(DISTINCT q.title, ', ') AS solved_list
            FROM concepts c
            LEFT JOIN questions q ON c.id = q.concept_id
            LEFT JOIN user_progress up ON q.id = up.question_id AND up.user_id = %s
            GROUP BY c.id, c.title
        """, (user_id,))
        
        db_results = cur.fetchall()
        print(db_results)
        journey_data = {}
        for row in db_results:
            title = row['concept_title']
            
            # Format the text for the hover tooltip
            details = "Locked. Solve previous concepts first."
            if row['solved_questions'] > 0:
                details = f"Solved: {row['solved_list']}"
            elif row['total_questions'] == 0:
                details = "Questions coming soon."

            # Use the EXACT concept title from your database as the dictionary key
            journey_data[title] = {
                "solved": row['solved_questions'],
                "total": row['total_questions'],
                "details": details
            }

        return jsonify(journey_data), 200

    except Exception as e:
        print("Error fetching journey data:", e)
        return jsonify({"error": "Failed to load journey"}), 500
    finally:
        if cur: cur.close()
        if con: con.close()
@app.route("/question/<int:q_id>")
def question_page(q_id):
    user_id = session.get("user_id")
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
        
    con = getDBConnection()
    cur = con.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
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
    finally:
        cur.close()
        con.close()
if __name__ == "__main__":
    app.secret_key="THERRANGBHRUCH"
    app.run(debug=True)