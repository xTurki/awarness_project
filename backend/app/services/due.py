"""Due date calculation (pure function, no database access).

Always returns a fixed date (never "today"), so the overdue notification key
stays the same and is only created once. Due dates are calculated, not stored,
so changing a test's interval updates everyone.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta


def due_date_for(test, registration, attempts: Iterable) -> date | None:
    """Return when the user is next due for this test, or None.

    `test` is the module's current published test (or None), `registration` the
    user's registration on the module, and `attempts` their attempts at the test.
    """
    if test is None or registration is None:
        return None

    interval = getattr(test, "retake_interval_days", None)
    period = getattr(test, "completion_deadline_days", None)

    # No interval and no deadline: never due.
    if not interval and not period:
        return None

    submitted = [row for row in attempts if row.is_submitted and row.submitted_at]
    # Use the latest attempt (id breaks ties since submitted_at is in seconds).
    latest = max(submitted, key=lambda row: (row.submitted_at, row.id)) if submitted else None
    ever_passed = any(row.passed for row in submitted)

    if interval:
        if not ever_passed:
            # Never passed: due one full interval after registration.
            return registration.registered_at.date() + timedelta(days=interval)

        if latest.passed:
            return latest.submitted_at.date() + timedelta(days=interval)

        # Passed before but failed the latest attempt: due from that attempt.
        return latest.submitted_at.date()

    # One-off test with a deadline: once passed it is never due again.
    if ever_passed:
        return None
    return registration.registered_at.date() + timedelta(days=period)
