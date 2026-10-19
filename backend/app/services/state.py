"""A user's state on a module (not started, in progress, passed, due, ...).

Pure function, no database access. The due date is calculated by `due.py` and
passed in.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from enum import Enum

from app.config import settings
from app.database import utcnow


class State(str, Enum):
    NO_TEST = "no test available"
    NOT_STARTED = "not started"
    IN_PROGRESS = "in progress"
    PASSED = "passed"
    FAILED = "failed"

    # Based on the due date.
    DUE = "due"
    OVERDUE = "overdue"


# Sort order for states, most urgent first.
RANK = {
    State.OVERDUE: 0,
    State.FAILED: 1,
    State.DUE: 2,
    State.NOT_STARTED: 3,
    State.IN_PROGRESS: 4,
    State.PASSED: 5,
    State.NO_TEST: 6,
}


def state_for(test, attempts: Iterable, due_date: date | None = None) -> State:
    """Work out the user's state on a module.

    `test` is the current published test (or None) and `attempts` are the
    user's attempts at that test only. `due_date` comes from `due.py`.
    """
    if test is None or not test.is_published:
        return State.NO_TEST

    rows = list(attempts)

    if any(not attempt.is_submitted for attempt in rows):
        # An attempt in progress takes priority over due/overdue.
        return State.IN_PROGRESS

    submitted = [attempt for attempt in rows if attempt.is_submitted]
    if not submitted:
        return _with_due(State.NOT_STARTED, due_date)

    # Use the latest attempt (id breaks ties).
    deciding = max(submitted, key=lambda a: (a.submitted_at, a.id))

    if deciding.passed:
        return _with_due(State.PASSED, due_date)
    return _with_due(State.FAILED, due_date)


def _with_due(settled: State, due_date: date | None) -> State:
    """Apply the due/overdue states based on the due date."""
    if due_date is None:
        return settled

    # Compare calendar dates (UTC).
    today = utcnow().date()
    if due_date < today:
        return State.OVERDUE
    if due_date <= today + timedelta(days=settings.due_soon_lead_days):
        return State.DUE
    return settled


def score_for(attempts: Iterable) -> int | None:
    """Score of the latest submitted attempt (includes overrides), or None."""
    submitted = [attempt for attempt in attempts if attempt.is_submitted]
    if not submitted:
        return None
    return max(submitted, key=lambda a: (a.submitted_at, a.id)).score_percent


def rank(state: State) -> int:
    """Sort key: most urgent states first."""
    return RANK.get(state, 9)
