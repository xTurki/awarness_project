"""Building a test, and the freeze.

Once one attempt exists nothing in the test can change, through any route
(FR-013, SC-011). Publishing and unpublishing stay available, which is how an
instructor stops further attempts on a test they can no longer edit (FR-014).
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
def bank(db, owner, module):
    return [
        question_service.create_question(
            db,
            owner,
            module.id,
            QuestionWrite(prompt=f"Question {n}?", points=1, options=["Right", "Wrong"], correct=[0]),
        )
        for n in range(1, 4)
    ]


def _test_write(bank, **overrides):
    data = dict(
        title="Awareness check",
        allowed_attempts=2,
        passing_score=80,
        question_ids=[q.id for q in bank],
    )
    data.update(overrides)
    return TestWrite(**data)


# ------------------------------------------------------------------- building


def test_a_test_holds_the_chosen_questions_in_order(db, owner, module, bank):
    created = test_service.create(db, owner, module.id, _test_write(bank))
    ordered = test_service.questions_of(db, created.id)

    assert [q.id for q in ordered] == [q.id for q in bank]
    assert created.question_count == 3
    assert created.is_published is False


def test_a_question_from_another_module_is_not_added(db, owner, module, bank, make_user):
    other = Module(title="Other", is_published=True)
    db.add(other)
    db.commit()
    db.refresh(other)
    db.add(Registration(user_id=owner.id, module_id=other.id, role_in_module="instructor"))
    db.commit()

    foreign = question_service.create_question(
        db, owner, other.id,
        QuestionWrite(prompt="Foreign?", points=1, options=["A", "B"], correct=[0]),
    )

    created = test_service.create(
        db, owner, module.id, _test_write(bank, question_ids=[bank[0].id, foreign.id])
    )
    assert created.question_count == 1


# ------------------------------------------------------------------ publishing


def test_publishing_with_no_questions_is_refused(db, owner, module):
    empty = test_service.create(db, owner, module.id, _test_write([], question_ids=[]))

    with pytest.raises(test_service.CannotPublish) as caught:
        test_service.set_published(db, owner, empty.id, True)
    assert "no questions" in str(caught.value)


def test_a_pass_mark_above_a_hundred_is_refused():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TestWrite(title="Bad", passing_score=150)


def test_publishing_makes_it_visible_to_a_trainee(db, owner, module, bank, trainee):
    created = test_service.create(db, owner, module.id, _test_write(bank))

    assert test_service.list_for_module(db, trainee, module.id) == []

    test_service.set_published(db, owner, created.id, True)
    assert [t.id for t in test_service.list_for_module(db, trainee, module.id)] == [created.id]


# ---------------------------------------------------------------- the freeze


def _attempt(db, trainee, test_id):
    return attempt_service.start(db, trainee, test_id)


def test_a_test_can_be_edited_freely_before_anyone_attempts_it(db, owner, module, bank):
    created = test_service.create(db, owner, module.id, _test_write(bank))
    updated = test_service.update(
        db, owner, created.id, _test_write(bank, title="Renamed")
    )
    assert updated.title == "Renamed"
    assert updated.is_frozen is False


def test_one_attempt_freezes_the_test(db, owner, module, bank, trainee):
    created = test_service.create(db, owner, module.id, _test_write(bank))
    test_service.set_published(db, owner, created.id, True)
    _attempt(db, trainee, created.id)

    with pytest.raises(test_service.TestFrozen) as caught:
        test_service.update(db, owner, created.id, _test_write(bank, title="Too late"))

    assert "attempted" in str(caught.value)
    assert "replacement" in str(caught.value), "the refusal must explain itself (FR-014)"


def test_the_questions_in_an_attempted_test_are_frozen_too(db, owner, module, bank, trainee):
    """The freeze reaches question_service, which knows nothing about tests."""
    created = test_service.create(db, owner, module.id, _test_write(bank))
    test_service.set_published(db, owner, created.id, True)
    _attempt(db, trainee, created.id)

    with pytest.raises(question_service.QuestionFrozen):
        question_service.update_question(
            db, owner, module.id, bank[0].id,
            QuestionWrite(prompt="Reworded", points=1, options=["A", "B"], correct=[0]),
        )

    with pytest.raises(question_service.QuestionFrozen):
        question_service.delete_question(db, owner, module.id, bank[0].id)


def test_a_bank_question_outside_any_attempted_test_stays_editable(db, owner, module, bank, trainee):
    created = test_service.create(
        db, owner, module.id, _test_write(bank, question_ids=[bank[0].id])
    )
    test_service.set_published(db, owner, created.id, True)
    _attempt(db, trainee, created.id)

    # bank[1] is in no attempted test, so it is still ordinary.
    updated = question_service.update_question(
        db, owner, module.id, bank[1].id,
        QuestionWrite(prompt="Still editable", points=1, options=["A", "B"], correct=[1]),
    )
    assert updated.prompt == "Still editable"


def test_unpublishing_still_works_when_frozen(db, owner, module, bank, trainee):
    """This is the route out: stop further attempts, then build a replacement."""
    created = test_service.create(db, owner, module.id, _test_write(bank))
    test_service.set_published(db, owner, created.id, True)
    _attempt(db, trainee, created.id)

    after = test_service.set_published(db, owner, created.id, False)
    assert after.is_published is False
    assert after.is_frozen is True


def test_a_frozen_test_says_so_in_its_read_model(db, owner, module, bank, trainee):
    created = test_service.create(db, owner, module.id, _test_write(bank))
    test_service.set_published(db, owner, created.id, True)

    assert test_service.get_test(db, owner, created.id).is_frozen is False
    _attempt(db, trainee, created.id)
    assert test_service.get_test(db, owner, created.id).is_frozen is True
