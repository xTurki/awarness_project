"""The read model for the notification list.

The new table never reaches a template (done-gate 5). This phase adds no input
model of its own: its only input is the two schedule fields, which are validated
through Phase 2's `TestWrite`.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class NotificationRead(BaseModel):
    """One entry in a person's list."""

    id: int
    module_id: int
    module_title: str
    kind: str
    due_date: date | None
    title: str
    body: str | None
    created_at: datetime
    is_seen: bool
    #: Straight to the module it concerns (FR-032).
    link: str
