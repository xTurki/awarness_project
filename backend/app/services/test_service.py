"""Building a test, and the freeze that protects what people have already sat.

`assert_not_attempted` sits at the top of every mutating function. One helper,
one rule, checked by asking whether an attempt exists rather than by reading a
flag that could drift from reality (research R6, FR-013).
"""

from __future__ import annotations

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.config import settings
from app.database import utcnow
from app.models.attempt import Attempt
from app.models.question import Question
from app.models.test import Test, TestQuestion
from app.models.user import User
from app.schemas.quiz import TestRead, TestWrite
from app.services import module_service


class TestNotFound(Exception):
    pass


class TestFrozen(Exception):
    """Somebody has attempted it. The message explains itself (FR-014)."""


class CannotPublish(Exception):
    """No questions, or a pass mark that could not be reached."""


class InvalidSchedule(Exception):
    """A retake interval or completion period that cannot mean anything.

    The message is what the form shows, so it says what to do rather than what
    went wrong.
    """


FROZEN_MESSAGE = (
    "This test has been attempted, so nothing in it can change. Unpublish it to "
    "stop further attempts, then build a replacement."
)


def assert_not_attempted(db: DbSession, test_id: int) -> None:
    if db.exec(select(Attempt).where(Attempt.test_id == test_id)).first() is not None:
        raise TestFrozen(FROZEN_MESSAGE)


def is_attempted(db: DbSession, test_id: int) -> bool:
    return db.exec(select(Attempt).where(Attempt.test_id == test_id)).first() is not None


# ------------------------------------------------------------------- listing


def list_for_module(db: DbSession, actor: User, module_id: int) -> list[TestRead]:
    """Instructors see all; trainees see published ones inside their window."""
    module_service.get_for(db, module_id, actor)
    rows = db.exec(select(Test).where(Test.module_id == module_id).order_by(Test.id)).all()

    if _can_write(db, module_id, actor):
        return [_read(db, row) for row in rows]

    now = utcnow()
    return [
        _read(db, row)
        for row in rows
        if row.is_published
        and (row.opens_at is None or row.opens_at <= now)
        and (row.closes_at is None or now <= row.closes_at)
    ]


def get_test(db: DbSession, actor: User, test_id: int) -> TestRead:
    row = _test(db, test_id)
    module_service.get_for(db, row.module_id, actor)

    if not row.is_published and not _can_write(db, row.module_id, actor):
        raise TestNotFound()
    return _read(db, row)


def questions_of(db: DbSession, test_id: int) -> list[Question]:
    """In the instructor's chosen order."""
    pairs = db.exec(
        select(TestQuestion)
        .where(TestQuestion.test_id == test_id)
        .order_by(TestQuestion.position)
    ).all()
    questions = {q.id: q for q in db.exec(select(Question)).all()}
    return [questions[pair.question_id] for pair in pairs if pair.question_id in questions]


# ------------------------------------------------------------------- building


