"""View models for the results pages (read-only)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ModuleResultRow(BaseModel):
    """A row on the trainee dashboard."""

    module_id: int
    title: str
    state: str
    score_percent: int | None
    # The attempt in progress, otherwise the module history.
    link: str
    description: str | None = None
    art_colour: str = ""
    art_image: str | None = None


class AttemptRow(BaseModel):
    """One attempt in a user's module history."""

    attempt_id: int
    test_title: str
    attempt_number: int
    started_at: datetime
    submitted_at: datetime | None
    score_percent: int | None
    passed: bool | None
    is_submitted: bool
    # The attempt if running, otherwise its review.
    link: str
    # True if the attempt belongs to an older test.
    at_replaced_test: bool = False


class CurrentTestRow(BaseModel):
    """The module's current test, for templates."""

    id: int
    title: str


class CohortRow(BaseModel):
    """A user's row in the instructor's module view."""

    user_id: int
    full_name: str
    email: str
    state: str
    score_percent: int | None
    link: str
