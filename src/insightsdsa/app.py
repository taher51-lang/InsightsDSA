from datetime import date, datetime, timedelta, timezone
import logging
import warnings
from pathlib import Path

# Authlib registers ``simplefilter("always", AuthlibDeprecationWarning)`` and still imports deprecated
# ``authlib.jose`` for Google OAuth until v2; suppress only that notice (multiline message).
from authlib.deprecate import AuthlibDeprecationWarning

warnings.filterwarnings(
    "ignore",
    message=r"(?s).*authlib\.jose module is deprecated.*",
    category=AuthlibDeprecationWarning,
)

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import safe_join
from sqlalchemy import (
    and_,
    case,
    delete,
    distinct,
    exists,
    func,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.flask_client import OAuth
from flask_wtf.csrf import CSRFProtect
from langchain_core.messages import AIMessage,HumanMessage
import traceback
from logging.handlers import RotatingFileHandler 
import json
from werkzeug.middleware.proxy_fix import ProxyFix
from cryptography.fernet import Fernet
import redis

from .analyst_bot import InsightCoach
from .config import settings
from .constants import PACKAGE_ROOT, PROJECT_ROOT
from .dashboard_data import build_dashboard_payload
from .retention_data import build_retention_payload
from .db import SessionLocal, get_dialect_name, get_session
from .init_db import ensure_user_progress_sm2_columns
from .models import ActivityLog, ChatMessage, Concept, Question, User, UserProgress
from .sm2 import sm2_algorithm

_log = logging.getLogger(__name__)

# Redis: stores per-user API keys (hash ``user:<id>``) and the ``ai_analysis_queue`` list for the worker.
# Production should set REDIS_URL. For local dev without a server, set INSIGHTSDSA_USE_MEMORY_REDIS=1.
if settings.use_memory_redis:
    import fakeredis

    Redis = fakeredis.FakeStrictRedis(decode_responses=True)
    _log.info(
        "Redis: using in-memory fakeredis (INSIGHTSDSA_USE_MEMORY_REDIS=1). "
        "Queue/worker state is not visible to other processes."
    )
elif settings.redis_url:
    Redis = redis.from_url(settings.redis_url, decode_responses=True)
    _log.info("Redis: connected via REDIS_URL.")
else:
    Redis = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password,
        decode_responses=True,
    )
    _log.info(
        "Redis: connecting to %s:%s (set REDIS_URL or INSIGHTSDSA_USE_MEMORY_REDIS=1).",
        settings.redis_host,
        settings.redis_port,
    )
if not settings.encryption_key:
    raise RuntimeError(
        "ENCRYPTION_KEY must be set in the environment (Fernet-compatible key)."
    )
cipher_suite = Fernet(settings.encryption_key)
app = Flask(
    __name__,
    template_folder=str(PACKAGE_ROOT / "templates"),
    static_folder=str(PACKAGE_ROOT / "static"),
)
app.secret_key = settings.flask_secret_key

_chatbot = None


def _get_chatbot():
    global _chatbot
    if _chatbot is None:
        from . import ai_bot_backend as _ab

        _chatbot = _ab.chatbot
    return _chatbot


# Setup Production Logging
_log_dir = Path(PROJECT_ROOT) / settings.log_dir
_log_dir.mkdir(parents=True, exist_ok=True)
_log_path = _log_dir / settings.log_file
file_handler = RotatingFileHandler(
    str(_log_path),
    maxBytes=settings.log_max_bytes,
    backupCount=settings.log_backup_count,
)
file_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
app.logger.info('LogicLens startup')

try:
    ensure_user_progress_sm2_columns()
except Exception as exc:
    app.logger.exception("ensure_user_progress_sm2_columns failed: %s", exc)

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

# --- SPA (Angular): built UI lives under ``frontend/dist/insightsdsa-ui/browser`` ---
SPA_BROWSER_DIR = PROJECT_ROOT / "frontend" / "dist" / "insightsdsa-ui" / "browser"
SPA_INDEX_FILE = SPA_BROWSER_DIR / "index.html"
SPA_LOGIN_PATH = "/login"

