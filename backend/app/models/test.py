"""A test, and the ordered questions that make it up.

**Frozen once attempted.** No column records this: the check is whether any
attempt row exists. A boolean would be a second source of truth able to
disagree with reality (research R6).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from app.database import utcnow


class Test(SQLModel, table=True):
    __tablename__ = "test"

    # Named Test, which pytest would otherwise try to collect as a test class.
    __test__ = False

    id: int | None = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    title: str = Field(max_length=255, nullable=False)
    instructions: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    is_published: bool = Field(default=False, nullable=False)

    # Null means open from the start, and null means never closes. The window
    # governs when an attempt may *start*.
    opens_at: datetime | None = Field(default=None, nullable=True)
    closes_at: datetime | None = Field(default=None, nullable=True)

    # Null means untimed.
    time_limit_minutes: int | None = Field(default=None, nullable=True)

    allowed_attempts: int = Field(default=1, nullable=False)
    shuffle_questions: bool = Field(default=False, nullable=False)

    # A percentage. Required before a retake interval can be set, because a
    # cycle that restarts on passing must know what passing means (Phase 4).
    passing_score: int | None = Field(default=None, nullable=True)

    # How often it must be retaken. Null means one-off, and nobody becomes due
    # for it a second time (FR-002).
    retake_interval_days: int | None = Field(default=None, nullable=True)

    # How long after their own registration a one-off test should be passed.
    # Null means nobody is chased. If both are set, the interval wins, and the
    # form offers one or the other.
    completion_deadline_days: int | None = Field(default=None, nullable=True)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class TestQuestion(SQLModel, table=True):
    """Which questions make up a test, and in what order the instructor chose.

    A join table because a bank question may appear in more than one test.
    """

    __tablename__ = "test_question"

    test_id: int = Field(foreign_key="test.id", primary_key=True)
    question_id: int = Field(foreign_key="question.id", primary_key=True)
    position: int = Field(nullable=False)
