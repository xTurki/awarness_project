"""Read model for the notification list."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    """One notification in a user's list."""

    id: int
    module_id: int
    module_title: str
    kind: str
    due_date: date | None
    title: str
    body: str | None
    created_at: datetime
    is_seen: bool
    # Link to the related module.
    link: str
