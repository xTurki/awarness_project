"""Session expiry, logout and deactivation."""

from __future__ import annotations

from datetime import timedelta

from app.database import utcnow
from app.models.session import Session as SessionRow


def test_signing_out_ends_the_session(client, make_user, sign_in, csrf):
    user = make_user(email="a@example.com")
    token_id = sign_in(user)

    csrf_token = csrf("/")
    response = client.post("/logout", data={"csrf_token": csrf_token})
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    # Use /modules since / is public.
    assert client.get("/modules").status_code == 303, "protected pages must be unreachable"
    assert token_id is not None


def test_the_session_row_is_gone_after_signing_out(client, db, make_user, sign_in, csrf):
    user = make_user(email="a@example.com")
    token_id = sign_in(user)

    client.post("/logout", data={"csrf_token": csrf("/")})

    assert db.get(SessionRow, token_id) is None


def test_an_expired_session_is_refused_and_deleted(client, db, make_user, sign_in):
    user = make_user(email="a@example.com")
    token_id = sign_in(user)

    row = db.get(SessionRow, token_id)
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.add(row)
    db.commit()

    response = client.get("/modules")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
    assert db.get(SessionRow, token_id) is None, "an expired row is deleted on sight"


def test_a_stale_cookie_does_not_loop_between_login_and_dashboard(client, db, make_user, sign_in):
    """An expired cookie doesn't cause a redirect loop between /login and /."""
    user = make_user(email="a@example.com")
    token_id = sign_in(user)

    row = db.get(SessionRow, token_id)
    db.delete(row)
    db.commit()

    response = client.get("/login")
    assert response.status_code == 200, "a dead cookie must show the form, not redirect"
    assert "Sign in" in response.text


def test_a_valid_session_still_skips_the_sign_in_page(client, make_user, sign_in):
    sign_in(make_user(email="a@example.com"))

    response = client.get("/login")
    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_deactivation_refuses_an_existing_session_on_the_next_request(
    client, db, make_user, sign_in
):
    """Deactivation takes effect on the next request."""
    user = make_user(email="a@example.com")
    sign_in(user)
    assert client.get("/modules").status_code == 200

    user.is_active = False
    db.add(user)
    db.commit()

    # Use /modules since / is public.
    response = client.get("/modules")
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
