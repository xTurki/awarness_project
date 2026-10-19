"""Creating, sending, listing and marking notifications.

The notification row is saved before the email is sent, so failed emails can be
retried. `create` returns None if the row already exists (unique constraint).
Registration and result emails are sent in a background thread.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.database import engine, utcnow
from app.models.module import Module
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationRead
from app.services import email_service

_EMAILS = Path(__file__).resolve().parents[1] / "templates" / "emails"

_SENDER = ThreadPoolExecutor(max_workers=2, thread_name_prefix="mail")

# Disabled in tests (the worker can't see rows in the test transaction).
SEND_IN_BACKGROUND = True


# --------------------------------------------------- the two immediate events


def notify_registered(db: DbSession, person: User, module: Module) -> None:
    """Notify a user that they were registered on a module."""
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
    deliver_soon(db, person.email, f"Added to {module.title}", body, [row])


def notify_result(db: DbSession, person: User, module: Module, test, attempt) -> None:
    """Notify a user of their test result."""
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
    deliver_soon(db, person.email, f"Your result for {test.title}", body, [row])


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
    """Create a notification, or return None if it already exists.

    Uses a savepoint so a duplicate doesn't roll back the whole transaction.
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
        # Already exists.
        return None

    db.commit()
    db.refresh(row)
    return row


def deliver(db: DbSession, to: str, subject: str, body: str, rows: list[Notification]) -> bool:
    """Send one email and mark all the given rows as emailed.

    On failure the rows stay unmarked and are retried on the next run.
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


def deliver_soon(db: DbSession, to: str, subject: str, body: str, rows: list[Notification]) -> None:
    """Like `deliver`, but sends in a background thread."""
    if not SEND_IN_BACKGROUND:
        deliver(db, to, subject, body, rows)
        return

    ids = [row.id for row in rows]
    _SENDER.submit(_send_and_stamp, to, subject, body, ids)


def _send_and_stamp(to: str, subject: str, body: str, ids: list[int]) -> None:
    try:
        email_service.send_email_now(to, subject, body)
    except email_service.EmailDeliveryFailed as exc:
        print(f"[notification] delivery failed for {to}: {exc}", flush=True)
        return
    _stamp_sent(ids)


def _stamp_sent(ids: list[int]) -> None:
    sent_at = utcnow()
    with DbSession(engine) as db:
        for row_id in ids:
            row = db.get(Notification, row_id)
            if row is not None:
                row.emailed_at = sent_at
                db.add(row)
        db.commit()


# ------------------------------------------------------------------- reading


def list_for(db: DbSession, user: User) -> list[NotificationRead]:
    """The user's notifications, newest first."""
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
    """Number of unread notifications."""
    return len(
        db.exec(
            select(Notification).where(
                Notification.user_id == user.id, Notification.read_at.is_(None)
            )
        ).all()
    )


def mark_seen(db: DbSession, user: User) -> int:
    """Mark all of the user's notifications as read."""
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
