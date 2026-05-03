"""Integration smoke tests for the Flask application."""

from werkzeug.security import generate_password_hash


def test_homepage_renders_spa_or_placeholder(client):
    resp = client.get("/")
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert b"<html" in resp.data.lower()


def test_api_v1_health(client):
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_loginpage_serves_spa_shell(client):
    """LEGACY PATH /loginpage is served by the Angular shell (same as other SPA routes)."""
    resp = client.get("/loginpage", follow_redirects=False)
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert b"<html" in resp.data.lower()


def test_spa_login_shell(client):
    resp = client.get("/login")
    assert resp.status_code in (200, 503)


def test_dashboard_api_returns_concepts(client, flask_app):
    from insightsdsa.db import get_session
    from insightsdsa.models import Concept, User

    with flask_app.app_context():
        with get_session() as s:
            u = User(
                name="Test",
                username="dash_user",
                email="dash_user@example.com",
                userpassword=generate_password_hash("pw"),
            )
            s.add(u)
            s.flush()
            uid = u.id
            s.add(Concept(title="Arrays", icon="\U0001f4ca"))
            s.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["user_name"] = "dash_user"

    resp = client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    data = resp.get_json()
    assert isinstance(data.get("concepts"), list)
    assert any(c.get("title") == "Arrays" for c in data["concepts"])
    assert "chart_data" in data and len(data["chart_data"]) == 3


def test_api_v1_concept_questions(client, flask_app):
    from insightsdsa.db import get_session
    from insightsdsa.models import Concept, Question, User

    with flask_app.app_context():
        with get_session() as s:
            u = User(
                name="T",
                username="q_user",
                email="q_user@example.com",
                userpassword=generate_password_hash("pw"),
            )
            s.add(u)
            s.flush()
            uid = u.id
            c = Concept(id=99, title="Graphs", icon="📊")
            s.add(c)
            s.flush()
            s.add(
                Question(
                    title="Sample Q",
                    difficulty="Easy",
                    link="https://example.com/p/1",
                    concept_id=99,
                    description="Desc",
                )
            )
            s.commit()

    with client.session_transaction() as sess:
        sess["user_id"] = uid

    resp = client.get("/api/v1/concepts/99/questions")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["concept"]["title"] == "Graphs"
    assert len(body["questions"]) == 1
    assert body["questions"][0]["title"] == "Sample Q"


def test_question_route_serves_spa_shell(client):
    """Problem workspace is handled by the Angular SPA."""
    resp = client.get("/question/1")
    assert resp.status_code in (200, 503)
    if resp.status_code == 200:
        assert b"<html" in resp.data.lower()
