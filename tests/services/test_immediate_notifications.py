"""The two events that are notified inside the request that caused them.

Neither waits for the daily job. A registration notice sent tomorrow morning is
not a registration notice (FR-018, research R4).
"""

from __future__ import annotations

import pytest
from sqlmodel import select

from app.models.module import Module
from app.models.notification import Notification
from app.models.registration import Registration
from app.schemas.module import RosterAdd
from app.schemas.quiz import QuestionWrite, TestWrite
from app.services import (
    attempt_service,
    question_service,
    registration_service,
    test_service,
)


@pytest.fixture()
def module(db):
    row = Module(title="Phishing Awareness", is_published=True)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def owner(db, make_user, module):
    person = make_user(email="owner@example.com", role="instructor")
    db.add(Registration(user_id=person.id, module_id=module.id, role_in_module="instructor"))
    db.commit()
    return person


@pytest.fixture()
def live_test(db, owner, module):
    questions = [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt=f"Q{n}?", points=1, options=["right", "wrong"], correct=[0]),
        )
        for n in (1, 2)
    ]
    created = test_service.create(
        db, owner, module.id,
        TestWrite(
            title="Check",
            allowed_attempts=3,
            passing_score=80,
            question_ids=[q.id for q in questions],
        ),
    )
    test_service.set_published(db, owner, created.id, True)
    return created


def _kinds(db, user_id) -> list[str]:
    return [
        row.kind
        for row in db.exec(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.id)
        ).all()
    ]


# ------------------------------------------------------------- registration


def test_registering_somebody_notifies_them_at_once(
    db, mail, owner, module, make_user
):
    person = make_user(email="new@example.com", full_name="New Person")

    registration_service.register_many(
        db, owner, module.id, RosterAdd(user_ids=[person.id], role_in_module="trainee")
    )

    assert _kinds(db, person.id) == ["registered"]
    assert len(mail) == 1
    to, subject, body = mail[0]
    assert to == "new@example.com"
    assert "Phishing Awareness" in body


def test_registering_five_in_one_action_notifies_each_about_their_own(
    db, mail, owner, module, make_user
):
    """One action, five notices, each naming that person (FR-015, quickstart
    Scenario 5)."""
    people = [make_user(email=f"p{n}@example.com", full_name=f"Person {n}") for n in range(5)]

    registration_service.register_many(
        db,
        owner,
        module.id,
        RosterAdd(user_ids=[person.id for person in people], role_in_module="trainee"),
    )

    for person in people:
        assert _kinds(db, person.id) == ["registered"]

    assert len(mail) == 5
    assert {to for to, _, _ in mail} == {f"p{n}@example.com" for n in range(5)}
    # Each message greets the person it went to, not the batch.
    for person in people:
        assert any(
            to == person.email and person.full_name in body for to, _, body in mail
        )


def test_somebody_already_registered_is_not_notified_again(
    db, mail, owner, module, make_user
):
    person = make_user(email="already@example.com")
    selection = RosterAdd(user_ids=[person.id], role_in_module="trainee")

    registration_service.register_many(db, owner, module.id, selection)
    registration_service.register_many(db, owner, module.id, selection)

    assert _kinds(db, person.id) == ["registered"]
    assert len(mail) == 1


def test_a_mail_failure_does_not_undo_the_registration(
    db, failing_mail, owner, module, make_user
):
    """The record and the registration both stand; only the delivery failed
    (FR-023, FR-025)."""
    person = make_user(email="new@example.com")

    added = registration_service.register_many(
        db, owner, module.id, RosterAdd(user_ids=[person.id], role_in_module="trainee")
    )

    assert added == 1
    row = db.exec(
        select(Notification).where(Notification.user_id == person.id)
    ).first()
    assert row is not None
    assert row.emailed_at is None


# ------------------------------------------------------------------- results


def test_submitting_a_test_notifies_the_person_who_submitted(
    db, mail, owner, module, make_user, live_test
):
    person = make_user(email="taker@example.com", full_name="Taker")
    db.add(Registration(user_id=person.id, module_id=module.id, role_in_module="trainee"))
    db.commit()

    attempt = attempt_service.start(db, person, live_test.id)
    attempt_service.submit_own(db, person, attempt.id)

    assert _kinds(db, person.id) == ["result"]
    assert len(mail) == 1
    to, subject, body = mail[0]
    assert to == "taker@example.com"
    assert "Check" in body


def test_the_result_notice_says_the_outcome(
    db, mail, owner, module, make_user, live_test
):
    person = make_user(email="taker@example.com")
    db.add(Registration(user_id=person.id, module_id=module.id, role_in_module="trainee"))
    db.commit()

    attempt = attempt_service.start(db, person, live_test.id)
    attempt_service.submit_own(db, person, attempt.id)

    row = db.exec(select(Notification).where(Notification.user_id == person.id)).first()
    # Nothing was answered, so it did not pass.
    assert "Not passed" in row.title
    assert "0%" in row.body


def test_nobody_else_is_told_about_somebody_elses_result(
    db, mail, owner, module, make_user, live_test
):
    person = make_user(email="taker@example.com")
    db.add(Registration(user_id=person.id, module_id=module.id, role_in_module="trainee"))
    db.commit()

    attempt = attempt_service.start(db, person, live_test.id)
    attempt_service.submit_own(db, person, attempt.id)

    assert _kinds(db, owner.id) == []


def test_each_submission_is_its_own_notice(
    db, mail, owner, module, make_user, live_test
):
    """Two attempts, two results. The unique constraint does not collapse them,
    because a result carries no due date and two nulls never collide."""
    person = make_user(email="taker@example.com")
    db.add(Registration(user_id=person.id, module_id=module.id, role_in_module="trainee"))
    db.commit()

    for _ in range(2):
        attempt = attempt_service.start(db, person, live_test.id)
        attempt_service.submit_own(db, person, attempt.id)

    assert _kinds(db, person.id) == ["result", "result"]
