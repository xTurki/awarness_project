"""Taking a test, and everything that keeps an attempt safe.

Four rules carry this module:

1. **Each answer is its own write**, an upsert made the moment it is given, so a
   dropped connection loses at most the click in flight.
2. **`ends_at` and `question_order` are fixed when the attempt starts** and are
   never recomputed, which is what makes an instructor's later edit harmless.
3. **The server owns the clock.** Every write checks it; the countdown a browser
   shows decides nothing.
4. **An expired attempt is submitted the next time anyone reads it.** No
   scheduled sweep exists in this phase.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import NamedTuple

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.database import utcnow
from app.models.attempt import Attempt, AttemptAnswer
from app.models.module import Module
from app.models.question import Question
from app.models.registration import Registration
from app.models.test import Test
from app.models.user import User
from app.schemas.quiz import (
    AttemptAnswerRead,
    AttemptRead,
    CohortRow,
    OptionReview,
    QuestionRead,
    QuestionReview,
    ScoreOverride,
)
from app.services import (
    module_service,
    notification_service,
    question_service,
    scoring,
    test_service,
)


class AttemptNotFound(Exception):
    pass


class NotYours(Exception):
    """The attempt belongs to somebody else."""


class OutsideWindow(Exception):
    pass


class NoAttemptsLeft(Exception):
    pass


class AttemptClosed(Exception):
    """Its ending moment has passed, so nothing more can be recorded."""


class NotSubmitted(Exception):
    """A score cannot be overridden on an attempt still in progress (FR-036)."""


class CannotStart(NamedTuple):
    """Why somebody may not sit a test, and the moment involved if there is one.

    The moment travels separately rather than baked into the sentence, because
    the page renders it in the reader's own zone and cannot do that to a string
    it has already been handed.
    """

    text: str
    at: datetime | None = None


# ------------------------------------------------------------------- starting


def start(db: DbSession, actor: User, test_id: int) -> Attempt:
    """Begin an attempt, or resume the one already open.

    A person has at most one attempt in progress per test: opening it on a
    second device continues the same attempt rather than starting another.
    """
    test = db.get(Test, test_id)
    if test is None:
        raise AttemptNotFound()

    try:
        module_service.get_for(db, test.module_id, actor)
    except module_service.NotFound:
        # A module they cannot see does not exist, and neither does its test.
        raise AttemptNotFound() from None

    if not test.is_published:
        raise AttemptNotFound()

    if _registration(db, test.module_id, actor.id) is None:
        raise AttemptNotFound()

    open_attempt = db.exec(
        select(Attempt).where(
            Attempt.test_id == test_id,
            Attempt.user_id == actor.id,
            Attempt.is_submitted == False,  # noqa: E712
        )
    ).first()
    if open_attempt is not None:
        return expire_if_due(db, open_attempt)

    now = utcnow()
    if test.opens_at is not None and now < test.opens_at:
        raise OutsideWindow("This test is not open yet.")
    if test.closes_at is not None and now > test.closes_at:
        raise OutsideWindow("This test has closed.")

    taken = _submitted_count(db, test_id, actor.id)
    # A recurring test ignores the limit entirely: a person may retake it as
    # often as they need until they pass. A fixed number would otherwise leave
    # somebody permanently overdue with no way out of it (Phase 4 FR-005).
    if not test.retake_interval_days and taken >= test.allowed_attempts:
        raise NoAttemptsLeft(
            f"You have used all {test.allowed_attempts} permitted attempts at this test."
        )

    questions = test_service.questions_of(db, test_id)
    order = [q.id for q in questions]
    if test.shuffle_questions:
        random.shuffle(order)

    row = Attempt(
        test_id=test_id,
        user_id=actor.id,
        # Derived here, never taken from the request.
        attempt_number=taken + 1,
        started_at=now,
        ends_at=_ending_moment(now, test),
        question_order=order,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def why_not_startable(
    db: DbSession, actor: User, test: Test | None
) -> CannotStart | None:
    """None if this person may start this test, otherwise the reason in words.

    The page asks this so it can offer the button only to somebody who can use
    it, and say what is in the way when it cannot. Every refusal `start` can
    raise has a sentence here, in the same order, and a test pins the two
    together: if this returns None, `start` must succeed, and if it returns a
    reason, `start` must refuse.

    Offering the button regardless and letting the service refuse was the old
    behaviour, and it produced a Start button that answered "Not found".
    """
    if test is None or not test.is_published:
        return CannotStart("This test is not published yet.")

    if _registration(db, test.module_id, actor.id) is None:
        return CannotStart(
            "You are not registered on this module, so you cannot sit its test. "
            "Ask whoever runs it to add you."
        )

    # An attempt already open is resumable whatever the window says: the window
    # governs when an attempt may *start*, and theirs already did.
    open_attempt = db.exec(
        select(Attempt).where(
            Attempt.test_id == test.id,
            Attempt.user_id == actor.id,
            Attempt.is_submitted == False,  # noqa: E712
        )
    ).first()
    if open_attempt is not None and open_attempt.ends_at > utcnow():
        return None

    now = utcnow()
    if test.opens_at is not None and now < test.opens_at:
        return CannotStart("This test opens at", test.opens_at)
    if test.closes_at is not None and now > test.closes_at:
        return CannotStart("This test closed at", test.closes_at)

    if not test.retake_interval_days:
        taken = _submitted_count(db, test.id, actor.id)
        if taken >= test.allowed_attempts:
            return CannotStart(
                f"You have used all {test.allowed_attempts} permitted attempts "
                "at this test."
            )

    return None


def _ending_moment(started_at, test: Test):
    """min(started_at + limit, closes_at), decided once and stored.

    Computing this on each request instead would let an instructor's later edit
    move the deadline of an attempt already running, which FR-016 forbids.
    """
    candidates = []
    if test.time_limit_minutes:
        candidates.append(started_at + timedelta(minutes=test.time_limit_minutes))
    if test.closes_at:
        candidates.append(test.closes_at)
    if not candidates:
        # Untimed and never closing: far enough away to mean "no deadline".
        return started_at + timedelta(days=365)
    return min(candidates)


# -------------------------------------------------------------------- reading


def get_own(db: DbSession, actor: User, attempt_id: int) -> Attempt:
    row = db.get(Attempt, attempt_id)
    if row is None or row.user_id != actor.id:
        raise AttemptNotFound()
    return expire_if_due(db, row)


def get_viewable(db: DbSession, actor: User, attempt_id: int) -> Attempt:
    """The owner, or an instructor on the module the test belongs to."""
    row = db.get(Attempt, attempt_id)
    if row is None:
        raise AttemptNotFound()

    if row.user_id == actor.id:
        return expire_if_due(db, row)

    test = db.get(Test, row.test_id)
    try:
        module_service.get_for_write(db, test.module_id, actor)
    except (module_service.NotFound, module_service.NotPermitted):
        raise AttemptNotFound() from None
    return expire_if_due(db, row)


def expire_if_due(db: DbSession, row: Attempt) -> Attempt:
    """An attempt past its ending moment becomes submitted the next time anyone
    looks at it. There is no background process (research R8, FR-022)."""
    if not row.is_submitted and row.ends_at <= utcnow():
        return submit(db, row, at=row.ends_at)
    return row


def questions_for(db: DbSession, row: Attempt) -> list[QuestionRead]:
    """In the attempt's fixed order, with no `is_correct` anywhere."""
    by_id = {q.id: q for q in db.exec(select(Question)).all()}
    ordered: list[QuestionRead] = []

    for position, question_id in enumerate(row.question_order, start=1):
        question = by_id.get(question_id)
        if question is None:
            continue
        options, multiple = question_service.taking_view(db, question)
        ordered.append(
            QuestionRead(
                id=question.id,
                prompt=question.prompt,
                points=question.points,
                position=position,
                options=options,
                multiple=multiple,
            )
        )
    return ordered


