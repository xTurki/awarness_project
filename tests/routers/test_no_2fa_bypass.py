"""There is no way past the second factor (FR-014).

An absence test: it asserts that nothing exists, which is the only way a
requirement phrased as "MUST NOT provide any way" can be checked at all.
"""

from __future__ import annotations

import pytest

from app.main import app
from app.services import auth_service
from seed import ACCOUNTS, SEED_PASSWORD


@pytest.fixture()
def sent(monkeypatch):
    captured: list[str] = []

    async def fake_send(to, subject, body):
        for line in body.splitlines():
            if "Your sign-in code is:" in line:
                captured.append(line.split(":")[1].strip())

    monkeypatch.setattr(auth_service.email_service, "send_email", fake_send)
    return captured


def test_a_correct_password_alone_reaches_nothing(client, make_user, csrf, sent):
    make_user(email="a@example.com", password="demo-password")

    token = csrf("/login")
    client.post(
        "/login",
        data={"email": "a@example.com", "password": "demo-password", "csrf_token": token},
    )

    # A code was issued, but no session cookie was set and no page is reachable.
    assert client.cookies.get("session") is None
    assert client.get("/").status_code == 303
    assert client.get("/").headers["location"] == "/login"


def test_no_route_issues_a_session_without_the_code(client):
    """Only POST /login/verify creates a session. Nothing else may."""
    paths = {route.path for route in app.routes}
    assert "/login/verify" in paths

    unexpected = {
        path
        for path in paths
        if any(word in path for word in ("trust", "remember", "device", "bypass", "resend"))
    }
    assert unexpected == set(), f"unexpected sign-in shortcut routes: {unexpected}"


def test_seeded_accounts_are_exempt_from_the_password_change_not_from_the_code(
    db, client, csrf, sent
):
    """The one documented exemption is narrow, and this pins its edges."""
    from seed import seed

    seed(db)

    admin_email = ACCOUNTS[0][0]
    token = csrf("/login")
    response = client.post(
        "/login",
        data={"email": admin_email, "password": SEED_PASSWORD, "csrf_token": token},
    )

    # Step one succeeded, so the account is not required to change its password
    # first, but it still landed on the code page, not on the dashboard.
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login/verify")
    assert client.cookies.get("session") is None
    assert len(sent) == 1
