"""How many attempts a person may make.

`allowed_attempts` of 0 is unlimited. Any other number is respected, and on a
recurring test it is per cycle: the count starts again after each pass, so the
attempts of earlier cycles never use up a test that recurs for years.
"""

from __future__ import annotations

import pytest

from app.models.module import Module
from app.models.registration import Registration
from app.schemas.quiz import QuestionWrite, TestWrite
from app.services import attempt_service, question_service, test_service


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
def trainee(db, make_user, module):
    person = make_user(email="t@example.com", role="trainee")
    db.add(Registration(user_id=person.id, module_id=module.id, role_in_module="trainee"))
    db.commit()
    return person


@pytest.fixture()
def question(db, owner, module):
    return question_service.create_question(
        db, owner, module.id,
        QuestionWrite(prompt="Q?", points=1, options=["right", "wrong"], correct=[0]),
    )


def _test(db, owner, module, question, **overrides):
    data = dict(title="Check", passing_score=80, question_ids=[question.id])
    data.update(overrides)
    created = test_service.create(db, owner, module.id, TestWrite(**data))
    test_service.set_published(db, owner, created.id, True)
    return created


def _sit(db, trainee, test, question, *, passing: bool):
    row = attempt_service.start(db, trainee, test.id)
    if passing:
        attempt_service.save_answer(
            db, trainee, row.id, question.id, question_service.correct_ids(db, question.id)
        )
    return attempt_service.submit(db, row)


def test_unlimited_never_refuses(db, owner, module, question, trainee):
    test = _test(db, owner, module, question, allowed_attempts=0)

    for _ in range(6):
        _sit(db, trainee, test, question, passing=False)

    assert attempt_service.why_not_startable(db, trainee, test_service.row_of(db, test.id)) is None
    attempt_service.start(db, trainee, test.id)


def test_a_number_is_respected_on_a_one_off_test(db, owner, module, question, trainee):
    test = _test(db, owner, module, question, allowed_attempts=5)

    for _ in range(5):
        _sit(db, trainee, test, question, passing=False)

    with pytest.raises(attempt_service.NoAttemptsLeft, match="5 permitted attempts at this test"):
        attempt_service.start(db, trainee, test.id)


def test_a_number_is_respected_on_a_recurring_test(db, owner, module, question, trainee):
    """The limit used to be ignored entirely once a retake interval was set."""
    test = _test(db, owner, module, question, allowed_attempts=2, retake_interval_days=90)

    for _ in range(2):
        _sit(db, trainee, test, question, passing=False)

    with pytest.raises(attempt_service.NoAttemptsLeft, match="2 permitted attempts in this cycle"):
        attempt_service.start(db, trainee, test.id)


def test_a_pass_starts_a_fresh_allowance_on_a_recurring_test(
    db, owner, module, question, trainee
):
    test = _test(db, owner, module, question, allowed_attempts=2, retake_interval_days=90)

    _sit(db, trainee, test, question, passing=False)
    passed = _sit(db, trainee, test, question, passing=True)
    assert passed.passed is True

    # Two attempts are already behind them, but the pass began a new cycle.
    for _ in range(2):
        _sit(db, trainee, test, question, passing=False)

    with pytest.raises(attempt_service.NoAttemptsLeft):
        attempt_service.start(db, trainee, test.id)


def test_the_page_and_the_service_agree(db, owner, module, question, trainee):
    test = _test(db, owner, module, question, allowed_attempts=1, retake_interval_days=90)
    _sit(db, trainee, test, question, passing=False)

    reason = attempt_service.why_not_startable(db, trainee, test_service.row_of(db, test.id))
    assert reason is not None and "in this cycle" in reason.text
    with pytest.raises(attempt_service.NoAttemptsLeft):
        attempt_service.start(db, trainee, test.id)


def test_a_negative_number_is_refused_by_the_schema():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="Unlimited attempts"):
        TestWrite(title="Check", allowed_attempts=-1)
