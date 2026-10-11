"""A test's questions are drawn at random from the bank, by count."""

from __future__ import annotations

import pytest

from app.models.module import Module
from app.models.registration import Registration
from app.schemas.quiz import QuestionWrite, TestWrite
from app.services import question_service, test_service


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
def bank(db, owner, module):
    return [
        question_service.create_question(
            db,
            owner,
            module.id,
            QuestionWrite(prompt=f"Question {n}?", points=1, options=["Right", "Wrong"], correct=[0]),
        )
        for n in range(1, 21)
    ]


def _write(count, **overrides):
    return TestWrite(title="Quiz", passing_score=70, question_count=count, **overrides)


def _ids(db, test_id):
    return [q.id for q in test_service.questions_of(db, test_id)]


def test_draws_the_requested_number_from_the_bank(db, owner, module, bank):
    created = test_service.create(db, owner, module.id, _write(10))

    drawn = _ids(db, created.id)
    assert len(drawn) == 10
    assert len(set(drawn)) == 10
    assert set(drawn) <= {q.id for q in bank}


def test_draws_differ_between_tests(db, owner, module, bank):
    sets = {
        frozenset(_ids(db, test_service.create(db, owner, module.id, _write(10)).id))
        for _ in range(5)
    }
    assert len(sets) > 1


def test_edit_with_the_same_count_keeps_the_questions(db, owner, module, bank):
    created = test_service.create(db, owner, module.id, _write(10))
    before = _ids(db, created.id)

    test_service.update(db, owner, created.id, _write(10, instructions="New"))

    assert _ids(db, created.id) == before


def test_edit_with_a_new_count_draws_again(db, owner, module, bank):
    created = test_service.create(db, owner, module.id, _write(10))

    test_service.update(db, owner, created.id, _write(5))

    assert len(_ids(db, created.id)) == 5


@pytest.mark.parametrize("count", [0, 21])
def test_a_count_outside_the_bank_is_refused(db, owner, module, bank, count):
    with pytest.raises(test_service.InvalidQuestionCount, match="between 1 and 20"):
        test_service.create(db, owner, module.id, _write(count))


def test_an_empty_bank_is_refused(db, owner, module):
    with pytest.raises(test_service.InvalidQuestionCount, match="bank is empty"):
        test_service.create(db, owner, module.id, _write(1))
