"""Due date calculation (`due.due_date_for`)."""

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
    """No interval and no deadline: no due date."""
    assert due_date_for(_test(), _registration(), []) is None


def test_no_test_means_no_due_date():
    assert due_date_for(None, _registration(), []) is None


def test_no_registration_means_no_due_date():
    """Without a registration there is no due date."""
    assert due_date_for(_test(interval=90), None, []) is None


# ------------------------------------------------------ a full first cycle


def test_a_newcomer_gets_a_full_interval_from_their_registration():
    """Registered today on a 90-day interval: due in 90 days."""
    registered = datetime(2026, 9, 11, 10, 0, 0)
    due = due_date_for(_test(interval=90), _registration(registered), [])

    assert due == date(2026, 9, 11) + timedelta(days=90)


def test_an_early_failed_attempt_does_not_shorten_the_first_cycle():
    """A failed attempt before any pass doesn't change the first due date."""
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
    """Passed, then failed a retake: due from the failed attempt."""
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
    """Attempts in the same second are ordered by id."""
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
    """A passed one-off test is never due again."""
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


# ------------------------------------------------------ fixed dates only


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
    """The due date is always derived from the input dates, never "today".

    Otherwise the overdue notification key would change every day.
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

    # Same input, same result.
    assert due_date_for(test, registration, attempts) == answer