def answers_for(db: DbSession, attempt_id: int) -> dict[int, list[int]]:
    rows = db.exec(
        select(AttemptAnswer).where(AttemptAnswer.attempt_id == attempt_id)
    ).all()
    return {row.question_id: list(row.selected_option_ids) for row in rows}


def remaining_seconds(row: Attempt) -> int:
    return max(0, int((row.ends_at - utcnow()).total_seconds()))


# ------------------------------------------------------------------ answering


def save_answer(
    db: DbSession, actor: User, attempt_id: int, question_id: int, option_ids: list[int]
) -> None:
    """An upsert on (attempt_id, question_id).

    An answer changed five times leaves one row, and two devices on the same
    attempt both write to it: the last one wins.
    """
    row = db.get(Attempt, attempt_id)
    if row is None or row.user_id != actor.id:
        raise AttemptNotFound()

    if row.is_submitted:
        raise AttemptClosed("This attempt has already been submitted.")

    # The server clock decides, always (FR-020, FR-021).
    if row.ends_at <= utcnow():
        submit(db, row, at=row.ends_at)
        raise AttemptClosed("Time is up. The attempt was submitted with what you had.")

    if question_id not in row.question_order:
        raise AttemptNotFound()

    existing = db.exec(
        select(AttemptAnswer).where(
            AttemptAnswer.attempt_id == attempt_id,
            AttemptAnswer.question_id == question_id,
        )
    ).first()

    if existing is None:
        db.add(
            AttemptAnswer(
                attempt_id=attempt_id,
                question_id=question_id,
                selected_option_ids=list(option_ids),
            )
        )
    else:
        existing.selected_option_ids = list(option_ids)
        db.add(existing)

    db.commit()


