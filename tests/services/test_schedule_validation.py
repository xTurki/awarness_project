"""Validation of retake interval and completion period settings."""

from __future__ import annotations

import pytest

from app.config import settings
from app.models.module import Module
from app.models.registration import Registration
from app.schemas.quiz import QuestionWrite, TestWrite
from app.services import module_service, question_service, test_service


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
def questions(db, owner, module):
    return [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt=f"Q{n}?", points=1, options=["right", "wrong"], correct=[0]),
        )
        for n in (1, 2)
    ]


def _write(**overrides) -> TestWrite:
    data = {"title": "Check", "allowed_attempts": 1, "passing_score": 80}
    data.update(overrides)
    return TestWrite(**data)


# ------------------------------------------------------------ what is refused


def test_a_retake_interval_needs_a_pass_mark(db, owner, module):
    """A retake interval requires a pass mark."""
    with pytest.raises(test_service.InvalidSchedule) as refused:
        test_service.create(
            db, owner, module.id, _write(passing_score=None, retake_interval_days=90)
        )

    assert "pass mark" in str(refused.value).lower()


def test_a_completion_period_needs_a_pass_mark(db, owner, module):
    """A completion period requires a pass mark."""
    with pytest.raises(test_service.InvalidSchedule):
        test_service.create(
            db, owner, module.id, _write(passing_score=None, completion_deadline_days=30)
        )


def test_an_interval_shorter_than_the_warning_period_is_refused(db, owner, module):
    """The interval can't be shorter than the due-soon warning period."""
    too_short = settings.due_soon_lead_days - 1

    with pytest.raises(test_service.InvalidSchedule) as refused:
        test_service.create(db, owner, module.id, _write(retake_interval_days=too_short))

    assert str(settings.due_soon_lead_days) in str(refused.value)


def test_an_interval_equal_to_the_warning_period_is_allowed(db, owner, module):
    created = test_service.create(
        db, owner, module.id, _write(retake_interval_days=settings.due_soon_lead_days)
    )
    assert created.retake_interval_days == settings.due_soon_lead_days


def test_a_period_of_zero_days_is_refused(db):
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _write(retake_interval_days=0)


def test_an_instructor_elsewhere_cannot_set_one(db, make_user, module):
    outsider = make_user(email="outsider@example.com", role="instructor")

    with pytest.raises((module_service.NotFound, module_service.NotPermitted)):
        test_service.create(db, outsider, module.id, _write(retake_interval_days=90))


# ------------------------------------------------------------ what is accepted


def test_a_retake_interval_is_stored_and_shown_back(db, owner, module, questions):
    created = test_service.create(
        db, owner, module.id,
        _write(retake_interval_days=90, question_ids=[q.id for q in questions]),
    )

    assert created.retake_interval_days == 90
    assert created.completion_deadline_days is None


def test_a_completion_period_is_stored(db, owner, module):
    created = test_service.create(
        db, owner, module.id, _write(completion_deadline_days=30)
    )
    assert created.completion_deadline_days == 30


def test_neither_is_the_normal_case(db, owner, module):
    """A test with no schedule is valid."""
    created = test_service.create(db, owner, module.id, _write())

    assert created.retake_interval_days is None
    assert created.completion_deadline_days is None


def test_a_schedule_can_be_changed_later(db, owner, module):
    created = test_service.create(db, owner, module.id, _write(retake_interval_days=90))
    updated = test_service.update(
        db, owner, created.id, _write(retake_interval_days=365)
    )

    # Due dates are calculated, so they all change at once.
    assert updated.retake_interval_days == 365
