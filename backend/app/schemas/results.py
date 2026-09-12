"""View objects for the results pages.

**No input model appears here: this phase exposes no `POST` at all.** Nothing on
these pages enters, adjusts, or weights a score; correcting one stays where
Phase 2 put it, on the attempt (FR-025, FR-026).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ModuleResultRow(BaseModel):
    """One line on a trainee's dashboard."""

    module_id: int
    title: str
    state: str
    score_percent: int | None
    #: Where following this row goes: the attempt if one is in progress,
    #: otherwise the module's history.
    link: str


class AttemptRow(BaseModel):
    """One line of somebody's history for a module."""

    attempt_id: int
    test_title: str
    attempt_number: int
    started_at: datetime
    submitted_at: datetime | None
    score_percent: int | None
    passed: bool | None
    is_submitted: bool
    #: Into the attempt while it runs, to the review once it is finished.
    link: str
    #: True where the attempt was at a test the module has since replaced.
    at_replaced_test: bool = False


class CurrentTestRow(BaseModel):
    """The module's currently published test, for a link and a name.

    `current_test` returns the table row, because the services around it need a
    row: `due.py` reads its schedule and `state.py` reads whether it is
    published. Templates get this instead, so no `table=True` instance reaches
    one (done-gate 5).
    """

    id: int
    title: str


class CohortRow(BaseModel):
    """One person on the instructor's view of a module."""

    user_id: int
    full_name: str
    email: str
    state: str
    score_percent: int | None
    link: str
