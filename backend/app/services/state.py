"""Where somebody stands on a module. One function, seven states, no database.

Three call sites read this, and Phase 4 added *due* and *overdue* here rather
than anywhere else. Any state computed inside a query, a template, or a second
helper would be a copy of this rule, and copies drift (research R1).

It takes rows and returns an enum. No session, and no knowledge of who is
asking. The due date it compares against is computed by `due.py` at the call
site and passed in, so this module stays ignorant of registrations.
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

    # Phase 4, decided from the due_date argument Phase 3 reserved below.
    DUE = "due"
    OVERDUE = "overdue"


#: The order outstanding things are found in, worst first (research R4).
#: Overdue outranks everything: it is the one thing that has already been missed.
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
    """Evaluated in this order, first match winning.

    `test` is the module's currently published test, or None. `attempts` are
    that person's attempts **at that test**: attempts at a test since replaced
    are excluded by the caller, which is what makes publishing a replacement
    reset the whole cohort (FR-008).

    `due_date` comes from `due.py`, computed at the call site. Where it is None
    the test does not recur and the five states stand alone, which is every test
    in the platform until an instructor sets a schedule.
    """
    if test is None or not test.is_published:
        return State.NO_TEST

    rows = list(attempts)

    if any(not attempt.is_submitted for attempt in rows):
        # They are sitting it now. Whatever a date says, that is what they are
        # doing, and telling them it is overdue while they take it is noise.
        return State.IN_PROGRESS

    submitted = [attempt for attempt in rows if attempt.is_submitted]
    if not submitted:
        return _with_due(State.NOT_STARTED, due_date)

    # The most recent, not the best. The id breaks a tie, because submitted_at
    # has second precision (FR-005).
    deciding = max(submitted, key=lambda a: (a.submitted_at, a.id))

    if deciding.passed:
        return _with_due(State.PASSED, due_date)
    return _with_due(State.FAILED, due_date)


def _with_due(settled: State, due_date: date | None) -> State:
    """The two states Phase 4 added, considered after the five above.

    Somebody who passed within the current cycle is not due, and this needs no
    separate check: `due.py` sets their date a full interval after they passed,
    so it simply has not been reached. Once it has, they have lost currency and
    the fact that they once passed is exactly what stopped mattering (FR-010,
    research R2).
    """
    if due_date is None:
        return settled

    # Naive UTC, like every other date in the project. A due date is a calendar
    # date, so the comparison is a date comparison.
    today = utcnow().date()
    if due_date < today:
        return State.OVERDUE
    if due_date <= today + timedelta(days=settings.due_soon_lead_days):
        return State.DUE
    return settled


def score_for(attempts: Iterable) -> int | None:
    """Whatever the deciding attempt scored, including an instructor's override.

    Phase 2 stores an override in the same column, so nothing here needs to know
    one happened. A state with no deciding attempt shows no score (FR-004).
    """
    submitted = [attempt for attempt in attempts if attempt.is_submitted]
    if not submitted:
        return None
    return max(submitted, key=lambda a: (a.submitted_at, a.id)).score_percent


def rank(state: State) -> int:
    """Sorting key. Outstanding things come first (FR-007, FR-020)."""
    return RANK.get(state, 9)