def create(db: DbSession, actor: User, module_id: int, data: TestWrite) -> TestRead:
    module_service.get_for_write(db, module_id, actor)
    _check_pass_mark(db, module_id, data)
    _check_schedule(data)

    row = Test(
        module_id=module_id,
        title=data.title.strip(),
        instructions=data.instructions,
        opens_at=data.opens_at,
        closes_at=data.closes_at,
        time_limit_minutes=data.time_limit_minutes,
        allowed_attempts=data.allowed_attempts,
        shuffle_questions=data.shuffle_questions,
        passing_score=data.passing_score,
        retake_interval_days=data.retake_interval_days,
        completion_deadline_days=data.completion_deadline_days,
        is_published=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    _set_questions(db, row.id, module_id, data.question_ids)
    return _read(db, row)


def update(db: DbSession, actor: User, test_id: int, data: TestWrite) -> TestRead:
    row = _test(db, test_id)
    module_service.get_for_write(db, row.module_id, actor)
    assert_not_attempted(db, test_id)
    _check_pass_mark(db, row.module_id, data)
    _check_schedule(data)

    row.title = data.title.strip()
    row.instructions = data.instructions
    row.opens_at = data.opens_at
    row.closes_at = data.closes_at
    row.time_limit_minutes = data.time_limit_minutes
    row.allowed_attempts = data.allowed_attempts
    row.shuffle_questions = data.shuffle_questions
    row.passing_score = data.passing_score
    row.retake_interval_days = data.retake_interval_days
    row.completion_deadline_days = data.completion_deadline_days
    db.add(row)
    db.commit()

    _set_questions(db, test_id, row.module_id, data.question_ids)
    db.refresh(row)
    return _read(db, row)


def set_published(db: DbSession, actor: User, test_id: int, published: bool) -> TestRead:
    """Permitted even when frozen: unpublishing is how an instructor stops
    further attempts on a test they can no longer edit (FR-014)."""
    row = _test(db, test_id)
    module_service.get_for_write(db, row.module_id, actor)

    if published and not questions_of(db, test_id):
        raise CannotPublish("A test with no questions cannot be published.")

    row.is_published = published
    db.add(row)
    db.commit()
    db.refresh(row)
    return _read(db, row)


# ---------------------------------------------------------------------- helpers


def _check_schedule(data: TestWrite) -> None:
    """Both settings need a pass mark, and an interval needs room to warn in.

    A cycle that restarts on passing must know what passing means, so neither is
    accepted on a test with no pass mark (FR-003, FR-038). And an interval
    shorter than the warning period would fire the warning before the person had
    taken the test, which is a reminder about something they cannot yet have
    missed (FR-004).
    """
    if data.retake_interval_days is None and data.completion_deadline_days is None:
        return

    if data.passing_score is None:
        raise InvalidSchedule(
            "Set a pass mark first. A test that is chased has to know what "
            "passing means."
        )

    lead = settings.due_soon_lead_days
    if data.retake_interval_days is not None and data.retake_interval_days < lead:
        raise InvalidSchedule(
            f"A retake interval must be at least {lead} days, because people are "
            f"warned {lead} days before it falls due."
        )


def _check_pass_mark(db: DbSession, module_id: int, data: TestWrite) -> None:
    """A pass mark is a percentage, so it is reachable by definition, unless the
    test carries no points at all to earn it with (FR-012)."""
    if data.passing_score is None or not data.question_ids:
        return

    rows = db.exec(select(Question).where(Question.id.in_(data.question_ids))).all()
    available = sum(row.points for row in rows if row.module_id == module_id)
    if available <= 0 and data.passing_score > 0:
        raise CannotPublish(
            "These questions carry no points, so the pass mark could never be reached."
        )


def _set_questions(db: DbSession, test_id: int, module_id: int, question_ids: list[int]) -> None:
    for pair in db.exec(select(TestQuestion).where(TestQuestion.test_id == test_id)).all():
        db.delete(pair)
    db.commit()

    for position, question_id in enumerate(question_ids, start=1):
        question = db.get(Question, question_id)
        if question is None or question.module_id != module_id:
            continue  # a question from another module is not part of this test
        db.add(
            TestQuestion(test_id=test_id, question_id=question_id, position=position)
        )
    db.commit()


def row_of(db: DbSession, test_id: int) -> Test | None:
    """The table row, for the few callers that need the columns a read model
    does not carry. Authorisation is the caller's, which is why this is only
    used beside a `get_test` that has already done it."""
    return db.get(Test, test_id)


def _test(db: DbSession, test_id: int) -> Test:
    row = db.get(Test, test_id)
    if row is None:
        raise TestNotFound()
    return row


def _can_write(db: DbSession, module_id: int, actor: User) -> bool:
    try:
        module_service.get_for_write(db, module_id, actor)
        return True
    except (module_service.NotPermitted, module_service.NotFound):
        return False


def _read(db: DbSession, row: Test) -> TestRead:
    return TestRead(
        id=row.id,
        module_id=row.module_id,
        title=row.title,
        instructions=row.instructions,
        is_published=row.is_published,
        opens_at=row.opens_at,
        closes_at=row.closes_at,
        time_limit_minutes=row.time_limit_minutes,
        allowed_attempts=row.allowed_attempts,
        shuffle_questions=row.shuffle_questions,
        passing_score=row.passing_score,
        retake_interval_days=row.retake_interval_days,
        completion_deadline_days=row.completion_deadline_days,
        question_count=len(questions_of(db, row.id)),
        is_frozen=is_attempted(db, row.id),
    )
