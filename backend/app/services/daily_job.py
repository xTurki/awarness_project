"""Daily job: create due-soon/overdue notifications and send unsent emails.

It checks everyone each time (no "last run" state), so it is safe to run late,
twice, or manually. Duplicates are prevented by the unique constraint on
`notification`.
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
    """Counts from one run (logged and used in tests)."""

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
    """Entry point for the scheduler: runs the job for today.

    Errors are logged and not re-raised so the scheduler keeps running.
    """
    try:
        with DbSession(engine) as db:
            return run_daily(db, utcnow().date())
    except Exception as exc:  # noqa: BLE001
        print(f"[daily job] run failed: {exc}", flush=True)
        return None


def run_daily(db: DbSession, today: date) -> RunSummary:
    """Run the job for the given date (a parameter so tests can pick the day)."""
    summary = RunSummary()

    _record_who_is_due(db, today, summary)
    _send_what_has_not_been_sent(db, summary)

    print(f"[daily job] {today}: {summary}", flush=True)
    return summary


# ------------------------------------------------------------- steps 1 to 3


def _record_who_is_due(db: DbSession, today: date, summary: RunSummary) -> None:
    """Create due-soon and overdue notifications. Existing ones are skipped."""
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

        # Only attempts at the current test count.
        test = results_service.current_test(db, module_id)
        if test is None:
            continue
        if not test.retake_interval_days and not test.completion_deadline_days:
            continue  # test has no schedule

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
                continue  # not due soon yet

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
    """Send one email per user covering all their unsent notifications.

    Includes rows from earlier failed sends, so they are retried.
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
