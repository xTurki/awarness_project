"""Starting, answering, submitting and reviewing test attempts.

- Each answer is saved immediately (upsert).
- `ends_at` and `question_order` are fixed when the attempt starts.
- Time limits are checked on the server, not the browser.
- Expired attempts are submitted automatically the next time they are loaded.
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


class OutsideWindow(Exception):
    pass


class NoAttemptsLeft(Exception):
    pass


class AttemptClosed(Exception):
    """The attempt's time is up."""


class NotSubmitted(Exception):
    """Can't override the score of an attempt still in progress."""


class CannotStart(NamedTuple):
    """Reason a user can't start a test.

    `moment` is kept separate so the page can show it in the user's local time.
    """

    text: str
    at: datetime | None = None


# ------------------------------------------------------------------- starting


def start(db: DbSession, actor: User, test_id: int) -> Attempt:
    """Start a new attempt, or resume the one in progress (max one per test)."""
    test = db.get(Test, test_id)
    if test is None:
        raise AttemptNotFound()

    try:
        module_service.get_for(db, test.module_id, actor)
    except module_service.NotFound:
        # 404 if the user can't see the module.
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
    refusal = _limit_reached(db, test, actor.id)
    if refusal:
        raise NoAttemptsLeft(refusal)

    questions = test_service.questions_of(db, test_id)
    order = [q.id for q in questions]
    if test.shuffle_questions:
        random.shuffle(order)

    row = Attempt(
        test_id=test_id,
        user_id=actor.id,
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
    """Return None if the user can start the test, otherwise the reason.

    Must stay in sync with the checks in `start` (a test checks this).
    """
    if test is None or not test.is_published:
        return CannotStart("This test is not published yet.")

    if _registration(db, test.module_id, actor.id) is None:
        return CannotStart(
            "You are not registered on this module, so you cannot sit its test. "
            "Ask whoever runs it to add you."
        )

    # An attempt in progress can always be resumed, even outside the window.
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

    refusal = _limit_reached(db, test, actor.id)
    if refusal:
        return CannotStart(refusal)

    return None


def _ending_moment(started_at, test: Test):
    """min(started_at + time limit, closes_at). Calculated once at start."""
    candidates = []
    if test.time_limit_minutes:
        candidates.append(started_at + timedelta(minutes=test.time_limit_minutes))
    if test.closes_at:
        candidates.append(test.closes_at)
    if not candidates:
        # No time limit and no close date.
        return started_at + timedelta(days=365)
    return min(candidates)


# -------------------------------------------------------------------- reading


def get_own(db: DbSession, actor: User, attempt_id: int) -> Attempt:
    row = db.get(Attempt, attempt_id)
    if row is None or row.user_id != actor.id:
        raise AttemptNotFound()
    return expire_if_due(db, row)


def get_viewable(db: DbSession, actor: User, attempt_id: int) -> Attempt:
    """Get an attempt if the user owns it or instructs the module."""
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
    """Submit the attempt if its time has run out."""
    if not row.is_submitted and row.ends_at <= utcnow():
        return submit(db, row, at=row.ends_at)
    return row


def questions_for(db: DbSession, row: Attempt) -> list[QuestionRead]:
    """Questions in the attempt's order, without correct answers."""
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
    """Save an answer (upsert on attempt_id + question_id; last write wins)."""
    row = db.get(Attempt, attempt_id)
    if row is None or row.user_id != actor.id:
        raise AttemptNotFound()

    if row.is_submitted:
        raise AttemptClosed("This attempt has already been submitted.")

    # Check time on the server.
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
    """Score and submit the attempt. Submitting again does nothing."""
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

    # Store per-answer results for the review page.
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

    # Notify the user of the result (also runs for auto-submitted attempts).
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
    """Each question with the chosen and correct answers."""
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
    """The user's attempts on a test, newest first."""
    rows = db.exec(
        select(Attempt)
        .where(Attempt.test_id == test_id, Attempt.user_id == actor.id)
        .order_by(Attempt.started_at.desc(), Attempt.id.desc())
    ).all()
    return [_read(expire_if_due(db, row)) for row in rows]


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
    """Override the score (pass/fail is recalculated)."""
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


def _limit_reached(db: DbSession, test: Test, user_id: int) -> str | None:
    """Return a message if no attempts are left, else None.

    0 means unlimited. For recurring tests only attempts since the last pass count.
    """
    limit = test.allowed_attempts
    if not limit:
        return None

    submitted = db.exec(
        select(Attempt).where(
            Attempt.test_id == test.id,
            Attempt.user_id == user_id,
            Attempt.is_submitted == True,  # noqa: E712
        )
    ).all()

    if test.retake_interval_days:
        passes = [row for row in submitted if row.passed]
        if passes:
            last = max(passes, key=lambda row: (row.submitted_at, row.id))
            submitted = [
                row for row in submitted
                if (row.submitted_at, row.id) > (last.submitted_at, last.id)
            ]
        if len(submitted) >= limit:
            return f"You have used all {limit} permitted attempts in this cycle."
        return None

    if len(submitted) >= limit:
        return f"You have used all {limit} permitted attempts at this test."
    return None


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
