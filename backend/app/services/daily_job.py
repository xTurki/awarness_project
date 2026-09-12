"""The one thing this platform does without being asked.

`run_daily` is an ordinary function taking a session and a date. The scheduler
calls it; a test calls it directly for any day it likes. Nothing about it
requires a scheduler to be running, which is why the hard parts of this phase
are testable at all.

**It is a full sweep, not a delta.** It asks who is due *now*, never what
changed since last time, and there is no `last_run` record anywhere. A stored
last-run is wrong after a restart, wrong if the clock moves, and wrong if a run
half-completed; a missed day, a manual run, and a run repeated for the same date
all have to be safe, and a full sweep makes them so for free (research R5, R7,
FR-027).

Running it twice creates nothing the second time. That comes from the unique
constraint on `notification` and from sending only unstamped rows, not from this
module remembering anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.config import settings
from app.database import engine, utcnow
from app.models.attempt import Attempt
from app.models.module import Module
from app.models.notification import Notification
from app.models.registration import Registration
from app.models.user import User
from app.services import due, notification_service, results_service

_DIGEST = Path(__file__).resolve().parents[1] / "templates" / "emails" / "digest.txt"


@dataclass
class RunSummary:
    """What one run did. Printed to the log, and asserted on in tests."""

    considered: int = 0
    created: int = 0
    messages_sent: int = 0
    messages_failed: int = 0

    def __str__(self) -> str:
        return (
            f"considered {self.considered}, created {self.created}, "
            f"sent {self.messages_sent}, failed {self.messages_failed}"
        )


def run_now() -> RunSummary | None:
    """What the scheduler calls: its own session, and today's date.

    Building the session lives here rather than in `main.py`, where the name
    `Session` already belongs to the session *table* and `Session(engine)`
    quietly constructs a row instead of a database session. That was a real
    failure, and no test caught it because every test calls `run_daily` with a
    session already in hand. It cannot come back now: `main.py` names no session
    type at all.

    A failure is logged and swallowed. The scheduler must survive it, and the
    job is a full sweep, so a run that never completed costs nobody anything
    (FR-027).
    """
    try:
        with DbSession(engine) as db:
            return run_daily(db, utcnow().date())
    except Exception as exc:  # noqa: BLE001 - a failed run must not stop the scheduler
        print(f"[daily job] run failed: {exc}", flush=True)
        return None


def run_daily(db: DbSession, today: date) -> RunSummary:
    """Find who is due, record it, and tell them once.

    The date is a parameter rather than read from the clock, so a test can run
    it for any day, and so a run repeated for the same date is genuinely the
    same run rather than one that has quietly moved on.
    """
    summary = RunSummary()

    _record_who_is_due(db, today, summary)
    _send_what_has_not_been_sent(db, summary)

    print(f"[daily job] {today}: {summary}", flush=True)
    return summary


# ------------------------------------------------------------- steps 1 to 3


def _record_who_is_due(db: DbSession, today: date, summary: RunSummary) -> None:
    """Compute every due date and insert what has become due.

    Insertions refused by the unique constraint are skipped, and that refusal is
    the whole of FR-024: on a second run for the same date every insert is
    refused and nothing happens.
    """
    horizon = today + timedelta(days=settings.due_soon_lead_days)

    registrations = db.exec(
        select(Registration).where(Registration.role_in_module == "trainee")
    ).all()

    by_module: dict[int, list[Registration]] = {}
    for row in registrations:
        by_module.setdefault(row.module_id, []).append(row)

    for module_id, people in by_module.items():
        module = db.get(Module, module_id)
        if module is None or module.deleted_at is not None:
            continue

        # State follows the module's currently published test, so a due date
        # does too. Attempts at anything it replaced decide nothing, which is
        # what makes a replacement test make the whole cohort due again with no
        # grace period and no suppression (FR-020).
        test = results_service.current_test(db, module_id)
        if test is None:
            continue
        if not test.retake_interval_days and not test.completion_deadline_days:
            continue  # nobody is ever chased about this test (FR-039)

        attempts_by_user: dict[int, list[Attempt]] = {}
        for row in db.exec(select(Attempt).where(Attempt.test_id == test.id)).all():
            attempts_by_user.setdefault(row.user_id, []).append(row)

        for registration in people:
            summary.considered += 1
            due_date = due.due_date_for(
                test, registration, attempts_by_user.get(registration.user_id, [])
            )
            if due_date is None:
                continue

            if due_date < today:
                kind = "overdue"
                title = f"Overdue: {module.title}"
                body = (
                    f"Your training on {module.title} was due on "
                    f"{due_date.isoformat()} and has not been completed."
                )
            elif due_date <= horizon:
                kind = "due_soon"
                title = f"Due soon: {module.title}"
                body = (
                    f"Your training on {module.title} is due on "
                    f"{due_date.isoformat()}."
                )
            else:
                continue  # not yet worth saying anything about

            created = notification_service.create(
                db,
                user_id=registration.user_id,
                module_id=module_id,
                kind=kind,
                title=title,
                body=body,
                due_date=due_date,
            )
            if created is not None:
                summary.created += 1


# ------------------------------------------------------------- steps 4 to 6


def _send_what_has_not_been_sent(db: DbSession, summary: RunSummary) -> None:
    """One message per person, covering every unsent row they have.

    Deliberately not limited to rows created by this run. A send that failed
    last time left its rows unstamped, and this is where they are picked up
    again, without a second record being created (FR-025).
    """
    pending = db.exec(
        select(Notification)
        .where(
            Notification.emailed_at.is_(None),
            Notification.kind.in_(("due_soon", "overdue")),
        )
        .order_by(Notification.user_id, Notification.id)
    ).all()
    if not pending:
        return

    by_user: dict[int, list[Notification]] = {}
    for row in pending:
        by_user.setdefault(row.user_id, []).append(row)

    titles = {
        module.id: module.title
        for module in db.exec(
            select(Module).where(Module.id.in_({row.module_id for row in pending}))
        ).all()
    }

    for user_id, rows in by_user.items():
        person = db.get(User, user_id)
        if person is None or not person.is_active:
            continue

        overdue = [row for row in rows if row.kind == "overdue"]
        subject = (
            "Training overdue" if overdue else "Training due soon"
        )
        lead = (
            "Some of your training is overdue."
            if overdue
            else "Some of your training falls due shortly."
        )
        lines = "\n".join(
            f"  {titles.get(row.module_id, 'A module')}: "
            f"{'overdue since' if row.kind == 'overdue' else 'due'} "
            f"{row.due_date.isoformat() if row.due_date else 'soon'}"
            for row in rows
        )

        body = _DIGEST.read_text(encoding="utf-8").format(
            full_name=person.full_name, lead=lead, lines=lines
        )

        if notification_service.deliver(db, person.email, subject, body, rows):
            summary.messages_sent += 1
        else:
            summary.messages_failed += 1
