"""Jinja templates: compile-time checks (legacy HTML; primary UI is Angular SPA)."""

from __future__ import annotations

import pytest

from insightsdsa.constants import PACKAGE_ROOT

_TEMPLATE_DIR = PACKAGE_ROOT / "templates"
_TEMPLATE_NAMES = sorted(p.name for p in _TEMPLATE_DIR.glob("*.html"))


@pytest.mark.parametrize("name", _TEMPLATE_NAMES)
def test_template_compiles_in_flask_jinja_env(name, flask_app):
    """Every packaged HTML template loads in the real Flask Jinja environment (includes, filters)."""
    with flask_app.app_context():
        with flask_app.test_request_context("/"):
            flask_app.jinja_env.get_template(name)


def test_questions_template_render(flask_app):
    from flask import render_template

    with flask_app.app_context():
        with flask_app.test_request_context("/"):
            html = render_template("questions.html", concept_id=42)
    assert "Practice Problems" in html
    assert "Undefined" not in html


def test_retention_template_render(flask_app):
    from flask import render_template

    with flask_app.app_context():
        with flask_app.test_request_context("/"):
            queue_item = {
                "question_id": 99,
                "question_title": "Two Sum",
                "question_link": "https://example.com/p/1",
                "concept_title": "Hashing",
                "days_interval": 3,
            }
            html = render_template(
                "retention.html",
                queue=[queue_item],
                stats=[{"name": "Arrays", "solved": 1, "signal": 2}],
            )
    assert "Two Sum" in html
    assert "Hashing" in html
    assert "Arrays" in html
    assert "Memory Retention" in html
