"""Playwright smoke tests: public pages, auth gate, logged-in navigation (Angular SPA)."""

from __future__ import annotations

import pytest

from insightsdsa.seed_e2e_user import E2E_PASSWORD, E2E_USERNAME


def _expect_ok(page, path: str) -> None:
    r = page.goto(path)
    assert r is not None and r.ok, f"{path} -> {r.status if r else 'no response'}"


def test_public_pages(page):
    for path in ("/", "/login", "/about"):
        _expect_ok(page, path)


def test_dashboard_redirects_when_logged_out(page):
    page.goto("/dashboard")
    page.wait_for_url("**/login**")
    assert "login" in page.url.lower()


def test_login_and_all_main_pages(page):
    page.goto("/login")
    page.fill("#login-user", E2E_USERNAME)
    page.fill("#login-pass", E2E_PASSWORD)
    page.click("#loginbtn")
    page.wait_for_url("**/dashboard**")

    for path in (
        "/dashboard",
        "/memory",
        "/roadmap",
        "/resource",
        "/profile",
        "/journey",
        "/insights",
        "/questions/1",
        "/question/1",
        "/about",
    ):
        _expect_ok(page, path)
