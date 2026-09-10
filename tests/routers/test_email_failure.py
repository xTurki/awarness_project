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


def test_the_person_is_told_and_stays_on_the_sign_in_page(client, make_user, csrf, mail_is_down):
    make_user(email="a@example.com", password="demo-password")

    token = csrf("/login")
    response = client.post(
        "/login",
        data={"email": "a@example.com", "password": "demo-password", "csrf_token": token},
    )

    assert response.status_code == 503
    assert "could not be sent" in response.text
    assert "signing in again" in response.text.lower()
    assert "location" not in response.headers, "must not redirect to the code page"


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