# ----------------------------------------------------------------- submitting


def submit(db: DbSession, row: Attempt, at=None) -> Attempt:
    """Score it. A second submission is a no-op returning the same result."""
    if row.is_submitted:
        return row

    test = db.get(Test, row.test_id)
    answers = answers_for(db, row.id)

    questions = [
        (question_id, question.points, question_service.correct_ids(db, question_id))
        for question_id in row.question_order
        if (question := db.get(Question, question_id)) is not None
    ]

    earned, possible = scoring.score(questions, answers)
    percent = scoring.percentage(earned, possible)

    row.points_earned = earned
    row.points_possible = possible
    row.score_percent = percent
    row.passed = scoring.passed(percent, test.passing_score)
    row.is_submitted = True
    row.submitted_at = at or utcnow()
    db.add(row)

    # Mark each answer, so the review can show what was right without scoring
    # anything a second time.
    for stored in db.exec(
        select(AttemptAnswer).where(AttemptAnswer.attempt_id == row.id)
    ).all():
        question = db.get(Question, stored.question_id)
        if question is None:
            continue
        correct = scoring.score_question(
            question_service.correct_ids(db, stored.question_id),
            stored.selected_option_ids,
        )
        stored.is_correct = correct
        stored.points_awarded = question.points if correct else 0
        db.add(stored)

    db.commit()
    db.refresh(row)

    # The result exists as of this moment, so the person is told as of this
    # moment (FR-016, FR-018). This runs on the timed path too: an attempt whose
    # time ran out is submitted the next time anyone reads it, and that is when
    # its result became available.
    person = db.get(User, row.user_id)
    module = db.get(Module, test.module_id)
    if person is not None and module is not None:
        notification_service.notify_result(db, person, module, test, row)

    return row


def submit_own(db: DbSession, actor: User, attempt_id: int) -> Attempt:
    row = db.get(Attempt, attempt_id)
    if row is None or row.user_id != actor.id:
        raise AttemptNotFound()
    return submit(db, row)


# ------------------------------------------------------------------ reviewing


def review(db: DbSession, row: Attempt) -> list[tuple[QuestionReview, list[int], bool | None]]:
    """Each question, what was chosen, and whether it was right.

    The correct answer travels with it: a trainee is meant to learn what they
    got wrong (FR-031).
    """
    stored = {
        answer.question_id: answer
        for answer in db.exec(
            select(AttemptAnswer).where(AttemptAnswer.attempt_id == row.id)
        ).all()
    }

    out = []
    for position, question_id in enumerate(row.question_order, start=1):
        question = db.get(Question, question_id)
        if question is None:
            continue
        options = question_service.options_for(db, question_id)
        answer = stored.get(question_id)
        out.append(
            (
                QuestionReview(
                    id=question.id,
                    prompt=question.prompt,
                    points=question.points,
                    position=position,
                    options=[
                        OptionReview(
                            id=o.id, text=o.text, position=o.position, is_correct=o.is_correct
                        )
                        for o in options
                    ],
                    multiple=sum(1 for o in options if o.is_correct) > 1,
                ),
                list(answer.selected_option_ids) if answer else [],
                answer.is_correct if answer else None,
            )
        )
    return out


