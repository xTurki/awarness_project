"""The state rule, across every combination.

Two cases here catch real mistakes rather than typos: most recent rather than
best, and attempts at a replaced test not counting. Both are the kind of error
that produces a plausible wrong answer and no complaint.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from app.services.state import State, rank, score_for, state_for

NOW = datetime(2026, 9, 10, 12, 0, 0)


def _test(published=True, passing_score=80):
    return SimpleNamespace(id=1, is_published=published, passing_score=passing_score)


def _attempt(id, submitted=True, score=None, passed=None, minutes_ago=0):
    return SimpleNamespace(
        id=id,
        is_submitted=submitted,
        submitted_at=NOW - timedelta(minutes=minutes_ago) if submitted else None,
        score_percent=score,
        passed=passed,
    )


# ------------------------------------------------------------- the five states


def test_no_test_on_the_module():
    assert state_for(None, []) is State.NO_TEST


def test_an_unpublished_test_is_the_same_as_none():
    """Distinct from "not started": there is nothing to complete (FR-006)."""
    assert state_for(_test(published=False), []) is State.NO_TEST


def test_a_published_test_never_attempted_is_not_started():
    assert state_for(_test(), []) is State.NOT_STARTED


def test_an_unsubmitted_attempt_is_in_progress():
    assert state_for(_test(), [_attempt(1, submitted=False)]) is State.IN_PROGRESS


def test_in_progress_wins_over_an_earlier_submitted_attempt():
    """Somebody retaking is in progress, whatever they scored last time."""
    rows = [_attempt(1, score=100, passed=True, minutes_ago=60), _attempt(2, submitted=False)]
    assert state_for(_test(), rows) is State.IN_PROGRESS


def test_a_passing_attempt_is_passed():
    assert state_for(_test(), [_attempt(1, score=90, passed=True)]) is State.PASSED


def test_a_failing_attempt_is_failed():
    assert state_for(_test(), [_attempt(1, score=40, passed=False)]) is State.FAILED


# ------------------------------------------------- most recent, not the best


def test_forty_then_ninety_then_seventy_is_failed_at_seventy():
    """The case the specification names. If this returns passed, the rule has
    quietly become "best attempt" (FR-005)."""
    rows = [
        _attempt(1, score=40, passed=False, minutes_ago=30),
        _attempt(2, score=90, passed=True, minutes_ago=20),
        _attempt(3, score=70, passed=False, minutes_ago=10),
    ]

    assert state_for(_test(), rows) is State.FAILED
    assert score_for(rows) == 70


def test_the_id_breaks_a_tie_when_two_land_in_the_same_second():
    """submitted_at is a DATETIME with second precision, so without the id the
    ordering is arbitrary."""
    rows = [
        _attempt(1, score=100, passed=True, minutes_ago=0),
        _attempt(2, score=20, passed=False, minutes_ago=0),
    ]
    assert state_for(_test(), rows) is State.FAILED
    assert score_for(rows) == 20


def test_the_order_the_rows_arrive_in_does_not_matter():
    rows = [
        _attempt(3, score=70, passed=False, minutes_ago=10),
        _attempt(1, score=40, passed=False, minutes_ago=30),
        _attempt(2, score=90, passed=True, minutes_ago=20),
    ]
    assert score_for(rows) == 70


# --------------------------------------------------------------- the score


def test_no_deciding_attempt_shows_no_score():
    assert score_for([]) is None
    assert score_for([_attempt(1, submitted=False)]) is None


def test_an_overridden_score_is_simply_the_score():
    """Phase 2 stores an override in the same column, so nothing here knows."""
    assert score_for([_attempt(1, score=90, passed=True)]) == 90


# ------------------------------------------------------- a replaced test


def test_attempts_at_a_replaced_test_are_excluded_by_the_caller():
    """The filtering happens in the query. Given only the current test's
    attempts, which is none, the state is not started (FR-008)."""
    replacement = _test()
    assert state_for(replacement, []) is State.NOT_STARTED


# ------------------------------------------------------------------ ordering


def test_outstanding_things_rank_before_completed_ones():
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


# --------------------------------------------------- the argument Phase 4 uses


def test_no_due_date_leaves_these_five_exactly_as_they_were():
    """The reservation worked: Phase 4 added two states without changing a
    single caller, and a test with no schedule still reads as it always did.

    What the argument does when it carries a date belongs to Phase 4 and is
    tested in `test_state_due.py`.
    """
    rows = [_attempt(1, score=90, passed=True)]
    assert state_for(_test(), rows) is State.PASSED
    assert state_for(_test(), rows, due_date=None) is State.PASSED


def test_the_enum_already_names_the_two_states_phase_four_adds():
    assert State.DUE.value == "due"
    assert State.OVERDUE.value == "overdue"


# ---------------------------------------------------------------- exhaustive


@pytest.mark.parametrize(
    "test,rows,expected",
    [
        (None, [], State.NO_TEST),
        (_test(published=False), [_attempt(1, passed=True)], State.NO_TEST),
        (_test(), [], State.NOT_STARTED),
        (_test(), [_attempt(1, submitted=False)], State.IN_PROGRESS),
        (_test(), [_attempt(1, score=100, passed=True)], State.PASSED),
        (_test(), [_attempt(1, score=0, passed=False)], State.FAILED),
    ],
)
def test_the_whole_matrix(test, rows, expected):
    assert state_for(test, rows) is expected
