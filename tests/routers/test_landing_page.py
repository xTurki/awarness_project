"""The one page a visitor may see, and the line it draws.

`GET /` is the landing page to somebody with no session and the dashboard to
anybody with one. It is a single route on purpose: registering `GET /` twice
shadows the second silently, with no error to find, which is what Phase 3 moved
the route to prevent.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.database import utcnow
from app.main import app
from app.models.session import Session as SessionRow


# ------------------------------------------------------------------ structure


def test_the_root_is_still_registered_exactly_once():
    roots = [route for route in app.routes if route.path == "/"]
    assert len(roots) == 1, f"GET / is registered {len(roots)} times"


# -------------------------------------------------------------- the visitor


def test_a_visitor_gets_a_page_not_a_redirect(client):
    page = client.get("/")

    assert page.status_code == 200
    assert "Security Awareness Training" in page.text


def test_the_page_offers_a_way_in(client):
    page = client.get("/")

    assert 'href="/login"' in page.text
    assert "Log in" in page.text


def test_the_page_says_there_is_no_sign_up(client):
    """A visitor with no account needs to know that is the design, not a
    missing button. Nobody creates their own account (Phase 0 FR-002)."""
    page = client.get("/")

    assert "no sign-up" in page.text.lower()


def test_a_visitor_sees_no_navigation(client):
    """There is nowhere to go from here except in, and the shell belongs to
    people who are signed in."""
    page = client.get("/")

    assert "Notifications" not in page.text
    assert "Sign out" not in page.text


def test_nothing_behind_it_opened_up(client):
    """The landing page is the only thing a visitor may reach."""
    for path in ("/modules", "/notifications", "/admin/accounts"):
        response = client.get(path)
        assert response.status_code == 303, path
        assert response.headers["location"] == "/login"


# ------------------------------------------------------- somebody signed in


def test_a_signed_in_trainee_gets_their_dashboard(client, sign_in, make_user):
    sign_in(make_user(email="t@example.com", role="trainee"))
    page = client.get("/")

    assert page.status_code == 200
    assert "Your training" in page.text
    assert "Security Awareness Training" not in page.text


def test_a_signed_in_administrator_gets_the_module_dashboard(
    client, sign_in, make_user
):
    sign_in(make_user(email="a@example.com", role="administrator"))
    page = client.get("/")

    assert page.status_code == 200
    assert "Welcome" in page.text


def test_a_dead_cookie_shows_the_landing_page_rather_than_looping(
    client, db, sign_in, make_user
):
    """The bug the stale-cookie test guards, seen from the other side: a browser
    holding an expired cookie lands on a page, and the row is still deleted."""
    user = make_user(email="a@example.com")
    token_id = sign_in(user)

    row = db.get(SessionRow, token_id)
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.add(row)
    db.commit()

    page = client.get("/")

    assert page.status_code == 200
    assert "Security Awareness Training" in page.text
    assert db.get(SessionRow, token_id) is None, "an expired row is deleted on sight"


def test_choosing_a_password_still_comes_first(client, sign_in, make_user):
    """`optional_account` does not enforce it, so the route does. Without that
    check the dashboard would be the one page reachable before the password is
    set (Phase 0 FR-011)."""
    user = make_user(email="new@example.com", must_set_password=True)
    sign_in(user)

    response = client.get("/")

    assert response.status_code == 303
    assert response.headers["location"] == "/password/new"
