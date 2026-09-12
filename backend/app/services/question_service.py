"""The question bank.

Validation happens on save, because neither rule is recoverable once a trainee
is mid-attempt: at least two options, at least one of them correct (FR-003).
"""

from __future__ import annotations

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models.attempt import Attempt
from app.models.question import AnswerOption, Question
from app.models.test import TestQuestion
from app.models.user import User
from app.schemas.quiz import OptionRead, OptionReview, QuestionReview, QuestionWrite
from app.services import module_service


class QuestionNotFound(Exception):
    pass


class QuestionFrozen(Exception):
    """The question sits in a test somebody has already attempted."""


def assert_question_not_attempted(db: DbSession, question_id: int) -> None:
    """A question inside an **attempted** test is frozen too.

    `test_service.assert_not_attempted` cannot see this from here: it is keyed
    on a test, and a question does not know which tests hold it. One query
    joining `test_question` to `attempt` answers it (FR-013, SC-011).
    """
    used_in = db.exec(
        select(TestQuestion.test_id).where(TestQuestion.question_id == question_id)
    ).all()
    if not used_in:
        return

    attempted = db.exec(select(Attempt).where(Attempt.test_id.in_(used_in))).first()
    if attempted is not None:
        raise QuestionFrozen(
            "This question is in a test that has already been attempted, so it "
            "cannot be changed. Build a replacement test instead."
        )


def list_bank(db: DbSession, actor: User, module_id: int) -> list[QuestionReview]:
    module_service.get_for_write(db, module_id, actor)
    rows = db.exec(
        select(Question).where(Question.module_id == module_id).order_by(Question.position)
    ).all()
    return [_review(db, row) for row in rows]


def get_question(db: DbSession, actor: User, module_id: int, question_id: int) -> QuestionReview:
    module_service.get_for_write(db, module_id, actor)
    return _review(db, _question(db, module_id, question_id))


def create_question(
    db: DbSession, actor: User, module_id: int, data: QuestionWrite
) -> QuestionReview:
    module_service.get_for_write(db, module_id, actor)

    row = Question(
        module_id=module_id,
        prompt=data.prompt.strip(),
        points=data.points,
        position=_next_position(db, module_id),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    _write_options(db, row.id, data)
    return _review(db, row)


def update_question(
    db: DbSession, actor: User, module_id: int, question_id: int, data: QuestionWrite
) -> QuestionReview:
    module_service.get_for_write(db, module_id, actor)
    row = _question(db, module_id, question_id)
    assert_question_not_attempted(db, question_id)

    row.prompt = data.prompt.strip()
    row.points = data.points
    db.add(row)

    for option in db.exec(
        select(AnswerOption).where(AnswerOption.question_id == question_id)
    ).all():
        db.delete(option)
    db.commit()

    _write_options(db, question_id, data)
    db.refresh(row)
    return _review(db, row)


def delete_question(db: DbSession, actor: User, module_id: int, question_id: int) -> None:
    module_service.get_for_write(db, module_id, actor)
    row = _question(db, module_id, question_id)
    assert_question_not_attempted(db, question_id)

    for option in db.exec(
        select(AnswerOption).where(AnswerOption.question_id == question_id)
    ).all():
        db.delete(option)
    db.delete(row)
    db.commit()


# ---------------------------------------------------------------------- helpers


def options_for(db: DbSession, question_id: int) -> list[AnswerOption]:
    return db.exec(
        select(AnswerOption)
        .where(AnswerOption.question_id == question_id)
        .order_by(AnswerOption.position)
    ).all()


def correct_ids(db: DbSession, question_id: int) -> list[int]:
    return [option.id for option in options_for(db, question_id) if option.is_correct]


def _write_options(db: DbSession, question_id: int, data: QuestionWrite) -> None:
    correct = set(data.correct)
    for index, text in enumerate(data.options):
        db.add(
            AnswerOption(
                question_id=question_id,
                text=text.strip()[:500],
                is_correct=index in correct,
                position=index + 1,
            )
        )
    db.commit()


def _question(db: DbSession, module_id: int, question_id: int) -> Question:
    row = db.get(Question, question_id)
    if row is None or row.module_id != module_id:
        raise QuestionNotFound()
    return row


def _next_position(db: DbSession, module_id: int) -> int:
    rows = db.exec(select(Question).where(Question.module_id == module_id)).all()
    return max((row.position for row in rows), default=0) + 1


def _review(db: DbSession, row: Question) -> QuestionReview:
    options = options_for(db, row.id)
    return QuestionReview(
        id=row.id,
        prompt=row.prompt,
        points=row.points,
        position=row.position,
        options=[
            OptionReview(
                id=o.id, text=o.text, position=o.position, is_correct=o.is_correct
            )
            for o in options
        ],
        multiple=sum(1 for o in options if o.is_correct) > 1,
    )


def taking_view(db: DbSession, row: Question) -> tuple[list[OptionRead], bool]:
    """Options as a trainee sees them while answering: no `is_correct`."""
    options = options_for(db, row.id)
    return (
        [OptionRead(id=o.id, text=o.text, position=o.position) for o in options],
        sum(1 for o in options if o.is_correct) > 1,
    )
