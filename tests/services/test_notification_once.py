"""Told once, retried until delivered, and stopped when they leave.

Three separate guarantees, and each of them is one line of mechanism:

* the unique constraint, so an overdue notice is created once (FR-014);
* `emailed_at` left null on a failed send, so the next run retries it without
  creating a second record (FR-025);
* the derivation reading a registration, so removing one stops the chasing
  while leaving what was already said in place (FR-012).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlmodel import select

from app.models.attempt import Attempt
from app.models.module import Module
from app.models.notification import Notification
from app.models.registration import Registration
from app.schemas.quiz import QuestionWrite, TestWrite
from app.services import daily_job, notification_service, question_service, test_service

TODAY = date(2027, 3, 15)


@pytest.fixture()
def setup(db, make_user):
    """One module on a 90-day interval, and one person long overdue on it."""
    owner = make_user(email="owner@example.com", role="instructor")
    module = Module(title="Phishing Awareness", is_published=True)
    db.add(module)
    db.commit()
    db.refresh(module)
    db.add(Registration(user_id=owner.id, module_id=module.id, role_in_module="instructor"))

    questions = [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt=f"Q{n}?", points=1, options=["a", "b"], correct=[0]),
        )
        for n in (1, 2)
    ]
    created = test_service.create(
        db, owner, module.id,
        TestWrite(
            title="Check",
            allowed_attempts=3,
            passing_score=80,
            retake_interval_days=90,
            question_ids=[q.id for q in questions],
        ),
    )
    test_service.set_published(db, owner, created.id, True)

    person = make_user(email="a@example.com", full_name="A Person")
    registration = Registration(
        user_id=person.id,
        module_id=module.id,
        role_in_module="trainee",
        registered_at=datetime.combine(TODAY - timedelta(days=300), datetime.min.time()),
    )
    db.add(registration)
    db.commit()
    db.refresh(registration)

    passed_at = datetime.combine(TODAY - timedelta(days=100), datetime.min.time())
    db.add(
        Attempt(
            test_id=created.id,
            user_id=person.id,
            attempt_number=1,
            started_at=passed_at,
            ends_at=passed_at + timedelta(hours=1),
            submitted_at=passed_at,
            is_submitted=True,
            question_order=[],
            score_percent=90,
            passed=True,
        )
    )
    db.commit()

    return {"module": module, "test": created, "person": person, "registration": registration}


def _rows(db, user_id) -> list[Notification]:
    return list(
        db.exec(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.id)
        ).all()
    )


# ------------------------------------------------------------------ told once


def test_an_overdue_notice_is_created_once_and_never_repeated(db, mail, setup):
    """Run it on five separate days. The due date has not moved, so the key has
    not moved, so there is nothing to insert after the first time (FR-014)."""
    for offset in (0, 1, 2, 30, 365):
        daily_job.run_daily(db, TODAY + timedelta(days=offset))

    overdue = [row for row in _rows(db, setup["person"].id) if row.kind == "overdue"]
    assert len(overdue) == 1
    assert len(mail) == 1


def test_create_returns_none_for_a_duplicate(db, setup):
    """The refusal comes from the database, not from a check in Python."""
    first = notification_service.create(
        db,
        user_id=setup["person"].id,
        module_id=setup["module"].id,
        kind="overdue",
        title="Overdue",
        due_date=TODAY,
    )
    second = notification_service.create(
        db,
        user_id=setup["person"].id,
        module_id=setup["module"].id,
        kind="overdue",
        title="Overdue",
        due_date=TODAY,
    )

    assert first is not None
    assert second is None


def test_a_refused_duplicate_does_not_take_the_next_one_down_with_it(db, setup):
    """The insert runs in a savepoint. Without one, a collision would poison the
    transaction and every notification after it in the run would be lost."""
    notification_service.create(
        db, user_id=setup["person"].id, module_id=setup["module"].id,
        kind="overdue", title="Overdue", due_date=TODAY,
    )
    notification_service.create(
        db, user_id=setup["person"].id, module_id=setup["module"].id,
        kind="overdue", title="Overdue", due_date=TODAY,
    )
    survivor = notification_service.create(
        db, user_id=setup["person"].id, module_id=setup["module"].id,
        kind="overdue", title="Overdue later", due_date=TODAY + timedelta(days=90),
    )

    assert survivor is not None


def test_the_next_cycle_is_a_different_row(db, setup):
    """`due_date` is in the key so that next cycle's notice is a new event
    rather than a duplicate of this one."""
    notification_service.create(
        db, user_id=setup["person"].id, module_id=setup["module"].id,
        kind="overdue", title="Overdue", due_date=TODAY,
    )
    later = notification_service.create(
        db, user_id=setup["person"].id, module_id=setup["module"].id,
        kind="overdue", title="Overdue", due_date=TODAY + timedelta(days=90),
    )

    assert later is not None


# ------------------------------------------------------------- a failed send


def test_a_failed_send_leaves_the_record_unstamped(db, failing_mail, setup):
    """The in-app notification exists, and no message went. That difference is
    the whole point of writing the record first (FR-021, FR-025)."""
    summary = daily_job.run_daily(db, TODAY)

    assert summary.created == 1
    assert summary.messages_failed == 1
    assert summary.messages_sent == 0

    rows = _rows(db, setup["person"].id)
    assert len(rows) == 1
    assert rows[0].emailed_at is None


def test_the_next_run_retries_without_creating_a_second_record(
    db, monkeypatch, setup
):
    """Mail was broken, then fixed. The row that never went is picked up again,
    and there is still only one of it (FR-025, SC-007)."""
    from app.services.email_service import EmailDeliveryFailed

    def refuse(to, subject, body):
        raise EmailDeliveryFailed("no route to host")

    monkeypatch.setattr("app.services.email_service.send_email_now", refuse)
    daily_job.run_daily(db, TODAY)

    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "app.services.email_service.send_email_now",
        lambda to, subject, body: sent.append((to, subject, body)),
    )
    second = daily_job.run_daily(db, TODAY)

    assert second.created == 0, "the retry created a second record"
    assert second.messages_sent == 1
    assert len(sent) == 1

    rows = _rows(db, setup["person"].id)
    assert len(rows) == 1
    assert rows[0].emailed_at is not None


def test_a_delivered_row_is_not_sent_again(db, mail, setup):
    daily_job.run_daily(db, TODAY)
    daily_job.run_daily(db, TODAY)

    assert len(mail) == 1


# ------------------------------------------------------- leaving the module


def test_removing_a_registration_stops_the_chasing(db, mail, setup):
    """Nothing is migrated and nothing is cleaned up: the row the derivation
    counts from is gone, so there is no due date to be past (FR-012)."""
    db.delete(setup["registration"])
    db.commit()

    summary = daily_job.run_daily(db, TODAY)

    assert summary.created == 0
    assert _rows(db, setup["person"].id) == []
    assert mail == []


def test_what_they_were_already_told_stays_in_their_list(db, mail, setup):
    """Their history does not evaporate because they left."""
    daily_job.run_daily(db, TODAY)
    assert len(_rows(db, setup["person"].id)) == 1

    db.delete(setup["registration"])
    db.commit()
    daily_job.run_daily(db, TODAY + timedelta(days=30))

    assert len(_rows(db, setup["person"].id)) == 1
