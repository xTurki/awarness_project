"""When somebody's training next falls due. One function, no database.

Alongside `scoring.py` and `state.py`: given rows, return an answer. No session,
no clock, nothing about who is asking. Due-date arithmetic has the most cases in
this phase and is the easiest thing to get subtly wrong, so it is a table-driven
test rather than something spread across a job and a page (research R1).

**Every branch returns a fixed calendar date, and none returns today.** That is
what makes an overdue notification a single event: the date an `overdue` row is
keyed on is the same tomorrow morning as it is this one, so the second insert is
refused. A branch returning *now* would move that key daily and turn one notice
into a stream of them (FR-009, FR-014).

There is no `due_at` column anywhere. Deriving is what makes FR-007 true: an
instructor changing the interval re-dates everyone at once, with nothing to
migrate and nothing to backfill.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta


def due_date_for(test, registration, attempts: Iterable) -> date | None:
    """The date this person's training on this test next falls due, or None.

    `test` is the module's currently published test, or None. `registration` is
    that person's registration on the module: without one there is nothing to
    count from, and removing it stops them being due at all (FR-012).
    `attempts` are their attempts at that test.
    """
    if test is None or registration is None:
        return None

    interval = getattr(test, "retake_interval_days", None)
    period = getattr(test, "completion_deadline_days", None)

    # Neither set: this test never falls due, and no reminder is ever generated
    # for it (FR-039).
    if not interval and not period:
        return None

    submitted = [row for row in attempts if row.is_submitted and row.submitted_at]
    # The most recent, not the best, with the id breaking a tie because
    # submitted_at has second precision. The same rule Phases 2 and 3 use to
    # decide what represents a person, applied to dates.
    latest = max(submitted, key=lambda row: (row.submitted_at, row.id)) if submitted else None
    ever_passed = any(row.passed for row in submitted)

    if interval:
        if not ever_passed:
            # A full first cycle from their own registration, whether or not
            # they have attempted and failed. A newcomer is not overdue the
            # morning after they are added, and a failed attempt does not
            # shorten the time they were given (FR-008).
            return registration.registered_at.date() + timedelta(days=interval)

        if latest.passed:
            return latest.submitted_at.date() + timedelta(days=interval)

        # They passed at some earlier point and their most recent attempt did
        # not. They have lost currency as of that attempt, so it is the due
        # date rather than the start of a fresh cycle (FR-009).
        return latest.submitted_at.date()

    # A completion period, and no interval. Passing it once ends it: this test
    # does not recur, so it never falls due again (FR-037).
    if ever_passed:
        return None
    return registration.registered_at.date() + timedelta(days=period)
