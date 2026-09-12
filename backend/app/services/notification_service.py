"""Creating notifications, listing them, and marking them seen.

**The record is written before anything is sent.** A message is a delivery of a
notification, never a substitute for one, so a mail outage costs the delivery
and leaves the notification in place to be retried and, meanwhile, read in the
application (FR-021, FR-025).

`create` returns None where the record already exists. That refusal comes from
the database, not from a check here: the unique constraint on
(user_id, kind, module_id, due_date) is what makes the daily job safe to run
twice, and no amount of bookkeeping in Python would be as reliable (research R5).
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.database import utcnow
from app.models.module import Module
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationRead
from app.services import email_service

_EMAILS = Path(__file__).resolve().parents[1] / "templates" / "emails"


# --------------------------------------------------- the two immediate events


def notify_registered(db: DbSession, person: User, module: Module) -> None:
    """Told at the moment it happens, individually.

    Both of the events in this section already happen inside a request, so the
    daily job has nothing to add: a registration notice sent tomorrow morning is
    not a registration notice (FR-015, FR-018, research R4).
    """
    row = create(
        db,
        user_id=person.id,
        module_id=module.id,
        kind="registered",
        title=f"You have been added to {module.title}",
        body=f"You are now registered on {module.title}.",
    )
    if row is None:
        return

    body = (_EMAILS / "registered.txt").read_text(encoding="utf-8").format(
        full_name=person.full_name, module_title=module.title
    )
    deliver(db, person.email, f"Added to {module.title}", body, [row])


def notify_result(db: DbSession, person: User, module: Module, test, attempt) -> None:
    """Told when their result becomes available, which is when it is scored."""
    outcome = "Passed" if attempt.passed else "Not passed"
    score = f"{attempt.score_percent}%" if attempt.score_percent is not None else "not scored"

    row = create(
        db,
        user_id=person.id,
        module_id=module.id,
        kind="result",
        title=f"{outcome}: {test.title}",
        body=f"You scored {score} on {test.title}.",
    )
    if row is None:
        return

    body = (_EMAILS / "result.txt").read_text(encoding="utf-8").format(
        full_name=person.full_name,
        module_title=module.title,
        test_title=test.title,
        score=score,
        outcome=outcome,
    )
    deliver(db, person.email, f"Your result for {test.title}", body, [row])


# ------------------------------------------------------------------ creating


def create(
    db: DbSession,
    user_id: int,
    module_id: int,
    kind: str,
    title: str,
    body: str | None = None,
    due_date: date | None = None,
) -> Notification | None:
    """One record per person per module per event, or None if it already exists.

    The insert runs inside a savepoint so that a refused duplicate rolls back
    only itself. Without that, one collision would poison the transaction and
    take every other notification in the run down with it.
    """
    row = Notification(
        user_id=user_id,
        module_id=module_id,
        kind=kind,
        title=title,
        body=body,
        due_date=due_date,
    )

    try:
        with db.begin_nested():
            db.add(row)
            db.flush()
    except IntegrityError:
        # Somebody has already been told this exact thing. That is the whole of
        # FR-022, and it is what a second run of the job hits. Rolling the
        # savepoint back has already discarded the pending row, so there is
        # nothing here to clean up.
        return None

    db.commit()
    db.refresh(row)
    return row


def deliver(db: DbSession, to: str, subject: str, body: str, rows: list[Notification]) -> bool:
    """Send one message and stamp every record it covered.

    One message may cover several records: somebody overdue on three modules
    gets one email and three stamped rows, and still sees three entries in their
    list (FR-019, FR-023, FR-034).

    A failure leaves them all unstamped, which is the entire implementation of
    FR-025: the next run finds them again and tries once more, without creating
    a second record.
    """
    try:
        email_service.send_email_now(to, subject, body)
    except email_service.EmailDeliveryFailed as exc:
        print(f"[notification] delivery failed for {to}: {exc}", flush=True)
        return False

    sent_at = utcnow()
    for row in rows:
        row.emailed_at = sent_at
        db.add(row)
    db.commit()
    return True


# ------------------------------------------------------------------- reading


def list_for(db: DbSession, user: User) -> list[NotificationRead]:
    """The caller's own, newest first (FR-029).

    Scoped to `user.id` here rather than by an argument a route could supply,
    so there is nothing for a route to get wrong (FR-033).
    """
    rows = db.exec(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
    ).all()
    if not rows:
        return []

    titles = {
        module.id: module.title
        for module in db.exec(
            select(Module).where(Module.id.in_({row.module_id for row in rows}))
        ).all()
    }

    return [
        NotificationRead(
            id=row.id,
            module_id=row.module_id,
            module_title=titles.get(row.module_id, "A module you have left"),
            kind=row.kind,
            due_date=row.due_date,
            title=row.title,
            body=row.body,
            created_at=row.created_at,
            is_seen=row.read_at is not None,
            link=f"/modules/{row.module_id}",
        )
        for row in rows
    ]


def unread_count(db: DbSession, user: User) -> int:
    """What the shell indicator shows (FR-030)."""
    return len(
        db.exec(
            select(Notification).where(
                Notification.user_id == user.id, Notification.read_at.is_(None)
            )
        ).all()
    )


def mark_seen(db: DbSession, user: User) -> int:
    """Opening the list marks everything in it seen (FR-031).

    On open rather than per entry: there is no dismiss action anywhere, and an
    indicator that never clears is worse than one that clears too eagerly
    (research R8).
    """
    rows = db.exec(
        select(Notification).where(
            Notification.user_id == user.id, Notification.read_at.is_(None)
        )
    ).all()

    seen_at: datetime = utcnow()
    for row in rows:
        row.read_at = seen_at
        db.add(row)
    db.commit()
    return len(rows)
