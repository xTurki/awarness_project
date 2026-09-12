"""The question bank, and what it refuses.

At least two options, at least one correct, checked when the question is saved
because neither is recoverable once a trainee is mid-attempt (FR-003).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.module import Module
from app.models.registration import Registration
from app.schemas.quiz import QuestionWrite
from app.services import module_service, question_service


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


def _write(prompt="Which of these is a phishing sign?", options=None, correct=None, points=1):
    return QuestionWrite(
        prompt=prompt,
        points=points,
        options=options if options is not None else ["A stranger asking for a password", "A team message"],
        correct=correct if correct is not None else [0],
    )


# ------------------------------------------------------------------ validation


def test_fewer_than_two_options_is_refused():
    with pytest.raises(ValidationError) as caught:
        _write(options=["Only one"])
    assert "two answer options" in str(caught.value)


def test_no_correct_option_is_refused():
    with pytest.raises(ValidationError) as caught:
        _write(correct=[])
    assert "at least one option as correct" in str(caught.value)


def test_a_blank_prompt_is_refused():
    with pytest.raises(ValidationError):
        _write(prompt="   ")


def test_blank_options_do_not_count_towards_the_two():
    with pytest.raises(ValidationError):
        _write(options=["Real", "   ", ""])


# -------------------------------------------------------------------- creating


def test_a_question_is_saved_with_its_options(db, owner, module):
    created = question_service.create_question(db, owner, module.id, _write())

    assert created.prompt.startswith("Which of these")
    assert len(created.options) == 2
    assert sum(1 for o in created.options if o.is_correct) == 1


def test_one_correct_option_means_a_single_choice(db, owner, module):
    created = question_service.create_question(db, owner, module.id, _write())
    assert created.multiple is False


def test_several_correct_options_mean_a_multiple_choice(db, owner, module):
    """The instructor never says which. It follows from how many are ticked."""
    created = question_service.create_question(
        db,
        owner,
        module.id,
        _write(options=["One", "Two", "Three"], correct=[0, 1]),
    )
    assert created.multiple is True


def test_questions_are_positioned_in_order(db, owner, module):
    first = question_service.create_question(db, owner, module.id, _write(prompt="First?"))
    second = question_service.create_question(db, owner, module.id, _write(prompt="Second?"))
    assert (first.position, second.position) == (1, 2)


# ------------------------------------------------------------ who may write


def test_an_instructor_on_another_module_is_refused(db, make_user, module):
    outsider = make_user(email="other@example.com", role="instructor")

    with pytest.raises(module_service.NotFound):
        question_service.list_bank(db, outsider, module.id)
    with pytest.raises(module_service.NotFound):
        question_service.create_question(db, outsider, module.id, _write())


def test_a_trainee_may_not_touch_the_bank(db, make_user, module):
    trainee = make_user(email="t@example.com", role="trainee")
    db.add(Registration(user_id=trainee.id, module_id=module.id, role_in_module="trainee"))
    db.commit()

    with pytest.raises(module_service.NotPermitted):
        question_service.list_bank(db, trainee, module.id)


# --------------------------------------------------------- editing and deleting


def test_editing_replaces_the_options(db, owner, module):
    created = question_service.create_question(db, owner, module.id, _write())

    updated = question_service.update_question(
        db,
        owner,
        module.id,
        created.id,
        _write(prompt="Rewritten?", options=["X", "Y", "Z"], correct=[2]),
    )

    assert updated.prompt == "Rewritten?"
    assert [o.text for o in updated.options] == ["X", "Y", "Z"]
    assert [o.is_correct for o in updated.options] == [False, False, True]


def test_deleting_removes_it_from_the_bank(db, owner, module):
    created = question_service.create_question(db, owner, module.id, _write())
    question_service.delete_question(db, owner, module.id, created.id)

    assert question_service.list_bank(db, owner, module.id) == []
