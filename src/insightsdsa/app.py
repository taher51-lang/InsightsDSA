"""Flask API — routes converted from raw SQL to SQLAlchemy ORM.

All render_template() calls are replaced with SPA index serving or JSON APIs.
"""

from datetime import date, datetime, timedelta
import logging
import json
import traceback
from pathlib import Path
from logging.handlers import RotatingFileHandler

from flask import (
    Flask, abort, flash, jsonify, redirect, request, send_from_directory, session, url_for,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import and_, delete, exists, func, select, update
from sqlalchemy.exc import IntegrityError
from authlib.integrations.flask_client import OAuth
from flask_wtf.csrf import CSRFProtect
from langchain_core.messages import AIMessage, HumanMessage
from cryptography.fernet import Fernet
import redis

from .analyst_bot import InsightCoach
from .config import settings
from .constants import PACKAGE_ROOT, PROJECT_ROOT
from .dashboard_data import build_dashboard_payload
from .retention_data import build_retention_payload
from .db import SessionLocal, get_session
from .models import ActivityLog, ChatMessage, Concept, Question, User, UserProgress
from .sm2 import sm2_algorithm

_log = logging.getLogger(__name__)

# ── Redis ──
if settings.use_memory_redis:
    import fakeredis
    Redis = fakeredis.FakeStrictRedis(decode_responses=True)
elif settings.redis_url:
    Redis = redis.from_url(settings.redis_url, decode_responses=True)
else:
    Redis = redis.Redis(
        host=settings.redis_host, port=settings.redis_port,
        db=settings.redis_db, password=settings.redis_password, decode_responses=True,
    )

if not settings.encryption_key:
    raise RuntimeError("ENCRYPTION_KEY must be set in the environment (Fernet-compatible key).")
cipher_suite = Fernet(settings.encryption_key)

app = Flask(__name__, template_folder=str(PACKAGE_ROOT / "templates"), static_folder=str(PACKAGE_ROOT / "static"))
app.secret_key = settings.flask_secret_key
app.config.update(
    SESSION_COOKIE_SAMESITE=settings.session_cookie_samesite,
    SESSION_COOKIE_SECURE=settings.session_cookie_secure,
    SESSION_COOKIE_HTTPONLY=settings.session_cookie_httponly,
    SESSION_COOKIE_NAME=settings.session_cookie_name,
)

_chatbot = None
def _get_chatbot():
    global _chatbot
    if _chatbot is None:
        from . import ai_bot_backend as _ab
        _chatbot = _ab.chatbot
    return _chatbot

# ── Logging ──
_log_dir = Path(PROJECT_ROOT) / settings.log_dir
_log_dir.mkdir(parents=True, exist_ok=True)
file_handler = RotatingFileHandler(str(_log_dir / settings.log_file), maxBytes=settings.log_max_bytes, backupCount=settings.log_backup_count)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('LogicLens startup')

@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

csrf = CSRFProtect(app)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ── SPA serving ──
SPA_BROWSER_DIR = PROJECT_ROOT / "frontend" / "dist" / "insightsdsa-ui" / "browser"
SPA_INDEX_FILE = SPA_BROWSER_DIR / "index.html"

def _serve_spa_index():
    if not SPA_INDEX_FILE.is_file():
        return jsonify({"error": "SPA bundle not found", "hint": "Run: cd frontend && npm install && npm run build"}), 503
    return send_from_directory(SPA_BROWSER_DIR, "index.html")

def encrypt_key(plain_text):
    return cipher_suite.encrypt(plain_text.encode()).decode()
def decrypt_key(encrypted_text):
    return cipher_suite.decrypt(encrypted_text.encode()).decode()

# ── Google OAuth ──
oauth = OAuth(app)
google = oauth.register(
    name='google', client_id=settings.google_client_id, client_secret=settings.google_client_secret,
    server_metadata_url=settings.google_openid_metadata_url, client_kwargs={'scope': 'openid email profile'},
)

# ═══════════════════════════════════════════
#  API ENDPOINTS
# ═══════════════════════════════════════════

@app.get("/api/v1/health")
def api_v1_health():
    return jsonify({"status": "ok"})

@app.get("/api/v1/csrf")
def api_v1_csrf():
    from flask_wtf.csrf import generate_csrf
    return jsonify({"csrf_token": generate_csrf()})

@app.get("/api/v1/auth/me")
def api_v1_auth_me():
    if "user_id" not in session:
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "user_id": session["user_id"], "user_name": session.get("user_name"), "email": session.get("user_email"), "profile_pic": session.get("profile_pic")})

