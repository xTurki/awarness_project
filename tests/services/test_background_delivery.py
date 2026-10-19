"""Registration and result emails are sent in a background thread."""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlmodel import select

from app.models.module import Module
from app.models.notification import Notification
from app.services import notification_service


@pytest.fixture(autouse=True)
def one_worker(monkeypatch):
    """Use a single worker so tests can wait for sends to finish."""
    worker = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr(notification_service, "_SENDER", worker)
    yield worker
    worker.shutdown(wait=True)


def _drain(worker):
    worker.submit(lambda: None).result(timeout=5)


@pytest.fixture()
def module(db):
    row = Module(title="Phishing Awareness", is_published=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def slow_relay(monkeypatch):
    """Fake email sender that blocks until the test releases it."""
    release = threading.Event()
    sent = threading.Event()
    stamped: list[list[int]] = []

    def hold(to, subject, body):
        release.wait(timeout=5)
        sent.set()

    monkeypatch.setattr(notification_service, "SEND_IN_BACKGROUND", True)
    monkeypatch.setattr("app.services.email_service.send_email_now", hold)
    monkeypatch.setattr(notification_service, "_stamp_sent", lambda ids: stamped.append(ids))
    return release, sent, stamped


def test_the_record_exists_before_the_message_is_sent(
    db, make_user, module, slow_relay, one_worker
):
    release, sent, stamped = slow_relay
    person = make_user(email="t@example.com", role="trainee")

    notification_service.notify_registered(db, person, module)

    rows = db.exec(select(Notification).where(Notification.user_id == person.id)).all()
    assert [row.kind for row in rows] == ["registered"]
    assert rows[0].emailed_at is None
    assert not sent.is_set(), "the call returned without waiting for the relay"

    release.set()
    assert sent.wait(timeout=5)
    _drain(one_worker)
    assert stamped == [[rows[0].id]]


def test_a_failed_background_send_leaves_the_record_unstamped(
    db, make_user, module, monkeypatch, one_worker
):
    from app.services.email_service import EmailDeliveryFailed

    stamped: list[list[int]] = []

    def refuse(to, subject, body):
        raise EmailDeliveryFailed("relay refused")

    monkeypatch.setattr(notification_service, "SEND_IN_BACKGROUND", True)
    monkeypatch.setattr("app.services.email_service.send_email_now", refuse)
    monkeypatch.setattr(notification_service, "_stamp_sent", lambda ids: stamped.append(ids))
    person = make_user(email="t@example.com", role="trainee")

    notification_service.notify_registered(db, person, module)
    _drain(one_worker)

    assert stamped == []
    row = db.exec(select(Notification).where(Notification.user_id == person.id)).one()
    assert row.emailed_at is None