# If the browser asks for a real file (favicon, chunk, font) and it is missing from
# the Angular output, return 404 — never the SPA HTML shell (wrong Content-Type).
_SPA_MISSING_FILE_EXTS = (
    ".ico",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".avif",
    ".bmp",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".js",
    ".mjs",
    ".css",
    ".map",
)


def _path_looks_like_asset_file(path: str) -> bool:
    lower = path.lower()
    return any(lower.endswith(ext) for ext in _SPA_MISSING_FILE_EXTS)


app.logger.info(
    "SPA: index=%s exists=%s (PROJECT_ROOT=%s) app.py=%s",
    SPA_INDEX_FILE,
    SPA_INDEX_FILE.is_file(),
    PROJECT_ROOT,
    Path(__file__).resolve(),
)
if not SPA_INDEX_FILE.is_file():
    app.logger.warning(
        "Angular bundle missing. From repo root run: cd frontend && npm install && npm run build"
    )


def _serve_spa_index():
    if not SPA_INDEX_FILE.is_file():
        return jsonify(
            {
                "error": "SPA bundle not found",
                "hint": "Run: cd frontend && npm install && npm run build",
            }
        ), 503
    return send_from_directory(SPA_BROWSER_DIR, "index.html")


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
    return jsonify(
        {
            "authenticated": True,
            "user_id": session["user_id"],
            "user_name": session.get("user_name"),
            "email": session.get("user_email"),
            "profile_pic": session.get("profile_pic"),
        }
    )


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


