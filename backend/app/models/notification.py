"""In-app notifications.

The row is saved before any email is sent, so an email failure doesn't lose the
notification. The unique constraint stops the daily job creating duplicates.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlmodel import Column, Field, SQLModel, Text, UniqueConstraint

from app.database import utcnow

KINDS = ("registered", "result", "due_soon", "overdue")


class Notification(SQLModel, table=True):
    __tablename__ = "notification"
    # `due_date` is part of the key so each retake cycle gets its own notice.
    # Note: NULLs don't conflict in MySQL unique keys.
    __table_args__ = (
        UniqueConstraint(
            "user_id", "kind", "module_id", "due_date", name="uq_notification_event"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    kind: str = Field(max_length=20, nullable=False)

    # Null for `registered` and `result`.
    due_date: date | None = Field(default=None, nullable=True)

    title: str = Field(max_length=255, nullable=False)
    body: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    # Null = unread.
    read_at: datetime | None = Field(default=None, nullable=True)

    # Null = not emailed yet (failed sends are retried on the next run).
    emailed_at: datetime | None = Field(default=None, nullable=True)
