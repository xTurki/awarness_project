"""Tests and their questions.

A test can't be edited once it has attempts (checked by looking for attempt rows).
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Column, Field, SQLModel, Text

from app.database import utcnow


class Test(SQLModel, table=True):
    __tablename__ = "test"

    # Stop pytest from collecting this class.
    __test__ = False

    id: int | None = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    title: str = Field(max_length=255, nullable=False)
    instructions: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    is_published: bool = Field(default=False, nullable=False)

    # When attempts can be started. Null = no limit.
    opens_at: datetime | None = Field(default=None, nullable=True)
    closes_at: datetime | None = Field(default=None, nullable=True)

    # Null means untimed.
    time_limit_minutes: int | None = Field(default=None, nullable=True)

    # 0 = unlimited. For recurring tests the limit is per cycle.
    allowed_attempts: int = Field(default=1, nullable=False)
    shuffle_questions: bool = Field(default=False, nullable=False)

    # Percentage. Required for recurring tests.
    passing_score: int | None = Field(default=None, nullable=True)

    # Null = one-off test.
    retake_interval_days: int | None = Field(default=None, nullable=True)

    # Days after registration to pass a one-off test. Null = no deadline.
    completion_deadline_days: int | None = Field(default=None, nullable=True)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class TestQuestion(SQLModel, table=True):
    """Questions in a test, in order."""

    __tablename__ = "test_question"

    test_id: int = Field(foreign_key="test.id", primary_key=True)
    question_id: int = Field(foreign_key="question.id", primary_key=True)
    position: int = Field(nullable=False)
