"""A mail outage is legible, and quick (FR-020, FR-021, SC-008).

The person is told plainly and left on the sign-in page — not sent to wait for a
code that never left.
"""

from __future__ import annotations

import time

import pytest

from app.services import auth_service
from app.services.email_service import EmailDeliveryFailed


@pytest.fixture()
def mail_is_down(monkeypatch):
    async def fail(to, subject, body):
        raise EmailDeliveryFailed("smtp: authentication failed")

    monkeypatch.setattr(auth_service.email_service, "send_email", fail)


def test_the_person_reaches_the_code_page_and_is_told_why(client, make_user, csrf, mail_is_down):
    """A mail outage slows sign-in; it does not stop it. The code was issued and
    is on the server console, so the person is carried to the page where they
    can use it, with the failure stated there (FR-020)."""
    make_user(email="a@example.com", password="demo-password")

    token = csrf("/login")
    response = client.post(
        "/login",
        data={"email": "a@example.com", "password": "demo-password", "csrf_token": token},
    )

    assert response.status_code == 303
    assert "mail=failed" in response.headers["location"]

    landed = client.get(response.headers["location"])
    assert landed.status_code == 200
    assert "could not be emailed" in landed.text
    assert "still issued" in landed.text


def test_no_session_is_issued_while_mail_is_down(client, make_user, csrf, mail_is_down):
    make_user(email="a@example.com", password="demo-password")
    client.post(
        "/login",
        data={
            "email": "a@example.com",
            "password": "demo-password",
            "csrf_token": csrf("/login"),
        },
    )
    assert client.cookies.get("session") is None


def test_the_failure_returns_well_inside_fifteen_seconds(client, make_user, csrf, mail_is_down):
    make_user(email="a@example.com", password="demo-password")

    started = time.monotonic()
    client.post(
        "/login",
        data={
            "email": "a@example.com",
            "password": "demo-password",
            "csrf_token": csrf("/login"),
        },
    )
    elapsed = time.monotonic() - started

    assert elapsed < 15, "the ten-second SMTP timeout is what bounds this"


def test_the_smtp_timeout_is_configured_and_bounded():
    from app.config import settings

    assert 0 < settings.smtp_timeout_seconds <= 10