def history_for(db: DbSession, actor: User, test_id: int) -> list[AttemptRead]:
    """This person's own attempts at one test, newest first (FR-030)."""
    rows = db.exec(
        select(Attempt)
        .where(Attempt.test_id == test_id, Attempt.user_id == actor.id)
        .order_by(Attempt.started_at.desc(), Attempt.id.desc())
    ).all()
    return [_read(expire_if_due(db, row)) for row in rows]


def most_recent_submitted(db: DbSession, test_id: int, user_id: int) -> Attempt | None:
    """The attempt that represents a person: the most recent, not the best.

    Phases 3 and 4 both read this rule, so it lives here once (FR-029).
    """
    return db.exec(
        select(Attempt)
        .where(
            Attempt.test_id == test_id,
            Attempt.user_id == user_id,
            Attempt.is_submitted == True,  # noqa: E712
        )
        # submitted_at is a DATETIME, so it has second precision. Without the
        # id as a tiebreak, two attempts submitted in the same second order
        # arbitrarily and "most recent" quietly returns the wrong one.
        .order_by(Attempt.submitted_at.desc(), Attempt.id.desc())
    ).first()


# --------------------------------------------------------- the instructor's view


def list_attempts_for_test(db: DbSession, actor: User, test_id: int) -> list[CohortRow]:
    test = db.get(Test, test_id)
    if test is None:
        raise AttemptNotFound()
    module_service.get_for_write(db, test.module_id, actor)

    rows = db.exec(
        select(Attempt, User)
        .join(User, User.id == Attempt.user_id)
        .where(Attempt.test_id == test_id)
        .order_by(User.full_name, Attempt.attempt_number)
    ).all()

    grouped: dict[int, CohortRow] = {}
    for attempt, person in rows:
        attempt = expire_if_due(db, attempt)
        if person.id not in grouped:
            grouped[person.id] = CohortRow(
                user_id=person.id,
                full_name=person.full_name,
                email=person.email,
                attempts=[],
            )
        grouped[person.id].attempts.append(_read(attempt))

    return list(grouped.values())


def override_score(
    db: DbSession, actor: User, attempt_id: int, data: ScoreOverride
) -> AttemptRead:
    """Replace the automatic score. Pass or fail follows the new number.

    An automatically scored test with no human override is a test whose
    mistakes cannot be undone (FR-035).
    """
    row = db.get(Attempt, attempt_id)
    if row is None:
        raise AttemptNotFound()

    test = db.get(Test, row.test_id)
    module_service.get_for_write(db, test.module_id, actor)

    row = expire_if_due(db, row)
    if not row.is_submitted:
        raise NotSubmitted("Only a finished attempt can have its score corrected.")

    row.score_percent = data.score_percent
    row.passed = scoring.passed(data.score_percent, test.passing_score)
    row.score_overridden = True
    db.add(row)
    db.commit()
    db.refresh(row)
    return _read(row)


# ---------------------------------------------------------------------- helpers


def _registration(db: DbSession, module_id: int, user_id: int) -> Registration | None:
    return db.exec(
        select(Registration).where(
            Registration.module_id == module_id, Registration.user_id == user_id
        )
    ).first()


def _submitted_count(db: DbSession, test_id: int, user_id: int) -> int:
    return len(
        db.exec(
            select(Attempt).where(
                Attempt.test_id == test_id,
                Attempt.user_id == user_id,
                Attempt.is_submitted == True,  # noqa: E712
            )
        ).all()
    )


def _read(row: Attempt) -> AttemptRead:
    return AttemptRead(
        id=row.id,
        test_id=row.test_id,
        user_id=row.user_id,
        attempt_number=row.attempt_number,
        started_at=row.started_at,
        ends_at=row.ends_at,
        submitted_at=row.submitted_at,
        is_submitted=row.is_submitted,
        score_percent=row.score_percent,
        passed=row.passed,
        score_overridden=row.score_overridden,
    )


def read(row: Attempt) -> AttemptRead:
    return _read(row)
