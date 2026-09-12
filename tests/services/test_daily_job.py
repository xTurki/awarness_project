"""The scheduled run, and the thing it must never do twice.

The first test in this module is the one the whole phase is shaped around: run
the job twice for the same date and assert that the second run created nothing
and sent nothing. Everything else here is a consequence of that design.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlmodel import select

from app.config import settings
from app.models.attempt import Attempt
from app.models.module import Module
from app.models.notification import Notification
from app.models.registration import Registration
from app.schemas.quiz import QuestionWrite, TestWrite
from app.services import daily_job, question_service, test_service

INTERVAL = 90
TODAY = date(2027, 3, 15)


# --------------------------------------------------------------- the fixtures


@pytest.fixture()
def owner(db, make_user):
    return make_user(email="owner@example.com", role="instructor")


@pytest.fixture()
def make_module(db, owner):
    def _make(title: str, interval: int | None = INTERVAL, period: int | None = None):
        module = Module(title=title, is_published=True)
        db.add(module)
        db.commit()
        db.refresh(module)
        db.add(
            Registration(
                user_id=owner.id, module_id=module.id, role_in_module="instructor"
            )
        )
        db.commit()

        questions = [
            question_service.create_question(
                db, owner, module.id,
                QuestionWrite(prompt=f"Q{n}?", points=1, options=["a", "b"], correct=[0]),
            )
            for n in (1, 2)
        ]
        created = test_service.create(
            db, owner, module.id,
            TestWrite(
                title=f"{title} check",
                allowed_attempts=3,
                passing_score=80,
                retake_interval_days=interval,
                completion_deadline_days=period,
                question_ids=[q.id for q in questions],
            ),
        )
        test_service.set_published(db, owner, created.id, True)
        return module, created

    return _make


@pytest.fixture()
def enrol(db):
    def _enrol(person, module, days_ago: int):
        row = Registration(
            user_id=person.id,
            module_id=module.id,
            role_in_module="trainee",
            registered_at=datetime.combine(
                TODAY - timedelta(days=days_ago), datetime.min.time()
            ),
        )
        db.add(row)
        db.commit()
        return row

    return _enrol


@pytest.fixture()
def attempted(db):
    """A finished attempt, written directly: the point here is the date it
    carries, not the taking of it."""

    def _attempt(person, test, days_ago: int, passed: bool):
        when = datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time())
        row = Attempt(
            test_id=test.id,
            user_id=person.id,
            attempt_number=1,
            started_at=when,
            ends_at=when + timedelta(hours=1),
            submitted_at=when,
            is_submitted=True,
            question_order=[],
            score_percent=90 if passed else 40,
            passed=passed,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    return _attempt


def _notifications(db, user_id=None) -> list[Notification]:
    query = select(Notification).where(
        Notification.kind.in_(("due_soon", "overdue"))
    )
    if user_id is not None:
        query = query.where(Notification.user_id == user_id)
    return list(db.exec(query.order_by(Notification.id)).all())


# ------------------------------------------------------- running it twice


def test_a_second_run_for_the_same_date_changes_nothing(
    db, mail, make_user, make_module, enrol, attempted
):
    """The assertion the phase exists to satisfy (FR-024, SC-003).

    Idempotency comes from the unique constraint, not from the job remembering
    that it ran. A `last_run` record would look like the obvious solution and
    would be wrong after a restart, a clock change, or a half-completed run.
    """
    person = make_user(email="a@example.com", full_name="A Person")
    module, test = make_module("Phishing")
    enrol(person, module, days_ago=200)
    attempted(person, test, days_ago=100, passed=True)

    first = daily_job.run_daily(db, TODAY)
    assert first.created == 1
    assert first.messages_sent == 1
    assert len(mail) == 1

    second = daily_job.run_daily(db, TODAY)

    assert second.created == 0, "a second run created a record"
    assert second.messages_sent == 0, "a second run sent a message"
    assert len(_notifications(db)) == 1
    assert len(mail) == 1


def test_a_third_and_fourth_run_are_equally_harmless(
    db, mail, make_user, make_module, enrol, attempted
):
    person = make_user(email="a@example.com")
    module, test = make_module("Phishing")
    enrol(person, module, days_ago=200)
    attempted(person, test, days_ago=100, passed=True)

    for _ in range(4):
        daily_job.run_daily(db, TODAY)

    assert len(_notifications(db)) == 1
    assert len(mail) == 1


# ----------------------------------------------------------- who is picked up


def test_someone_overdue_is_told_it_has_lapsed(
    db, mail, make_user, make_module, enrol, attempted
):
    person = make_user(email="a@example.com")
    module, test = make_module("Phishing")
    enrol(person, module, days_ago=200)
    attempted(person, test, days_ago=100, passed=True)

    daily_job.run_daily(db, TODAY)

    rows = _notifications(db, person.id)
    assert [row.kind for row in rows] == ["overdue"]
    assert rows[0].due_date == TODAY - timedelta(days=10)


def test_someone_approaching_is_warned_before_it_lapses(
    db, mail, make_user, make_module, enrol, attempted
):
    """Passed 76 days ago on a 90-day interval: due in 14 days, which is the
    warning period exactly."""
    person = make_user(email="b@example.com")
    module, test = make_module("Phishing")
    enrol(person, module, days_ago=200)
    attempted(person, test, days_ago=INTERVAL - settings.due_soon_lead_days, passed=True)

    daily_job.run_daily(db, TODAY)

    assert [row.kind for row in _notifications(db, person.id)] == ["due_soon"]


def test_someone_who_passed_recently_hears_nothing(
    db, mail, make_user, make_module, enrol, attempted
):
    person = make_user(email="c@example.com")
    module, test = make_module("Phishing")
    enrol(person, module, days_ago=200)
    attempted(person, test, days_ago=5, passed=True)

    daily_job.run_daily(db, TODAY)

    assert _notifications(db, person.id) == []
    assert mail == []


def test_a_newcomer_hears_nothing(db, mail, make_user, make_module, enrol):
    """Registered yesterday, so they have their own full interval (FR-008)."""
    person = make_user(email="f@example.com")
    module, _ = make_module("Phishing")
    enrol(person, module, days_ago=1)

    daily_job.run_daily(db, TODAY)

    assert _notifications(db, person.id) == []


def test_a_newcomer_who_failed_once_still_hears_nothing(
    db, mail, make_user, make_module, enrol, attempted
):
    """A failed attempt does not shorten a first cycle (FR-008)."""
    person = make_user(email="g@example.com")
    module, test = make_module("Phishing")
    enrol(person, module, days_ago=1)
    attempted(person, test, days_ago=0, passed=False)

    daily_job.run_daily(db, TODAY)

    assert _notifications(db, person.id) == []


def test_never_attempted_and_registered_long_ago_is_overdue(
    db, mail, make_user, make_module, enrol
):
    person = make_user(email="d@example.com")
    module, _ = make_module("Phishing")
    enrol(person, module, days_ago=200)

    daily_job.run_daily(db, TODAY)

    assert [row.kind for row in _notifications(db, person.id)] == ["overdue"]


def test_a_test_with_no_schedule_never_produces_anything(
    db, mail, make_user, make_module, enrol
):
    """No interval and no completion period means nobody is ever chased
    (FR-039, SC-016)."""
    person = make_user(email="h@example.com")
    module, _ = make_module("One off", interval=None)
    enrol(person, module, days_ago=2000)

    summary = daily_job.run_daily(db, TODAY)

    assert summary.created == 0
    assert _notifications(db) == []


def test_an_instructor_is_not_chased_about_their_own_module(
    db, mail, owner, make_module
):
    """Only trainee registrations fall due. A module somebody runs is not
    training they owe."""
    module, _ = make_module("Phishing")

    daily_job.run_daily(db, TODAY)

    assert _notifications(db, owner.id) == []


# --------------------------------------------------------- one email, many rows


def test_overdue_on_three_modules_is_one_email_and_three_records(
    db, mail, make_user, make_module, enrol
):
    """FR-019 with FR-034: the record and the message are different things."""
    person = make_user(email="busy@example.com", full_name="Busy Person")
    for title in ("Phishing", "Passwords", "Devices"):
        module, _ = make_module(title)
        enrol(person, module, days_ago=200)

    daily_job.run_daily(db, TODAY)

    assert len(_notifications(db, person.id)) == 3
    assert len(mail) == 1

    to, subject, body = mail[0]
    assert to == "busy@example.com"
    for title in ("Phishing", "Passwords", "Devices"):
        assert title in body


def test_two_people_get_a_message_each(db, mail, make_user, make_module, enrol):
    module, _ = make_module("Phishing")
    for address in ("one@example.com", "two@example.com"):
        enrol(make_user(email=address), module, days_ago=200)

    daily_job.run_daily(db, TODAY)

    assert len(mail) == 2
    assert {to for to, _, _ in mail} == {"one@example.com", "two@example.com"}


# ------------------------------------------------------------- catching up


def test_a_run_skipped_for_days_catches_everyone_up(
    db, mail, make_user, make_module, enrol, attempted
):
    """The job asks who is due now, never what changed since last time, so a
    week of missed runs costs nobody anything (FR-027, SC-006)."""
    person = make_user(email="a@example.com")
    module, test = make_module("Phishing")
    enrol(person, module, days_ago=200)
    attempted(person, test, days_ago=100, passed=True)

    # Nobody ran it for a week. The first run afterwards finds them anyway.
    late = daily_job.run_daily(db, TODAY + timedelta(days=7))

    assert late.created == 1
    assert [row.kind for row in _notifications(db, person.id)] == ["overdue"]


def test_running_it_for_a_later_date_does_not_repeat_an_overdue_notice(
    db, mail, make_user, make_module, enrol, attempted
):
    """Seven days later the same person is still overdue and hears nothing
    further. Their due date has not moved, so the row is the same row (FR-014,
    SC-005 pattern)."""
    person = make_user(email="a@example.com")
    module, test = make_module("Phishing")
    enrol(person, module, days_ago=200)
    attempted(person, test, days_ago=100, passed=True)

    daily_job.run_daily(db, TODAY)
    daily_job.run_daily(db, TODAY + timedelta(days=7))

    assert len(_notifications(db, person.id)) == 1
    assert len(mail) == 1


# --------------------------------------------------------------- passing again


def test_retaking_and_passing_stops_the_chasing(
    db, mail, make_user, make_module, enrol, attempted
):
    """FR-011, SC-005: they are no longer due, and their next date is a full
    interval from the attempt that passed."""
    person = make_user(email="a@example.com")
    module, test = make_module("Phishing")
    enrol(person, module, days_ago=200)
    attempted(person, test, days_ago=100, passed=True)

    daily_job.run_daily(db, TODAY)
    assert len(mail) == 1

    # They put it right today.
    attempted(person, test, days_ago=0, passed=True)

    daily_job.run_daily(db, TODAY + timedelta(days=1))

    assert len(mail) == 1, "somebody who has passed was chased again"
    assert len(_notifications(db, person.id)) == 1


# --------------------------------------------------------- a completion period


def test_a_completion_period_counts_from_each_persons_own_registration(
    db, mail, make_user, make_module, enrol
):
    module, _ = make_module("Induction", interval=None, period=30)
    late = make_user(email="late@example.com")
    fresh = make_user(email="fresh@example.com")
    enrol(late, module, days_ago=60)
    enrol(fresh, module, days_ago=1)

    daily_job.run_daily(db, TODAY)

    assert [row.kind for row in _notifications(db, late.id)] == ["overdue"]
    assert _notifications(db, fresh.id) == []


def test_passing_a_one_off_test_ends_it(
    db, mail, make_user, make_module, enrol, attempted
):
    module, test = make_module("Induction", interval=None, period=30)
    person = make_user(email="done@example.com")
    enrol(person, module, days_ago=60)
    attempted(person, test, days_ago=50, passed=True)

    daily_job.run_daily(db, TODAY)

    assert _notifications(db, person.id) == []


# ------------------------------------------------- what the scheduler calls


def test_the_scheduler_entry_point_builds_its_own_session_and_runs(
    db, engine, mail, monkeypatch, make_user, make_module, enrol
):
    """`run_now` is the function the cron job is given, and nothing else covers
    it: every other test here hands `run_daily` a session already built.

    That gap let a real failure through. `main.py` imports the session *table*
    as `Session`, so a database session built there constructed a row instead,
    and the scheduled run died with "takes 1 positional argument but 2 were
    given" every night while the whole suite stayed green.
    """
    person = make_user(email="a@example.com")
    module, _ = make_module("Phishing")
    enrol(person, module, days_ago=2000)
    # Committed through the fixture's connection, so the separate session this
    # opens can see it.
    db.commit()

    monkeypatch.setattr(daily_job, "engine", engine)
    summary = daily_job.run_now()

    assert summary is not None, "the scheduled entry point failed and was swallowed"
    assert isinstance(summary, daily_job.RunSummary)


# ----------------------------------------------------------- a replacement test


def test_a_replacement_test_makes_everyone_due_on_the_next_run(
    db, mail, owner, make_user, make_module, enrol, attempted
):
    """No grace period and no suppression: the instructor was warned before
    publishing exactly what it would do (FR-020, Phase 3 FR-027).

    State follows the module's currently published test, and nobody has
    attempted this one, so their clock runs from their registration again.
    """
    person = make_user(email="a@example.com")
    module, original = make_module("Phishing")
    enrol(person, module, days_ago=200)
    attempted(person, original, days_ago=5, passed=True)

    # Nothing to say: they passed five days ago on a 90-day interval.
    assert daily_job.run_daily(db, TODAY).created == 0

    questions = [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt="New Q?", points=1, options=["a", "b"], correct=[0]),
        )
    ]
    replacement = test_service.create(
        db, owner, module.id,
        TestWrite(
            title="Phishing check, revised",
            allowed_attempts=3,
            passing_score=80,
            retake_interval_days=INTERVAL,
            question_ids=[q.id for q in questions],
        ),
    )
    test_service.set_published(db, owner, replacement.id, True)

    after = daily_job.run_daily(db, TODAY)

    assert after.created == 1
    assert [row.kind for row in _notifications(db, person.id)] == ["overdue"]


def test_attempts_at_the_replaced_test_decide_nothing(
    db, mail, owner, make_user, make_module, enrol, attempted
):
    """Their pass is still in their history. It simply stops deciding whether
    they are current, which is the same rule Phase 3 applies to state."""
    person = make_user(email="a@example.com")
    module, original = make_module("Phishing")
    enrol(person, module, days_ago=200)
    attempted(person, original, days_ago=1, passed=True)

    questions = [
        question_service.create_question(
            db, owner, module.id,
            QuestionWrite(prompt="New Q?", points=1, options=["a", "b"], correct=[0]),
        )
    ]
    replacement = test_service.create(
        db, owner, module.id,
        TestWrite(
            title="Revised",
            allowed_attempts=3,
            passing_score=80,
            retake_interval_days=INTERVAL,
            question_ids=[q.id for q in questions],
        ),
    )
    test_service.set_published(db, owner, replacement.id, True)

    daily_job.run_daily(db, TODAY)

    assert [row.kind for row in _notifications(db, person.id)] == ["overdue"]