@app.get("/api/v1/dashboard")
def api_v1_dashboard():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        payload = build_dashboard_payload(int(user_id), s)
    payload["user_name"] = session.get("user_name") or ""
    return jsonify(payload)

@app.get("/api/v1/retention")
def api_v1_retention():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        with get_session() as s:
            return jsonify(build_retention_payload(int(user_id), s))
    except Exception:
        _log.exception("api_v1_retention")
        return jsonify({"error": "Database error"}), 500

# ── Auth routes ──
@app.route('/login/google')
def login_google():
    if not settings.google_client_id or not settings.google_client_secret:
        flash("Google sign-in is not configured.")
        return redirect("/login")
    redirect_uri = settings.google_redirect_uri or url_for('google_callback', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/login/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
    except Exception as exc:
        app.logger.warning("Google OAuth error: %s", exc)
        flash("Google sign-in was cancelled or failed. Please try again.")
        return redirect("/login")
    user_info = token.get('userinfo')
    if user_info is None:
        try:
            user_info = google.userinfo(token=token)
        except Exception:
            flash("Could not read your Google profile.")
            return redirect("/login")
    email = user_info.get('email')
    if not email:
        flash("Google did not return an email for this account.")
        return redirect("/login")
    g_id = user_info.get('sub')
    full_name = user_info.get('name', 'Explorer')
    first_name = (full_name.split() or ["Explorer"])[0]
    pic = user_info.get('picture', '')
    with get_session() as s:
        existing_id = s.scalar(select(User.id).where(User.email == email))
        if existing_id:
            s.execute(update(User).where(User.email == email).values(google_id=g_id, profile_pic=pic))
            user_id = existing_id
        else:
            u = User(username=first_name, name=full_name, email=email, google_id=g_id, profile_pic=pic)
            s.add(u)
            s.flush()
            user_id = u.id
        session["user_id"] = user_id
    session["user_email"] = email
    session["user_name"] = first_name
    session["profile_pic"] = pic
    return redirect("/dashboard")

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
    try:
        with get_session() as s:
            result = s.execute(select(User.id, User.username, User.name, User.userpassword, User.google_id).where(User.username == username)).mappings().first()
            if not result:
                return jsonify({"error": "Invalid Credentials"}), 401
            if result["userpassword"] is None and result["google_id"] is not None:
                return jsonify({"error": "This account is linked with Google. Please use the 'Continue with Google' button."}), 403
            current_db_password = result["userpassword"]
            is_valid = False
            needs_upgrade = False
            if current_db_password.startswith('scrypt:') or current_db_password.startswith('pbkdf2:'):
                is_valid = check_password_hash(current_db_password, userpass)
            else:
                is_valid = (current_db_password == userpass)
                if is_valid:
                    needs_upgrade = True
            if not is_valid:
                return jsonify({"error": "Invalid Credentials"}), 401
            if needs_upgrade:
                new_hashed_password = generate_password_hash(userpass)
                s.execute(update(User).where(User.id == result["id"]).values(userpassword=new_hashed_password))
            session['user_id'] = result['id']
            session['user_name'] = result['username']
            if result["name"]:
                return jsonify({"message": "Login successful", "name": result['name']}), 200
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
    hashed_password = generate_password_hash(userpass)
    try:
        with get_session() as s:
            u = User(name=name, username=username, email=useremail, userpassword=hashed_password)
            s.add(u)
            s.flush()
            session['user_id'] = u.id
            session['user_name'] = u.username
            return jsonify({"message": "Registration Successful!"}), 201
    except IntegrityError:
        return jsonify({"error": "Username or Email already exists!"}), 409
    except Exception as e:
        print("Database Error:", e)
        return jsonify({"error": "Server error. Please try again."}), 500

# ── Data API routes ──
def getStreak(user_id, s):
    total_solved = s.scalar(select(func.count()).select_from(UserProgress).where(and_(UserProgress.user_id == user_id, UserProgress.is_solved.is_(True)))) or 0
    solved_rows = s.scalars(select(UserProgress.solved_at).where(and_(UserProgress.user_id == user_id, UserProgress.solved_at.isnot(None)))).all()
    active_dates = {dt.date() for dt in solved_rows if dt is not None}
    streak = 0
    today = date.today()
    if today in active_dates:
        streak = 1
        check_date = today - timedelta(days=1)
    elif (today - timedelta(days=1)) in active_dates:
        streak = 1
        check_date = today - timedelta(days=2)
    else:
        streak = 0
        check_date = None
    while check_date and check_date in active_dates:
        streak += 1
        check_date -= timedelta(days=1)
    return total_solved, streak

@app.route("/api/user_stats")
def get_user_stats():
    user_id = session.get('user_id')
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        total_solved, streak = getStreak(user_id, s)
        return jsonify({"total_solved": total_solved, "streak": streak})

@app.route("/api/get_questions/<int:concept_id>")
def get_questions_api(concept_id):
    user_id = session.get('user_id')
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        solved_exists = exists(select(1).where(and_(UserProgress.question_id == Question.id, UserProgress.user_id == user_id)))
        stmt = select(Question.id, Question.title, Question.difficulty, Question.link, solved_exists.label("is_solved")).where(Question.concept_id == concept_id)
        questions = []
        for row in s.execute(stmt).mappings().all():
            d = dict(row)
            d["is_solved"] = bool(d["is_solved"])
            questions.append(d)
        difficulty_map = {"Easy": 1, "Medium": 2, "Hard": 3}
        questions.sort(key=lambda x: difficulty_map.get(x['difficulty'], 4))
    return jsonify(questions)

@app.route("/api/get_question_details/<int:q_id>")
def get_question_details(q_id):
    user_id = session.get("user_id")
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        with get_session() as s:
            solved_exists = exists(select(1).where(and_(UserProgress.question_id == Question.id, UserProgress.user_id == user_id)))
            stmt = select(Question.id, Question.title, Question.description, Question.difficulty, Question.link, solved_exists.label("is_solved")).where(Question.id == q_id)
            data = s.execute(stmt).mappings().first()
            if not data:
                return jsonify({"error": "Question not found"}), 404
            out = dict(data)
            out["is_solved"] = bool(out["is_solved"])
            return jsonify(out)
    except Exception:
        return jsonify({"error": "Server error"}), 500

@app.route("/api/toggle_solve", methods=["POST"])
def toggle_solve():
    user_id = session.get("user_id")
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    q_id = data.get("question_id")
    confidence = data.get("confidence")
    time_spent = data.get("time_spent")
    provider = data.get("provider")
    s = SessionLocal()
    try:
        ex = s.scalar(select(UserProgress.user_id).where(and_(UserProgress.user_id == user_id, UserProgress.question_id == q_id)))
        if ex:
            s.execute(delete(UserProgress).where(and_(UserProgress.user_id == user_id, UserProgress.question_id == q_id)))
            s.execute(delete(ActivityLog).where(and_(ActivityLog.user_id == user_id, ActivityLog.question_id == q_id, ActivityLog.action == "solved")))
            action = "reset"
        else:
            tomorrow = date.today() + timedelta(days=1)
            action = "solved"
            s.add(UserProgress(user_id=user_id, question_id=q_id, solved_at=datetime.now(), interval_days=1, ease_factor=2.5, repetitions=1, next_review=tomorrow, is_solved=True))
            log = ActivityLog(user_id=user_id, question_id=q_id, action="solved", confidence_level=confidence, time_spent_seconds=time_spent)
            s.add(log)
            s.flush()
            activity_id = log.id
            task_payload = {"activity_id": activity_id, "user_id": user_id, "q_id": q_id, "provider": provider}
            Redis.lpush("ai_analysis_queue", json.dumps(task_payload))
        s.commit()
        return jsonify({"status": "success", "action": action})
    except Exception as e:
        s.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        s.close()

@app.route("/api/ask_ai", methods=["POST"])
def ask_AI():
    user_id = session.get("user_id")
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        data = request.get_json()
        query = data.get('query')
        question_id = data.get('question_id')
        thread_id = data.get('thread_id')
        safe_thread_id = f"user_{user_id}_{thread_id}"
        provider = data.get('provider')
        desc = s.scalar(select(Question.description).where(Question.id == question_id))
    question_description = desc if desc else "No description Provided"
    config = {"configurable": {"thread_id": safe_thread_id}}
    if not user_id:
        return jsonify({"error": "Unauthorized. Please log in."}), 401
    try:
        encrypted_key = Redis.hget(f"user:{session['user_id']}", "api_key")
        if not encrypted_key:
            return jsonify({"error": "API Key Required", "message": "Please go to Settings and add your API key first."}), 401
        response = _get_chatbot().invoke({'messages': [HumanMessage(content=query)], 'question': question_description, 'user_api_key': decrypt_key(encrypted_key), 'provider': provider}, config=config)
        ai_response = response['messages'][-1].content
        with get_session() as s:
            s.add(ChatMessage(user_id=user_id, question_id=question_id, thread_id=thread_id, role='user', content=query))
            s.add(ChatMessage(user_id=user_id, question_id=question_id, thread_id=thread_id, role='assistant', content=ai_response))
        return jsonify({"answer": ai_response})
    except Exception as e:
        traceback.print_exc()
        error_msg = str(e).lower()
        if "insufficient_quota" in error_msg or "billing" in error_msg:
            return jsonify({"code": "API_EXHAUSTED", "error": "Your API provider quota is exhausted."}), 402
        elif "429" in error_msg or "rate_limit" in error_msg or "too many requests" in error_msg:
            return jsonify({"code": "RATE_LIMITED", "error": "You're moving too fast! Please wait a moment."}), 429
        elif "invalid" in error_msg or "api_key" in error_msg or "auth" in error_msg:
            return jsonify({"code": "INVALID_KEY", "error": "Your API key is invalid or has been revoked."}), 401
        return jsonify({"error": "An unexpected AI error occurred."}), 500

@app.route('/api/review', methods=['POST'])
def api_review():
    user_id = session.get('user_id')
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    question_id = data.get('question_id')
    quality = int(data.get('quality', 0))
    time_seconds = int(data.get('time_spent', 0))
    provider = data.get("provider")
    with get_session() as s:
        try:
            row = s.execute(select(UserProgress.interval_days, UserProgress.ease_factor, UserProgress.repetitions).where(and_(UserProgress.user_id == user_id, UserProgress.question_id == question_id))).first()
            curr_ivl = row[0] if row and row[0] else 1
            curr_ease = row[1] if row and row[1] else 2.5
            curr_reps = row[2] if row and row[2] else 0
            new_ivl, new_ease, new_reps, new_date = sm2_algorithm(quality, curr_ivl, curr_ease, curr_reps)
            s.execute(update(UserProgress).where(and_(UserProgress.user_id == user_id, UserProgress.question_id == question_id)).values(interval_days=new_ivl, ease_factor=new_ease, repetitions=new_reps, next_review=new_date, solved_at=datetime.now()))
            log = ActivityLog(user_id=user_id, question_id=question_id, action="reviewed", confidence_level=quality, time_spent_seconds=time_seconds)
            s.add(log)
            s.flush()
            task_payload = {"activity_id": log.id, "user_id": user_id, "q_id": question_id, "provider": provider}
            Redis.lpush("ai_analysis_queue", json.dumps(task_payload))
            return jsonify({"status": "success", "new_date": str(new_date)})
        except Exception as e:
            return jsonify({"error": "Server error! check again after few time"}), 500

# ── Profile ──
def getUserInfo(user_id, s):
    row = s.execute(select(User.id, User.name, User.username, User.phone_number, User.email).where(User.id == user_id)).mappings().first()
    if not row:
        return None
    return dict(row)

def getLogs(user_id, s):
    stmt = (select(Question.title.label("problem"), Concept.title.label("concept"), Question.difficulty, UserProgress.solved_at)
            .select_from(UserProgress).join(Question, UserProgress.question_id == Question.id).join(Concept, Question.concept_id == Concept.id)
            .where(UserProgress.user_id == user_id).order_by(UserProgress.solved_at.desc()).limit(15))
    logs_data = [dict(row) for row in s.execute(stmt).mappings().all()]
    today = datetime.now().date()
    for log in logs_data:
        difficulty = log.get('difficulty', '').lower()
        if difficulty == 'easy': log['color'] = 'success'
        elif difficulty == 'medium': log['color'] = 'warning'
        else: log['color'] = 'danger'
        solved_date = log['solved_at'].date()
        days_ago = (today - solved_date).days
        if days_ago == 0: log['date'] = "Today"
        elif days_ago == 1: log['date'] = "Yesterday"
        elif days_ago < 7: log['date'] = f"{days_ago} Days Ago"
        elif days_ago < 14: log['date'] = "1 Week Ago"
        elif days_ago < 30: log['date'] = f"{days_ago // 7} Weeks Ago"
        else: log['date'] = solved_date.strftime("%b %d, %Y")
        del log['solved_at']
    return logs_data

@app.route('/api/profile')
def api_profile():
    user_id = session.get('user_id')
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        total_solved, streak = getStreak(user_id, s)
        userinfo = getUserInfo(user_id, s)
        userLogs = getLogs(user_id, s)
    if not userinfo:
        return jsonify({"error": "User not found"}), 404
    data = {"user": {"name": userinfo['name'], "username": userinfo["username"], "email": userinfo["email"], "streak": streak}, "logs": userLogs}
    return jsonify(data)

@app.route('/api/change-password', methods=['POST'])
def change_password():
    user_id = session.get('user_id')
    if 'user_id' not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    if not current_password or not new_password:
        return jsonify({"error": "Both fields are required."}), 400
    try:
        with get_session() as s:
            user = s.execute(select(User.userpassword).where(User.id == user_id)).mappings().first()
            if not user:
                return jsonify({"error": "User not found"}), 404
            current_db_password = user['userpassword']
            if not current_db_password:
                return jsonify({"error": "This account is linked with an external provider and does not have a password."}), 400
            
            is_valid = False
            if current_db_password.startswith('scrypt:') or current_db_password.startswith('pbkdf2:'):
                is_valid = check_password_hash(current_db_password, current_password)
            else:
                is_valid = (current_db_password == current_password)
            if not is_valid:
                return jsonify({"error": "Incorrect current password"}), 401
            s.execute(update(User).where(User.id == user_id).values(userpassword=generate_password_hash(new_password)))
            return jsonify({"success": True, "message": "Password updated securely!"})
    except Exception as e:
        _log.exception("Change password error")
        return jsonify({"error": "Server error. Could not update password."}), 500

# ── Consistency ──
@app.route('/api/consistency')
def api_consistency():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        try:
            stats = s.execute(select(
                func.count(func.distinct(func.date(ActivityLog.created_at))).label("active_days"),
                func.count().filter(ActivityLog.action == 'solved').label("solves"),
                func.count().filter(ActivityLog.action == 'reviewed').label("reviews"),
            ).where(and_(ActivityLog.user_id == user_id, ActivityLog.created_at >= datetime.now() - timedelta(days=30)))).first()
            active_days = stats.active_days or 0
            solves = stats.solves or 0
            reviews = stats.reviews or 0
            habit_score = min(50, (active_days / 20.0) * 50)
            discipline_score = 0
            if solves > 0: discipline_score = min(50, (reviews / (solves * 0.5)) * 50)
            elif reviews > 0: discipline_score = 50
            score = round(habit_score + discipline_score)
            return jsonify({"score": score, "active_days": active_days, "solves": solves, "reviews": reviews}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

# ── Chat History ──
@app.route('/api/chat_history/<int:question_id>', methods=['GET'])
def get_chat_history(question_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        try:
            latest_thread = s.scalar(select(ChatMessage.thread_id).where(and_(ChatMessage.user_id == user_id, ChatMessage.question_id == question_id)).order_by(ChatMessage.created_at.desc()).limit(1))
            if not latest_thread:
                return jsonify({"history": []}), 200
            rows = s.execute(select(ChatMessage.role, ChatMessage.content, ChatMessage.thread_id).where(ChatMessage.thread_id == latest_thread).order_by(ChatMessage.created_at.asc())).mappings().all()
            return jsonify({"history": [dict(r) for r in rows]}), 200
        except Exception as e:
            return jsonify({"error": "Failed to fetch history"}), 500

def fetch_session_transcript(user_id, q_id):
    try:
        with get_session() as s:
            rows = s.execute(select(ChatMessage.role, ChatMessage.content).where(and_(ChatMessage.user_id == user_id, ChatMessage.question_id == q_id)).order_by(ChatMessage.id.asc())).all()
        transcript = []
        for role, content in rows:
            if role == 'user': transcript.append(HumanMessage(content=content))
            else: transcript.append(AIMessage(content=content))
        return transcript
    except Exception:
        return []

# ── Insights ──
def get_skill_matrix_stats(user_id):
    with get_session() as s:
        rows = s.execute(select(Concept.title.label("concept_title"), func.count(ActivityLog.id).label("solved_count"), func.avg(ActivityLog.ai_bifurcated_score).label("avg_logic"), func.avg(ActivityLog.clarity_of_thought).label("avg_clarity"), func.avg(ActivityLog.confidence_level).label("avg_confidence"))
            .select_from(ActivityLog).join(Question, ActivityLog.question_id == Question.id).join(Concept, Question.concept_id == Concept.id)
            .where(ActivityLog.user_id == user_id).group_by(Concept.title)).all()
    formatted = []
    for r in rows:
        avg_logic = float(r[2] or 0); avg_clarity = float(r[3] or 0); avg_confidence = float(r[4] or 0)
        composite = (avg_logic + avg_clarity + avg_confidence) / 3
        formatted.append({"label": r[0], "count": r[1], "mastery": round(composite * 20, 1), "clarity": round(avg_clarity * 20, 1)})
    return formatted

def get_concept_breakdown(user_id):
    with get_session() as s:
        try:
            rows = s.execute(select(Concept.title, Question.title, ActivityLog.time_spent_seconds, ActivityLog.confidence_level)
                .select_from(ActivityLog).join(Question, ActivityLog.question_id == Question.id).join(Concept, Question.concept_id == Concept.id)
                .where(ActivityLog.user_id == user_id).order_by(Concept.title, ActivityLog.created_at.desc())).all()
            grouped = {}
            for concept, q_title, time_sec, conf in rows:
                concept_name = concept or "Uncategorized"; question_name = q_title or "Unknown Question"
                safe_time = int(time_sec) if time_sec is not None else 0
                safe_conf = float(conf) if conf is not None else 0.0
                if concept_name not in grouped: grouped[concept_name] = []
                mins = safe_time // 60
                grouped[concept_name].append({"title": question_name, "time": f"{mins}m" if mins > 0 else "< 1m", "autonomy": f"{int(safe_conf * 20)}%"})
            return grouped
        except Exception:
            return {}

@app.route('/api/insights/matrix', methods=['GET'])
def get_insights_data():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"status": "success", "matrix_stats": get_skill_matrix_stats(user_id), "concept_history": get_concept_breakdown(user_id)})

@app.route('/api/insights/ai-summary', methods=['POST'])
def get_ai_summary():
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    try:
        stats = get_skill_matrix_stats(user_id)
        data = request.get_json()
        api_key = Redis.hget(f"user:{session['user_id']}", "api_key")
        provider = data.get("provider")
        decrypted_key = decrypt_key(api_key)
        if not stats:
            return jsonify({"diagnostic": "You need to solve some problems before I can analyze your logic patterns.", "predictor": "Start your journey. Complete at least 3 problems to unlock your interview predictor."})
        stats_str = ", ".join([f"{s['label']}: {s['mastery']}% Mastery ({s['count']} solved)" for s in stats])
        coach = InsightCoach(decrypted_key, provider)
        ai_result = coach.get_summary(stats_str)
        if ai_result:
            return jsonify({"diagnostic": ai_result.diagnostic, "predictor": ai_result.predictor})
        raise Exception("AI returned empty.")
    except Exception:
        return jsonify({"diagnostic": "System currently analyzing your latest data structures. Check back soon.", "predictor": "Gathering more data points to formulate an accurate interview readiness score."})

# ── Roadmap ──
@app.route('/api/roadmap-data')
def roadmap_data():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        rows = s.execute(select(Concept.id, Concept.title, func.count(UserProgress.question_id).label("solved_count"))
            .select_from(Concept).outerjoin(Question, Concept.id == Question.concept_id)
            .outerjoin(UserProgress, and_(Question.id == UserProgress.question_id, UserProgress.user_id == user_id, UserProgress.is_solved.is_(True)))
            .group_by(Concept.id, Concept.title).order_by(Concept.id.asc())).mappings().all()
        return jsonify([dict(r) for r in rows])

# ── Similar ──
@app.route("/api/get_similar/<int:q_id>")
def get_similar(q_id):
    user_id = session.get("user_id")
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        try:
            concept_id = s.scalar(select(Question.concept_id).where(Question.id == q_id))
            rows = s.execute(select(Question.id, Question.title, Question.difficulty)
                .where(and_(Question.concept_id == concept_id, Question.id != q_id,
                    ~exists(select(1).where(and_(UserProgress.question_id == Question.id, UserProgress.user_id == user_id, UserProgress.is_solved.is_(True))))))
                .order_by(func.random()).limit(3)).mappings().all()
            return jsonify([dict(r) for r in rows])
        except Exception:
            return jsonify({"error": "Could not fetch recommendations"}), 500

# ── Set API Key ──
@app.route('/api/set-key', methods=['POST'])
def set_api_key():
    data = request.json
    api_key = data.get('api_key')
    provider = data.get('provider')
    user_id = session.get("user_id")
    if api_key:
        encrypted_val = encrypt_key(api_key)
        redis_key = f"user:{user_id}"
        Redis.hset(redis_key, mapping={"api_key": encrypted_val, "provider": provider})
        Redis.expire(redis_key, 86400)
        return jsonify({"status": "success"}), 200
    return jsonify({"status": "error", "message": "No key provided"}), 400

# ── Journey ──
@app.route('/api/user-journey', methods=['GET'])
def get_user_journey():
    user_id = session.get('user_id')
    if not user_id: return jsonify({"error": "Unauthorized"}), 401
    try:
        with get_session() as s:
            rows = s.execute(select(Concept.title, Concept.icon, func.min(UserProgress.solved_at).label("achieved_at"), func.count(UserProgress.question_id).label("questions_mastered"))
                .select_from(UserProgress).join(Question, UserProgress.question_id == Question.id).join(Concept, Question.concept_id == Concept.id)
                .where(UserProgress.user_id == user_id).group_by(Concept.id, Concept.title, Concept.icon).order_by(func.min(UserProgress.solved_at).asc())).all()
        return jsonify([{"title": r[0], "icon": r[1], "achieved_at": r[2].isoformat() if r[2] else None, "count": r[3]} for r in rows])
    except Exception:
        return jsonify({"error": "Internal Server Error"}), 500

# ═══════════════════════════════════════════
#  SPA CATCH-ALL ROUTES (serve Angular index.html)
# ═══════════════════════════════════════════
@app.get("/")
def spa_root():
    return _serve_spa_index()

_SPA_ROUTES = ["dashboard", "login", "loginpage", "questions/<path:rest>", "question/<path:rest>",
               "memory", "roadmap", "resource", "profile", "insights", "journey", "about"]

@app.route("/<path:path>")
def spa_catch_all(path):
    # Serve static assets from the Angular build
    safe = SPA_BROWSER_DIR / path
    if safe.is_file():
        return send_from_directory(SPA_BROWSER_DIR, path)
    return _serve_spa_index()
