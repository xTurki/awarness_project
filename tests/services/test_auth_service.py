"""The code and credential cases, as a table.

Covers FR-013, FR-016, FR-017 and FR-018: two steps every time, a fixed lifetime,
single use, and a fresh sign-in replacing whatever was outstanding.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from app.database import utcnow
from app.services import auth_service


@pytest.fixture()
def sent(monkeypatch):
    """Capture the code instead of emailing it."""
    captured: list[str] = []

    async def fake_send(to, subject, body):
        for line in body.splitlines():
            if "Your sign-in code is:" in line:
                captured.append(line.split(":")[1].strip())

    monkeypatch.setattr(auth_service.email_service, "send_email", fake_send)
    return captured


def start(db, email, password):
    asyncio.run(auth_service.start_login(db, email, password))


def test_wrong_password_is_refused(db, make_user, sent):
    make_user(email="a@example.com", password="right-password")
    with pytest.raises(auth_service.InvalidCredentials):
        start(db, "a@example.com", "wrong-password")


def test_unknown_address_is_refused(db, sent):
    with pytest.raises(auth_service.InvalidCredentials):
        start(db, "nobody@example.com", "any-password")


def test_inactive_account_is_refused(db, make_user, sent):
    make_user(email="off@example.com", password="demo-password", is_active=False)
    with pytest.raises(auth_service.InactiveAccount):
        start(db, "off@example.com", "demo-password")


def test_correct_password_writes_both_code_columns(db, make_user, sent):
    user = make_user(email="a@example.com", password="demo-password")
    start(db, "a@example.com", "demo-password")
    db.refresh(user)

    assert user.login_code_hash is not None
    assert user.login_code_expires_at is not None
    assert len(sent) == 1 and len(sent[0]) == 6


def test_correct_code_clears_both_columns_and_returns_a_session(db, make_user, sent):
    user = make_user(email="a@example.com", password="demo-password")
    start(db, "a@example.com", "demo-password")

    row = auth_service.verify_code(db, "a@example.com", sent[0])
    db.refresh(user)

    assert row.user_id == user.id
    assert row.expires_at > row.created_at
    assert user.login_code_hash is None
    assert user.login_code_expires_at is None


def test_wrong_code_is_refused(db, make_user, sent):
    make_user(email="a@example.com", password="demo-password")
    start(db, "a@example.com", "demo-password")

    wrong = "000000" if sent[0] != "000000" else "111111"
    with pytest.raises(auth_service.CodeInvalid):
        auth_service.verify_code(db, "a@example.com", wrong)


def test_expired_code_is_refused_as_expired(db, make_user, sent):
    user = make_user(email="a@example.com", password="demo-password")
    start(db, "a@example.com", "demo-password")

    user.login_code_expires_at = utcnow() - timedelta(seconds=1)
    db.add(user)
    db.commit()

    with pytest.raises(auth_service.CodeExpired):
        auth_service.verify_code(db, "a@example.com", sent[0])


def test_a_used_code_is_refused_the_second_time(db, make_user, sent):
    make_user(email="a@example.com", password="demo-password")
    start(db, "a@example.com", "demo-password")

    auth_service.verify_code(db, "a@example.com", sent[0])
    with pytest.raises(auth_service.CodeInvalid):
        auth_service.verify_code(db, "a@example.com", sent[0])


def test_a_fresh_sign_in_replaces_the_outstanding_code(db, make_user, sent):
    """Two devices: the second issues a new code and the first stops working."""
    make_user(email="a@example.com", password="demo-password")
    start(db, "a@example.com", "demo-password")
    first = sent[0]

    start(db, "a@example.com", "demo-password")
    second = sent[1]
    assert first != second

    with pytest.raises(auth_service.CodeInvalid):
        auth_service.verify_code(db, "a@example.com", first)

    assert auth_service.verify_code(db, "a@example.com", second) is not None


def test_signing_out_deletes_the_session_row(db, make_user, sent):
    from app.models.session import Session as SessionRow

    make_user(email="a@example.com", password="demo-password")
    start(db, "a@example.com", "demo-password")
    row = auth_service.verify_code(db, "a@example.com", sent[0])

    auth_service.sign_out(db, row.id)
    assert db.get(SessionRow, row.id) is None