@app.get("/api/v1/concepts/<int:concept_id>/questions")
def api_v1_concept_questions(concept_id):
    """Concept metadata plus ordered questions for the Angular problem list."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        with get_session() as s:
            crow = s.execute(
                select(Concept.id, Concept.title, Concept.icon).where(
                    Concept.id == concept_id
                )
            ).first()
            if not crow:
                return jsonify({"error": "Concept not found"}), 404
            concept = {
                "id": int(crow[0]),
                "title": str(crow[1] or ""),
                "icon": str(crow[2] or ""),
            }
            solved_exists = exists(
                select(1).where(
                    and_(
                        UserProgress.question_id == Question.id,
                        UserProgress.user_id == user_id,
                    )
                )
            )
            stmt = (
                select(
                    Question.id,
                    Question.title,
                    Question.difficulty,
                    Question.link,
                    solved_exists.label("is_solved"),
                )
                .where(Question.concept_id == concept_id)
            )
            questions = []
            for row in s.execute(stmt).mappings().all():
                d = dict(row)
                d["is_solved"] = bool(d["is_solved"])
                questions.append(d)
            difficulty_map = {"Easy": 1, "Medium": 2, "Hard": 3}
            questions.sort(key=lambda x: difficulty_map.get(x["difficulty"], 4))
        return jsonify({"concept": concept, "questions": questions})
    except Exception:
        _log.exception("api_v1_concept_questions")
        return jsonify({"error": "Database error"}), 500


@app.get("/")
def spa_root():
    return _serve_spa_index()


@app.get("/loginpage", endpoint="LoginPage")
def loginpage_legacy_redirect():
    return redirect(SPA_LOGIN_PATH, code=301)

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
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url=settings.google_openid_metadata_url,
    client_kwargs={"scope": "openid email profile"},
)

# 1. THE TRIGGER: Send user to Google
@app.route('/login/google')
def login_google():
    if not settings.google_client_id or not settings.google_client_secret:
        flash(
            "Google sign-in is not configured. Set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET in the environment."
        )
        return redirect(SPA_LOGIN_PATH)
    # Must match an "Authorized redirect URI" in Google Cloud Console (see GOOGLE_REDIRECT_URI).
    redirect_uri = settings.google_redirect_uri or url_for(
        "google_callback", _external=True
    )
    return google.authorize_redirect(redirect_uri)

# 2. THE RECEIVER: Catch the data coming back
@app.route('/login/callback')
def google_callback():
    try:
        token = google.authorize_access_token()
    except OAuthError as exc:
        app.logger.warning("Google OAuth error: %s %s", exc.error, exc.description)
        flash(
            exc.description
            or exc.error
            or "Google sign-in was cancelled or failed. Please try again."
        )
        return redirect(SPA_LOGIN_PATH)

    user_info = token.get("userinfo")
    if user_info is None:
        try:
            user_info = google.userinfo(token=token)
        except Exception:
            app.logger.exception(
                "Google login: no userinfo on token and userinfo endpoint failed"
            )
            flash(
                "Could not read your Google profile (missing id_token or userinfo). "
                "Try again, or contact support if this persists."
            )
            return redirect(SPA_LOGIN_PATH)

    email = user_info.get("email")
    if not email:
        flash("Google did not return an email for this account.")
        return redirect(SPA_LOGIN_PATH)

    g_id = user_info.get("sub")
    if not g_id:
        flash("Google did not return a user identifier for this account.")
        return redirect(SPA_LOGIN_PATH)
    full_name = user_info.get("name") or "Explorer"
    first_name = (full_name.split() or ["Explorer"])[0]
    pic = user_info.get("picture") or ""

    with get_session() as s:
        existing_id = s.scalar(select(User.id).where(User.email == email))
        if existing_id:
            s.execute(
                update(User)
                .where(User.email == email)
                .values(google_id=g_id, profile_pic=pic)
            )
            user_id = existing_id
        else:
            u = User(
                username=first_name,
                name=full_name,
                email=email,
                google_id=g_id,
                profile_pic=pic,
            )
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
            result = (
                s.execute(
                    select(
                        User.id,
                        User.username,
                        User.name,
                        User.userpassword,
                        User.google_id,
                    ).where(User.username == username)
                )
                .mappings()
                .first()
            )
            if not result:
                return jsonify({"error": "Invalid Credentials"}), 401
            if result["userpassword"] is None and result["google_id"] is not None:
                return jsonify(
                    {
                        "error": "This account is linked with Google. Please use the 'Continue with Google' button."
                    }
                ), 403
            current_db_password = result["userpassword"]
            is_valid = False
            needs_upgrade = False
            if current_db_password.startswith("scrypt:") or current_db_password.startswith("pbkdf2:"):
                is_valid = check_password_hash(current_db_password, userpass)
            else:
                is_valid = current_db_password == userpass
                if is_valid:
                    needs_upgrade = True
            if not is_valid:
                return jsonify({"error": "Invalid Credentials"}), 401
            if needs_upgrade:
                new_hashed_password = generate_password_hash(userpass)
                s.execute(
                    update(User)
                    .where(User.id == result["id"])
                    .values(userpassword=new_hashed_password)
                )
                print(f"Security Upgrade Complete: Hashed password for user '{username}'")
            session["user_id"] = result["id"]
            session["user_name"] = result["username"]
            print(result["username"])
            if result["name"]:
                return jsonify({"message": "Login successful", "name": result["name"]}), 200
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
        with get_session() as s:
            u = User(
                name=name,
                username=username,
                email=useremail,
                userpassword=hashed_password,
            )
            s.add(u)
            s.flush()
            session["user_id"] = u.id
            session["user_name"] = u.username
            return jsonify({"message": "Registration Successful!"}), 201

    except IntegrityError:
        return jsonify({"error": "Username or Email already exists!"}), 409

    except Exception as e:
        print("Database Error:", e)
        return jsonify({"error": "Server error. Please try again."}), 500
@app.route("/dashboard")
def dashboard():
    return _serve_spa_index()


def getStreak(user_id, s):
    total_solved = (
        s.scalar(
            select(func.count())
            .select_from(UserProgress)
            .where(
                and_(
                    UserProgress.user_id == user_id,
                    UserProgress.is_solved.is_(True),
                )
            )
        )
        or 0
    )

    solved_rows = s.scalars(
        select(UserProgress.solved_at).where(
            and_(
                UserProgress.user_id == user_id,
                UserProgress.solved_at.isnot(None),
            )
        )
    ).all()
    active_dates = {dt.date() for dt in solved_rows if dt is not None}
    

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
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        total_solved, streak = getStreak(user_id, s)
        return jsonify({"total_solved": total_solved, "streak": streak})

@app.route("/questions/<int:concept_id>")
def questions_page(concept_id):
    del concept_id  # client route; data from ``/api/get_questions/<id>``
    return _serve_spa_index()
@app.route("/api/get_questions/<int:concept_id>")
def get_questions_api(concept_id):
    user_id = session.get('user_id')
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        solved_exists = exists(
            select(1).where(
                and_(
                    UserProgress.question_id == Question.id,
                    UserProgress.user_id == user_id,
                )
            )
        )
        stmt = (
            select(
                Question.id,
                Question.title,
                Question.difficulty,
                Question.link,
                solved_exists.label("is_solved"),
            )
            .where(Question.concept_id == concept_id)
        )
        questions = []
        for row in s.execute(stmt).mappings().all():
            d = dict(row)
            d["is_solved"] = bool(d["is_solved"])
            questions.append(d)
        difficulty_map = {"Easy": 1, "Medium": 2, "Hard": 3}
        questions.sort(key=lambda x: difficulty_map.get(x["difficulty"], 4))
    return jsonify(questions)

@app.route("/api/get_question_details/<int:q_id>")
def get_question_details(q_id):
    user_id = session.get("user_id")
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    try:
        with get_session() as s:
            solved_exists = exists(
                select(1).where(
                    and_(
                        UserProgress.question_id == Question.id,
                        UserProgress.user_id == user_id,
                    )
                )
            )
            stmt = (
                select(
                    Question.id,
                    Question.title,
                    Question.description,
                    Question.difficulty,
                    Question.link,
                    solved_exists.label("is_solved"),
                )
                .where(Question.id == q_id)
            )
            data = s.execute(stmt).mappings().first()
            print(data)
            if not data:
                return jsonify({"error": "Question not found"}), 404
            out = dict(data)
            out["is_solved"] = bool(out["is_solved"])
            return jsonify(out)
    except Exception:
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
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.get_json()
    q_id = data.get("question_id")
    confidence = data.get("confidence")
    time_spent = data.get("time_spent")
    # api_key = data.get("user_api_key")
    provider = data.get("provider")
    s = SessionLocal()
    try:
        exists = s.scalar(
            select(UserProgress.user_id).where(
                and_(
                    UserProgress.user_id == user_id,
                    UserProgress.question_id == q_id,
                )
            )
        )
        if exists:
            s.execute(
                delete(UserProgress).where(
                    and_(
                        UserProgress.user_id == user_id,
                        UserProgress.question_id == q_id,
                    )
                )
            )
            s.execute(
                delete(ActivityLog).where(
                    and_(
                        ActivityLog.user_id == user_id,
                        ActivityLog.question_id == q_id,
                        ActivityLog.action == "solved",
                    )
                )
            )
            action = "reset"
        else:
            tomorrow = date.today() + timedelta(days=1)
            action = "solved"
            s.add(
                UserProgress(
                    user_id=user_id,
                    question_id=q_id,
                    solved_at=datetime.now(),
                    interval_days=1,
                    ease_factor=2.5,
                    repetitions=1,
                    next_review=tomorrow,
                    is_solved=True,
                )
            )
            log = ActivityLog(
                user_id=user_id,
                question_id=q_id,
                action="solved",
                confidence_level=confidence,
                time_spent_seconds=time_spent,
            )
            s.add(log)
            s.flush()
            activity_id = log.id
            task_payload = {
                "activity_id": activity_id,
                "user_id": user_id,
                "q_id": q_id,
                "provider": provider,
            }
            Redis.lpush("ai_analysis_queue", json.dumps(task_payload))
        s.commit()
        return jsonify({"status": "success", "action": action})
    except Exception as e:
        s.rollback()
        print("Error: Server error")
        return jsonify({"error": str(e)}), 500
    finally:
        s.close()

@app.route("/api/ask_ai", methods=["POST"])
def ask_AI():
    user_id = session.get("user_id")
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        data = request.get_json()
        query = data.get("query")
        question_id = data.get("question_id")
        thread_id = data.get("thread_id")
        safe_thread_id = f"user_{user_id}_{thread_id}"
        provider = data.get("provider")
        desc = s.scalar(select(Question.description).where(Question.id == question_id))
        question_description = desc if desc else "No description Provided"
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
        response = _get_chatbot().invoke({
            'messages': [HumanMessage(content=query)],
            'question': question_description,
            'user_api_key': decrypt_key(encrypted_key), 
            'provider': provider          
        }, config=config)
        # 4. Extract the clean text response
        ai_response = response['messages'][-1].content
        # 5. Database logging (best-effort; AI response still returned on failure)
        log_s = SessionLocal()
        try:
            log_s.add(
                ChatMessage(
                    user_id=user_id,
                    question_id=question_id,
                    thread_id=thread_id,
                    role="user",
                    content=query,
                )
            )
            log_s.add(
                ChatMessage(
                    user_id=user_id,
                    question_id=question_id,
                    thread_id=thread_id,
                    role="assistant",
                    content=ai_response,
                )
            )
            log_s.commit()
        except Exception as db_err:
            log_s.rollback()
            print("Failed to save messages to DB:", db_err)
        finally:
            log_s.close()
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
@app.route("/memory")
def memory():
    return _serve_spa_index()


@app.route('/api/review', methods=['POST'])
def api_review():
    # 1. Security Check
    user_id = session.get('user_id')
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    # 2. Get Data from Frontend
    data = request.get_json()
    question_id = data.get('question_id')
    quality = int(data.get('quality', 0))  # 0, 3, 4, 5
    # Get time from 'time_spent' (matching the JS payload)
    time_seconds = int(data.get('time_spent', 0))
    provider = data.get("provider")
    s = SessionLocal()
    try:
        record = s.execute(
            select(
                UserProgress.interval_days,
                UserProgress.ease_factor,
                UserProgress.repetitions,
            ).where(
                and_(
                    UserProgress.user_id == user_id,
                    UserProgress.question_id == question_id,
                )
            )
        ).first()
        curr_ivl = record[0] if record and record[0] is not None else 1
        curr_ease = record[1] if record and record[1] is not None else 2.5
        curr_reps = record[2] if record and record[2] is not None else 0
        new_ivl, new_ease, new_reps, new_date = sm2_algorithm(
            quality, curr_ivl, curr_ease, curr_reps
        )
        print("")
        s.execute(
            update(UserProgress)
            .where(
                and_(
                    UserProgress.user_id == user_id,
                    UserProgress.question_id == question_id,
                )
            )
            .values(
                interval_days=new_ivl,
                ease_factor=new_ease,
                repetitions=new_reps,
                next_review=new_date,
                solved_at=func.now(),
            )
        )
        log = ActivityLog(
            user_id=user_id,
            question_id=question_id,
            action="reviewed",
            confidence_level=quality,
            time_spent_seconds=time_seconds,
        )
        s.add(log)
        s.flush()
        activity_id = log.id
        task_payload = {
            "activity_id": activity_id,
            "user_id": user_id,
            "q_id": question_id,
            "provider": provider,
        }
        Redis.lpush("ai_analysis_queue", json.dumps(task_payload))
        s.commit()
        return jsonify({"status": "success", "new_date": str(new_date)})
    except Exception:
        s.rollback()
        return jsonify({"error": "Server error! check again after few time"}), 500
    finally:
        s.close()
        

@app.route('/api/roadmap-data')
def roadmap_data():
    user_id = session.get('user_id')
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    with get_session() as s:
        stmt = (
            select(
                Concept.id,
                Concept.title,
                func.count(UserProgress.question_id).label("solved_count"),
            )
            .select_from(Concept)
            .outerjoin(Question, Concept.id == Question.concept_id)
            .outerjoin(
                UserProgress,
                and_(
                    Question.id == UserProgress.question_id,
                    UserProgress.user_id == user_id,
                    UserProgress.is_solved.is_(True),
                ),
            )
            .group_by(Concept.id, Concept.title)
            .order_by(Concept.id.asc())
        )
        concepts = [dict(r) for r in s.execute(stmt).mappings().all()]
    return jsonify(concepts)
@app.route('/roadmap')
def roadmap():
    return _serve_spa_index()


@app.route('/resource')
def resource():
    return _serve_spa_index()


@app.route('/profile')
def profile():
    return _serve_spa_index()

def getUserInfo(user_id, s):
    user_row = (
        s.execute(
            select(
                User.id,
                User.name,
                User.username,
                User.phone_number,
                User.email,
            ).where(User.id == user_id)
        )
        .mappings()
        .first()
    )
    if not user_row:
        return None
    return dict(user_row)


def getLogs(user_id, s):
    stmt = (
        select(
            Question.title.label("problem"),
            Concept.title.label("concept"),
            Question.difficulty,
            UserProgress.solved_at,
        )
        .select_from(UserProgress)
        .join(Question, UserProgress.question_id == Question.id)
        .join(Concept, Question.concept_id == Concept.id)
        .where(UserProgress.user_id == user_id)
        .order_by(UserProgress.solved_at.desc())
        .limit(15)
    )
    logs_data = list(s.execute(stmt).mappings().all())
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
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    with get_session() as s:
        total_solved, streak = getStreak(user_id, s)
        userinfo = getUserInfo(user_id, s)
        userLogs = getLogs(user_id, s)
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
    if "user_id" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')
    if not current_password or not new_password:
        return jsonify({"error": "Both fields are required."}), 400
    try:
        with get_session() as s:
            row = s.execute(
                select(User.userpassword).where(User.id == user_id)
            ).first()
            if not row:
                return jsonify({"error": "User not found"}), 404
            current_db_password = row[0]
            if current_db_password and (
                current_db_password.startswith("scrypt:")
                or current_db_password.startswith("pbkdf2:")
            ):
                is_valid = check_password_hash(current_db_password, current_password)
            else:
                is_valid = current_db_password == current_password
            if not is_valid:
                return jsonify({"error": "Incorrect current password"}), 401
            hashed_new_password = generate_password_hash(new_password)
            s.execute(
                update(User)
                .where(User.id == user_id)
                .values(userpassword=hashed_new_password)
            )
            return jsonify(
                {"success": True, "message": "Password updated securely!"}
            )

    except Exception as e:
        # if con: con.rollback()
        print(f"Database error during password change: {e}")
        return jsonify({"error": "Server error. Could not update password."}), 500
        

@app.route('/journey')
def journey():
    return _serve_spa_index()


@app.route("/question/<int:q_id>")
def question_page(q_id):
    del q_id  # Angular ``QuestionWorkspaceComponent`` reads id from the route
    return _serve_spa_index()

@app.route("/api/get_similar/<int:q_id>")
def get_similar(q_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
        
    try:
        with get_session() as s:
            concept_sq = (
                select(Question.concept_id)
                .where(Question.id == q_id)
                .scalar_subquery()
            )
            solved_subq = select(UserProgress.question_id).where(
                and_(
                    UserProgress.user_id == user_id,
                    UserProgress.is_solved.is_(True),
                )
            )
            rand = func.rand() if get_dialect_name() == "mysql" else func.random()
            stmt = (
                select(Question.id, Question.title, Question.difficulty)
                .where(
                    and_(
                        Question.concept_id == concept_sq,
                        Question.id != q_id,
                        Question.id.notin_(solved_subq),
                    )
                )
                .order_by(rand)
                .limit(3)
            )
            similar_questions = [dict(r) for r in s.execute(stmt).mappings().all()]
            return jsonify(similar_questions)
    except Exception as e:
        print(f"Error fetching similar: {e}")
        return jsonify({"error": "Could not fetch recommendations"}), 500

app.config.update(
    SESSION_COOKIE_SAMESITE=settings.session_cookie_samesite,
    SESSION_COOKIE_SECURE=settings.session_cookie_secure,
    SESSION_COOKIE_HTTPONLY=settings.session_cookie_httponly,
    SESSION_COOKIE_NAME=settings.session_cookie_name,
)
@app.route('/api/consistency')
def api_consistency():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with get_session() as s:
            thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
            stmt = select(
                func.count(distinct(func.date(ActivityLog.created_at))).label(
                    "active_days"
                ),
                func.sum(
                    case((ActivityLog.action == "solved", 1), else_=0)
                ).label("solves"),
                func.sum(
                    case((ActivityLog.action == "reviewed", 1), else_=0)
                ).label("reviews"),
            ).where(
                and_(
                    ActivityLog.user_id == user_id,
                    ActivityLog.created_at >= thirty_days_ago,
                )
            )
            stats = s.execute(stmt).mappings().first()
            active_days = stats["active_days"] or 0
            solves = stats["solves"] or 0
            reviews = stats["reviews"] or 0
            habit_score = min(50, (active_days / 20.0) * 50)
            discipline_score = 0
            if solves > 0:
                discipline_score = min(50, (reviews / (solves * 0.5)) * 50)
            elif solves == 0 and reviews > 0:
                discipline_score = 50
            score = round(habit_score + discipline_score)
            return jsonify(
                {
                    "score": score,
                    "active_days": active_days,
                    "solves": solves,
                    "reviews": reviews,
                }
            ), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat_history/<int:question_id>', methods=['GET'])
def get_chat_history(question_id):
    # 1. Grab the user ID (Adjust this based on how your app handles logins!)
    user_id = session.get("user_id") 
    
    # If you don't have a login system yet for V1, you can temporarily hardcode this to test:
    # user_id = 1 

    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        with get_session() as s:
            latest_tid = (
                select(ChatMessage.thread_id)
                .where(
                    and_(
                        ChatMessage.user_id == user_id,
                        ChatMessage.question_id == question_id,
                    )
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(1)
                .scalar_subquery()
            )
            stmt = (
                select(ChatMessage.role, ChatMessage.content, ChatMessage.thread_id)
                .where(ChatMessage.thread_id == latest_tid)
                .order_by(ChatMessage.created_at.asc())
            )
            history = list(s.execute(stmt).mappings().all())
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
        with get_session() as s:
            rows = s.execute(
                select(ChatMessage.role, ChatMessage.content)
                .where(
                    and_(
                        ChatMessage.user_id == user_id,
                        ChatMessage.question_id == q_id,
                    )
                )
                .order_by(ChatMessage.id.asc())
            ).all()
        transcript = []
        for role, content in rows:
            if role == "user":
                transcript.append(HumanMessage(content=content))
            else:
                transcript.append(AIMessage(content=content))
        return transcript
    except Exception as e:
        print(f"Database Retrieval Error: {e}")
        return []


def get_skill_matrix_stats(user_id):
    with get_session() as s:
        stmt = (
            select(
                Concept.title.label("concept_title"),
                func.count(ActivityLog.id).label("solved_count"),
                func.avg(ActivityLog.ai_bifurcated_score).label("avg_logic"),
                func.avg(ActivityLog.clarity_of_thought).label("avg_clarity"),
                func.avg(ActivityLog.confidence_level).label("avg_confidence"),
            )
            .select_from(ActivityLog)
            .join(Question, ActivityLog.question_id == Question.id)
            .join(Concept, Question.concept_id == Concept.id)
            .where(ActivityLog.user_id == user_id)
            .group_by(Concept.id, Concept.title)
        )
        rows = s.execute(stmt).all()
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
    s = SessionLocal()
    try:
        stmt = (
            select(
                Concept.title.label("concept"),
                Question.title.label("q_title"),
                ActivityLog.time_spent_seconds,
                ActivityLog.confidence_level,
            )
            .select_from(ActivityLog)
            .join(Question, ActivityLog.question_id == Question.id)
            .join(Concept, Question.concept_id == Concept.id)
            .where(ActivityLog.user_id == user_id)
            .order_by(Concept.title, ActivityLog.created_at.desc())
        )
        rows = s.execute(stmt).all()
        grouped = {}
        for concept, q_title, time_sec, conf in rows:
            concept_name = concept if concept else "Uncategorized"
            question_name = q_title if q_title else "Unknown Question"
            safe_time = int(time_sec) if time_sec is not None else 0
            safe_conf = float(conf) if conf is not None else 0.0
            if concept_name not in grouped:
                grouped[concept_name] = []
            mins = safe_time // 60
            time_display = f"{mins}m" if mins > 0 else "< 1m"
            grouped[concept_name].append(
                {
                    "title": question_name,
                    "time": time_display,
                    "autonomy": f"{int(safe_conf * 20)}%",
                }
            )
        return grouped
    except Exception as e:
        print(f"💥 Error in get_concept_breakdown: {e}")
        return {}
    finally:
        s.close()

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
    return _serve_spa_index()

@app.route('/api/insights/ai-summary', methods=['POST'])
def get_ai_summary():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        # 1. Grab the exact same stats we use for the Radar Chart
        stats = get_skill_matrix_stats(user_id)
        data = request.get_json()

        api_key = Redis.hget(f"user:{session['user_id']}", "api_key")
        provider = data.get("provider")
        if not api_key:
            return jsonify({
                "diagnostic": "Add an API key in Profile to unlock AI insights.",
                "predictor": "Configure your provider key, then try again.",
            })
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
        with get_session() as s:
            stmt = (
                select(
                    Concept.title,
                    Concept.icon,
                    func.min(UserProgress.solved_at).label("achieved_at"),
                    func.count(UserProgress.question_id).label("questions_mastered"),
                )
                .select_from(UserProgress)
                .join(Question, UserProgress.question_id == Question.id)
                .join(Concept, Question.concept_id == Concept.id)
                .where(UserProgress.user_id == user_id)
                .group_by(Concept.id, Concept.title, Concept.icon)
                .order_by(func.min(UserProgress.solved_at).asc())
            )
            rows = s.execute(stmt).all()
        journey_data = []
        for row in rows:
            journey_data.append(
                {
                    "title": row[0],
                    "icon": row[1],
                    "achieved_at": row[2].isoformat() if row[2] else None,
                    "count": row[3],
                }
            )
        return jsonify(journey_data)
    except Exception as e:
        print(f"Journey API Error: {e}")
        return jsonify({"error": "Internal Server Error"}), 500
@app.route("/about")
def aboutus():
    return _serve_spa_index()


@app.get("/<path:spa_path>")
def spa_fallback(spa_path):
    """Serve built Angular assets or the SPA shell for client-side routes."""
    if spa_path.startswith("api/"):
        abort(404)
    if spa_path.startswith("static/"):
        return app.send_static_file(spa_path.removeprefix("static/"))
    if SPA_INDEX_FILE.is_file():
        asset = safe_join(str(SPA_BROWSER_DIR), spa_path)
        if asset is not None and Path(asset).is_file():
            return send_from_directory(SPA_BROWSER_DIR, spa_path)
        if _path_looks_like_asset_file(spa_path):
            abort(404)
    elif _path_looks_like_asset_file(spa_path):
        abort(404)
    return _serve_spa_index()


if __name__ == "__main__":
    app.run()