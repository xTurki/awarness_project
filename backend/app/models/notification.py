"""One record that one person was told one thing about one module.

**The record is the notification.** A message is a delivery of it, never a
substitute: the row is written before anything is sent, so a mail outage costs
the delivery and not the notification (FR-021).

The unique constraint below is the whole of this phase's idempotency. Running
the daily job twice tries to insert the same row and is refused by the database,
rather than relying on the job to remember that it already ran (research R5).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Column, Text, UniqueConstraint
from sqlmodel import Field, SQLModel

from app.database import utcnow

#: Two arrive from the daily sweep, two from inside a request.
KINDS = ("registered", "result", "due_soon", "overdue")


class Notification(SQLModel, table=True):
    __tablename__ = "notification"
    # `due_date` belongs in the key so that next cycle's overdue notice is a
    # different row rather than a duplicate of this one. Within a cycle the date
    # does not move, so that row is inserted once and never again (FR-014, FR-022).
    #
    # Two nulls never collide in MySQL, which is why a repeated `registered`
    # event is prevented by there being only one registration rather than here.
    __table_args__ = (
        UniqueConstraint(
            "user_id", "kind", "module_id", "due_date", name="uq_notification_event"
        ),
    )

    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    # Every notification concerns exactly one module, which is what keeps the
    # in-app list granular where messages were combined (FR-017, FR-034).
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    kind: str = Field(max_length=20, nullable=False)

    #: The due date this concerns. Null for `registered` and `result`.
    due_date: date | None = Field(default=None, nullable=True)

    title: str = Field(max_length=255, nullable=False)
    body: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    #: Null means unseen. This drives the shell indicator (FR-030, FR-031).
    read_at: datetime | None = Field(default=None, nullable=True)

    #: Null means no message has gone out. A failed send leaves it null, which
    #: is what makes the next run retry it (FR-023, FR-025).
    emailed_at: datetime | None = Field(default=None, nullable=True)
