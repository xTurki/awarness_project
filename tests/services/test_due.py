"""Every branch of the due-date arithmetic.

Three cases here catch real mistakes rather than typos:

* a newcomer gets a **full first cycle**, so nobody is overdue the morning after
  they are added (FR-008);
* an early **failed** attempt does not shorten that first cycle (FR-008);
* someone who passed and then retook and failed is due from **that failing
  attempt**, not from a fresh cycle (FR-009).

And the last test in this module is the one that protects FR-014: no branch ever
returns today, so an overdue row's key does not shift from one morning to the
next.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.due import due_date_for

REGISTERED = datetime(2026, 1, 1, 9, 0, 0)


def _test(interval=None, period=None):
    return SimpleNamespace(
        id=1,
        is_published=True,
        passing_score=80,
        retake_interval_days=interval,
        completion_deadline_days=period,
    )


def _registration(at=REGISTERED):
    return SimpleNamespace(id=1, user_id=1, module_id=1, registered_at=at)


def _attempt(id, submitted_at, passed):
    return SimpleNamespace(
        id=id, is_submitted=True, submitted_at=submitted_at, passed=passed
    )


# ------------------------------------------------------------- nothing to do


def test_a_test_with_neither_never_falls_due():
    """No interval and no completion period means no due date and no reminder,
    ever (FR-039)."""
    assert due_date_for(_test(), _registration(), []) is None


def test_no_test_means_no_due_date():
    assert due_date_for(None, _registration(), []) is None


def test_no_registration_means_no_due_date():
    """Removing somebody from a module stops them being due, because the row the
    derivation counts from is gone (FR-012)."""
    assert due_date_for(_test(interval=90), None, []) is None


# ------------------------------------------------------ a full first cycle


def test_a_newcomer_gets_a_full_interval_from_their_registration():
    """Registered today on a 90-day module, due in 90 days, not today (FR-008)."""
    registered = datetime(2026, 9, 11, 10, 0, 0)
    due = due_date_for(_test(interval=90), _registration(registered), [])

    assert due == date(2026, 9, 11) + timedelta(days=90)


def test_an_early_failed_attempt_does_not_shorten_the_first_cycle():
    """The case that would quietly make a newcomer overdue for failing once.

    They have never passed, so the clock still runs from their registration
    (FR-008), not from the attempt.
    """
    attempts = [_attempt(1, REGISTERED + timedelta(days=3), passed=False)]
    due = due_date_for(_test(interval=90), _registration(), attempts)

    assert due == REGISTERED.date() + timedelta(days=90)


def test_several_failed_attempts_still_do_not_shorten_it():
    attempts = [
        _attempt(1, REGISTERED + timedelta(days=3), passed=False),
        _attempt(2, REGISTERED + timedelta(days=40), passed=False),
    ]
    assert due_date_for(_test(interval=90), _registration(), attempts) == (
        REGISTERED.date() + timedelta(days=90)
    )


# --------------------------------------------------------- later cycles


def test_passing_starts_the_next_cycle_from_that_attempt():
    passed_at = REGISTERED + timedelta(days=30)
    attempts = [_attempt(1, passed_at, passed=True)]

    assert due_date_for(_test(interval=90), _registration(), attempts) == (
        passed_at.date() + timedelta(days=90)
    )


def test_passing_then_failing_is_due_from_the_failing_attempt():
    """Trainee E from the quickstart. If this returns a date 90 days out, the
    clock is running from the wrong attempt and somebody who has lost currency
    reads as current (FR-009)."""
    passed_at = REGISTERED + timedelta(days=30)
    failed_at = REGISTERED + timedelta(days=120)
    attempts = [
        _attempt(1, passed_at, passed=True),
        _attempt(2, failed_at, passed=False),
    ]

    assert due_date_for(_test(interval=90), _registration(), attempts) == failed_at.date()


def test_passing_again_after_failing_restarts_the_cycle():
    attempts = [
        _attempt(1, REGISTERED + timedelta(days=30), passed=True),
        _attempt(2, REGISTERED + timedelta(days=120), passed=False),
        _attempt(3, REGISTERED + timedelta(days=121), passed=True),
    ]

    assert due_date_for(_test(interval=90), _registration(), attempts) == (
        (REGISTERED + timedelta(days=121)).date() + timedelta(days=90)
    )


def test_the_order_the_attempts_arrive_in_does_not_matter():
    passed_at = REGISTERED + timedelta(days=30)
    failed_at = REGISTERED + timedelta(days=120)
    forwards = [_attempt(1, passed_at, True), _attempt(2, failed_at, False)]
    backwards = list(reversed(forwards))

    assert due_date_for(_test(interval=90), _registration(), forwards) == due_date_for(
        _test(interval=90), _registration(), backwards
    )


def test_the_id_breaks_a_tie_within_one_second():
    """submitted_at is a DATETIME, so two attempts can share a second."""
    same = REGISTERED + timedelta(days=30)
    attempts = [_attempt(1, same, passed=True), _attempt(2, same, passed=False)]

    assert due_date_for(_test(interval=90), _registration(), attempts) == same.date()


def test_an_unfinished_attempt_decides_nothing():
    running = SimpleNamespace(id=9, is_submitted=False, submitted_at=None, passed=None)
    assert due_date_for(_test(interval=90), _registration(), [running]) == (
        REGISTERED.date() + timedelta(days=90)
    )


# --------------------------------------------------- a completion period


def test_a_completion_period_counts_from_each_persons_registration():
    assert due_date_for(_test(period=30), _registration(), []) == (
        REGISTERED.date() + timedelta(days=30)
    )


def test_passing_a_one_off_test_ends_it_for_good():
    """It does not recur, so it never falls due again (FR-037)."""
    attempts = [_attempt(1, REGISTERED + timedelta(days=5), passed=True)]
    assert due_date_for(_test(period=30), _registration(), attempts) is None


def test_failing_a_one_off_test_leaves_the_original_deadline():
    attempts = [_attempt(1, REGISTERED + timedelta(days=5), passed=False)]
    assert due_date_for(_test(period=30), _registration(), attempts) == (
        REGISTERED.date() + timedelta(days=30)
    )


def test_an_interval_wins_where_both_are_set():
    attempts = [_attempt(1, REGISTERED + timedelta(days=5), passed=True)]
    both = _test(interval=90, period=30)

    assert due_date_for(both, _registration(), attempts) == (
        (REGISTERED + timedelta(days=5)).date() + timedelta(days=90)
    )


# ------------------------------------------- the assertion that protects FR-014


@pytest.mark.parametrize(
    "test,attempts",
    [
        (_test(interval=90), []),
        (_test(interval=90), [_attempt(1, REGISTERED + timedelta(days=2), False)]),
        (_test(interval=90), [_attempt(1, REGISTERED + timedelta(days=2), True)]),
        (
            _test(interval=90),
            [
                _attempt(1, REGISTERED + timedelta(days=2), True),
                _attempt(2, REGISTERED + timedelta(days=200), False),
            ],
        ),
        (_test(period=30), []),
        (_test(period=30), [_attempt(1, REGISTERED + timedelta(days=2), False)]),
    ],
)
def test_no_branch_returns_today_as_a_moving_value(test, attempts):
    """Every due date is a fixed calendar date derived from the rows given.

    If any branch returned "now", the key an overdue row is written under would
    move every morning, and a notification meant to arrive once would arrive
    daily. This is the bug the whole phase is shaped to prevent (FR-014).

    The assertion is that the answer is one of the dates the input rows can
    produce. Today is not among them, and cannot become one.
    """
    registration = _registration()
    interval = test.retake_interval_days
    period = test.completion_deadline_days

    derivable = {registration.registered_at.date() + timedelta(days=interval or period)}
    for row in attempts:
        derivable.add(row.submitted_at.date())
        if interval:
            derivable.add(row.submitted_at.date() + timedelta(days=interval))

    answer = due_date_for(test, registration, attempts)
    assert answer in derivable

    # And the same rows produce the same answer whenever they are asked, because
    # nothing in the computation reads a clock.
    assert due_date_for(test, registration, attempts) == answer
