"""The two-step flow end to end, and the forced password change.

FR-011 and SC-012: an account whose password an administrator set cannot reach
any part of the platform beyond the choose-a-password step.
"""

from __future__ import annotations

import pytest

from app.services import auth_service


@pytest.fixture()
def sent(monkeypatch):
    captured: list[str] = []

    async def fake_send(to, subject, body):
        for line in body.splitlines():
            if "Your sign-in code is:" in line:
                captured.append(line.split(":")[1].strip())

    monkeypatch.setattr(auth_service.email_service, "send_email", fake_send)
    return captured


def test_password_then_code_reaches_the_dashboard(client, make_user, csrf, sent):
    make_user(email="a@example.com", password="demo-password")

    token = csrf("/login")
    first = client.post(
        "/login",
        data={"email": "a@example.com", "password": "demo-password", "csrf_token": token},
    )
    assert first.status_code == 303
    assert first.headers["location"].startswith("/login/verify")

    token = csrf("/login/verify?email=a@example.com")
    second = client.post(
        "/login/verify",
        data={"email": "a@example.com", "code": sent[0], "csrf_token": token},
    )
    assert second.status_code == 303
    assert second.headers["location"] == "/"
    assert "session" in second.cookies or client.cookies.get("session")

    landed = client.get("/")
    assert landed.status_code == 200
    assert "Welcome" in landed.text


def test_a_wrong_code_keeps_you_on_the_page(client, make_user, csrf, sent):
    make_user(email="a@example.com", password="demo-password")

    token = csrf("/login")
    client.post(
        "/login",
        data={"email": "a@example.com", "password": "demo-password", "csrf_token": token},
    )

    token = csrf("/login/verify?email=a@example.com")
    wrong = "000000" if sent[0] != "000000" else "111111"
    response = client.post(
        "/login/verify",
        data={"email": "a@example.com", "code": wrong, "csrf_token": token},
    )

    assert response.status_code == 401
    assert "not correct" in response.text


def test_a_post_without_a_csrf_token_is_refused(client, make_user):
    make_user(email="a@example.com", password="demo-password")
    response = client.post(
        "/login", data={"email": "a@example.com", "password": "demo-password"}
    )
    assert response.status_code == 403


def test_must_set_password_blocks_every_other_page(client, make_user, sign_in):
    user = make_user(email="new@example.com", must_set_password=True)
    sign_in(user)

    for path in ("/", "/admin/accounts"):
        response = client.get(path)
        assert response.status_code == 303
        assert response.headers["location"] == "/password/new"


def test_setting_a_password_clears_the_requirement(client, make_user, sign_in, csrf):
    user = make_user(email="new@example.com", must_set_password=True)
    sign_in(user)

    token = csrf("/password/new")
    response = client.post(
        "/password/new",
        data={"password": "a-good-password", "confirm": "a-good-password", "csrf_token": token},
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"

    assert client.get("/").status_code == 200


def test_mismatched_confirmation_is_refused(client, make_user, sign_in, csrf):
    user = make_user(email="new@example.com", must_set_password=True)
    sign_in(user)

    token = csrf("/password/new")
    response = client.post(
        "/password/new",
        data={"password": "a-good-password", "confirm": "different-password", "csrf_token": token},
    )
    assert response.status_code == 400
    assert "do not match" in response.text
