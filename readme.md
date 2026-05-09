# InsightsDSA

**Identify Patterns. Master Logic.**

InsightsDSA is a full-stack DSA learning platform that goes beyond problem tracking. It combines a multi-provider **AI Tutor**, a **Spaced Repetition** memory system (SM-2), and an **Insights Engine** that diagnoses your logic quality — not just whether you passed test cases.

> Built for engineers who refuse to just "grind" LeetCode.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                      NGINX (TLS)                        │
└──────────────────────┬──────────────────────────────────┘
                       │ uwsgi_pass
┌──────────────────────▼──────────────────────────────────┐
│              Flask API (uWSGI × 4 workers)              │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────┐  │
│  │  Auth/OAuth  │  │  REST Routes │  │  CSRF Protect │  │
│  └─────────────┘  └──────────────┘  └───────────────┘  │
│  ┌─────────────────────────────────────────────────────┐│
│  │         LangGraph Chatbot (PostgresSaver)           ││
│  │   Gemini 2.5 Flash │ GPT-4o Mini │ Grok-3          ││
│  └─────────────────────────────────────────────────────┘│
└─────┬───────────┬──────────────┬────────────────────────┘
      │           │              │
┌─────▼───┐ ┌────▼─────┐  ┌────▼──────┐  ┌──────────────┐
│ Postgres│ │  Redis   │  │  Angular  │  │ Background   │
│   (DB)  │ │ (BYOK +  │  │   SPA     │  │ Worker       │
│         │ │  Queue)  │  │ (SSR-ready│  │ (AI Analyst) │
└─────────┘ └──────────┘  └──────────┘  └──────────────┘
```

---

## Core Features

### 🤖 AI Problem Workstation
Split-screen workspace with a multi-provider AI tutor powered by [LangGraph](https://github.com/langchain-ai/langgraph). The tutor gives **hints only** — never direct answers — and maintains full conversation history via PostgreSQL-backed checkpointing.

**Supported providers** (BYOK — Bring Your Own Key):
| Provider | Model | Use Case |
|----------|-------|----------|
| Google Gemini | `gemini-2.5-flash` | Default — fast, cost-effective |
| OpenAI | `gpt-4o-mini` | Alternative reasoning style |
| xAI | `grok-3` | Experimental |

### 🔬 Insights Engine
A background worker processes every solved problem through a separate AI **Analyst** agent that evaluates:
- **Mastery Score** (0–5): Technical depth of your approach
- **Clarity Score** (0–5): Logical flow and communication quality

These scores feed into concept-level skill matrices and an **Interview Readiness Predictor** that names specific companies and weak areas.

### 🧠 Spaced Repetition (SM-2)
The [SM-2 algorithm](https://en.wikipedia.org/wiki/SuperMemo#Description_of_SM-2_algorithm) schedules review sessions based on your per-problem memory strength. Problems you struggle with surface more frequently; mastered ones fade into longer intervals.

### 🔒 BYOK Security Model
- API keys are **Fernet-encrypted** (AES-128-CBC) before storage
- Keys live in **Redis** with a 24-hour TTL — never persisted to disk
- The server never logs or exposes plaintext keys
- Users bring their own API keys — zero platform cost for AI features

### 📊 Visual Dashboards
- Concept roadmap with solve progress per topic
- Difficulty distribution charts (Easy / Medium / Hard)
- Streak tracking and consistency scoring
- Mastery timeline showing concept unlock progression
- Per-concept drill-down with time-spent and autonomy metrics

### 👤 Authentication
- **Google OAuth 2.0** (OpenID Connect) — one-click sign-in
- **Username/Password** — Werkzeug scrypt hashing with automatic legacy hash upgrade
- Session-based auth with CSRF protection (`flask-wtf`)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | Angular 19 · TypeScript · Bootstrap 5 |
| **Backend** | Python · Flask 3 · SQLAlchemy 2 (ORM) |
| **AI Framework** | LangChain · LangGraph · Pydantic structured output |
| **Database** | PostgreSQL (app data + LangGraph checkpoints) |
| **Cache / Queue** | Redis (encrypted key store + background task queue) |
| **Auth** | Google OAuth 2.0 · Authlib · Werkzeug |
| **Crypto** | Fernet (cryptography lib) |
| **Server** | uWSGI · Nginx (TLS via Let's Encrypt) |
| **Deployment** | Ansible (roles: postgres, redis, app, nginx) |
| **Testing** | Pytest · Playwright (E2E) |

---

## Project Structure

```
InsightsDSA/
├── src/insightsdsa/
│   ├── app.py              # Flask routes and API endpoints
│   ├── ai_bot_backend.py   # LangGraph chatbot with PostgresSaver
│   ├── analyst_bot.py      # AI Analyst + InsightCoach (structured output)
│   ├── worker.py           # Background Redis queue consumer
│   ├── sm2.py              # SM-2 spaced repetition algorithm
│   ├── models.py           # SQLAlchemy ORM models
│   ├── config.py           # Environment-driven configuration
│   ├── appinit.py          # Curriculum seeder (concepts + questions)
│   └── db.py               # Engine and session factory
├── frontend/
│   └── src/app/
│       ├── pages/           # Angular standalone components
│       │   ├── workspace/   # AI tutor split-screen
│       │   ├── dashboard/   # Progress overview
│       │   ├── insights/    # Skill matrix + AI summary
│       │   ├── retention/   # Spaced repetition queue
│       │   ├── roadmap/     # Concept progression map
│       │   ├── journey/     # Mastery timeline
│       │   └── profile/     # Settings + AI key config
│       ├── core/            # Guards, interceptors, AI key service
│       └── services/        # API service layer
├── ansible/                 # Full-stack deployment automation
│   ├── roles/
│   │   ├── postgres/        # Database provisioning
│   │   ├── redis/           # Cache server config
│   │   └── insightsdsa/     # App deploy, uWSGI, Nginx, TLS
│   └── inventory/
│       ├── dev.yml
│       └── production.yml
├── tests/                   # Pytest unit + integration tests
├── e2e/                     # Playwright browser tests
├── wsgi.py                  # uWSGI / Gunicorn entrypoint
└── pyproject.toml           # Python dependencies
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- Redis 6+

### Local Development

```bash
# 1. Clone
git clone https://github.com/taher51-lang/InsightsDSA.git
cd InsightsDSA

# 2. Backend
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"

# 3. Create .env (see .env.example or ansible/roles/insightsdsa/templates/env.j2)
cp .env.example .env   # then edit with your credentials

# 4. Initialize database
python -m insightsdsa.appinit

# 5. Start Flask API
python -m flask --app insightsdsa.app run --debug

# 6. Frontend (separate terminal)
cd frontend
npm install
ng serve
```

App runs at `http://localhost:4200` with the API proxied to port 5000.

### Production Deployment

```bash
# Ansible deploys the full stack: Postgres, Redis, uWSGI, Nginx + Let's Encrypt
ansible-playbook -i ansible/inventory/production.yml ansible/site.yml
```

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection (SQLAlchemy format) |
| `CHECKPOINT_DATABASE_URL` | PostgreSQL connection (raw psycopg format, for LangGraph) |
| `FLASK_SECRET_KEY` | Flask session signing key |
| `ENCRYPTION_KEY` | Fernet key for API key encryption |
| `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` | Redis connection |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Google OAuth credentials |
| `GOOGLE_REDIRECT_URI` | OAuth callback URL |
| `ADMIN_EMAILS` | Comma-separated list of admin email addresses |
| `FRONTEND_URL` | Frontend origin for redirects (dev: `http://localhost:4200`) |

---

## How It Works

```
User solves a problem
        │
        ├──▶ Mark solved → SM-2 schedules next review date
        │
        ├──▶ Task queued to Redis ──▶ Background Worker
        │                               │
        │                     Reads chat transcript
        │                     Calls AI Analyst (structured output)
        │                     Writes mastery_score + clarity_score
        │                     back to activity_log
        │
        └──▶ User opens Insights page
                    │
                    └──▶ Skill matrix aggregated from scores
                         AI Coach generates interview readiness prediction
```

---

## License

© 2026 InsightsDSA — Built by **Taher Rangwala**.