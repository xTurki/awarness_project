"""The due and overdue states.

The due date itself is tested in test_due.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.config import settings
from app.database import utcnow
from app.services.state import State, rank, state_for

TODAY = utcnow().date()
LEAD = settings.due_soon_lead_days


def _test(published=True):
    return SimpleNamespace(id=1, is_published=published, passing_score=80)


def _attempt(id, passed, days_ago=1, submitted=True):
    return SimpleNamespace(
        id=id,
        is_submitted=submitted,
        submitted_at=datetime.combine(TODAY - timedelta(days=days_ago), datetime.min.time()),
        score_percent=90 if passed else 40,
        passed=passed,
    )


# ------------------------------------------------------------------ the two


def test_a_due_date_in_the_past_is_overdue():
    rows = [_attempt(1, passed=True, days_ago=100)]
    assert state_for(_test(), rows, TODAY - timedelta(days=10)) is State.OVERDUE


def test_a_due_date_inside_the_warning_period_is_due():
    rows = [_attempt(1, passed=True, days_ago=80)]
    assert state_for(_test(), rows, TODAY + timedelta(days=LEAD - 1)) is State.DUE


def test_a_due_date_today_is_due_not_overdue():
    """A due date of today is "due"; it becomes "overdue" tomorrow."""
    assert state_for(_test(), [_attempt(1, passed=False)], TODAY) is State.DUE


def test_a_due_date_beyond_the_warning_period_changes_nothing():
    rows = [_attempt(1, passed=True, days_ago=5)]
    assert state_for(_test(), rows, TODAY + timedelta(days=LEAD + 1)) is State.PASSED


def test_the_last_day_of_the_warning_period_still_counts():
    rows = [_attempt(1, passed=True, days_ago=5)]
    assert state_for(_test(), rows, TODAY + timedelta(days=LEAD)) is State.DUE


# --------------------------------------------------- where they do not apply


def test_no_due_date_leaves_the_five_states_untouched():
    """No due date keeps the normal states."""
    assert state_for(_test(), [_attempt(1, passed=True)]) is State.PASSED
    assert state_for(_test(), [_attempt(1, passed=False)]) is State.FAILED
    assert state_for(_test(), []) is State.NOT_STARTED


def test_a_newcomer_registered_today_is_neither_due_nor_overdue():
    """Someone registered today is not due."""
    assert state_for(_test(), [], TODAY + timedelta(days=90)) is State.NOT_STARTED


def test_an_attempt_in_progress_wins_over_any_date():
    """An attempt in progress shows as in progress, not overdue."""
    running = _attempt(9, passed=None, submitted=False)
    assert state_for(_test(), [running], TODAY - timedelta(days=30)) is State.IN_PROGRESS


def test_an_unpublished_test_is_still_no_test():
    assert state_for(_test(published=False), [], TODAY - timedelta(days=1)) is State.NO_TEST


def test_passing_clears_both():
    """Passing again clears due and overdue."""
    fresh = [_attempt(2, passed=True, days_ago=0)]
    assert state_for(_test(), fresh, TODAY + timedelta(days=90)) is State.PASSED


# ------------------------------------------------------------------ ordering


def test_overdue_sorts_above_everything():
    order = sorted(
        [State.PASSED, State.NOT_STARTED, State.DUE, State.OVERDUE, State.FAILED],
        key=rank,
    )
    assert order[0] is State.OVERDUE
    assert order.index(State.DUE) < order.index(State.PASSED)


def test_basic_state_order_is_unchanged():
    """The original five states keep their sort order."""
    order = sorted(
        [State.PASSED, State.NO_TEST, State.FAILED, State.IN_PROGRESS, State.NOT_STARTED],
        key=rank,
    )
    assert order == [
        State.FAILED,
        State.NOT_STARTED,
        State.IN_PROGRESS,
        State.PASSED,
        State.NO_TEST,
    ]


# ---------------------------------------------------------------- exhaustive


@pytest.mark.parametrize(
    "days_until_due,expected",
    [
        (-100, State.OVERDUE),
        (-1, State.OVERDUE),
        (0, State.DUE),
        (LEAD, State.DUE),
        (LEAD + 1, State.PASSED),
        (365, State.PASSED),
    ],
)
def test_the_whole_line(days_until_due, expected):
    rows = [_attempt(1, passed=True, days_ago=5)]
    assert state_for(_test(), rows, TODAY + timedelta(days=days_until_due)) is expected
