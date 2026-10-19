"""Test attempts and their answers.

`ends_at` and `question_order` are set once when the attempt starts and never
recalculated, so an attempt can be resumed and later test edits don't affect it.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import JSON, Column, Field, Index, SQLModel, UniqueConstraint

from app.database import utcnow


class Attempt(SQLModel, table=True):
    __tablename__ = "attempt"
    # Used by attempt-count and latest-attempt queries.
    __table_args__ = (Index("ix_attempt_test_user", "test_id", "user_id"),)

    id: int | None = Field(default=None, primary_key=True)
    test_id: int = Field(foreign_key="test.id", index=True, nullable=False)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)

    # Calculated from the user's previous attempts.
    attempt_number: int = Field(nullable=False)

    started_at: datetime = Field(default_factory=utcnow, nullable=False)

    # min(started_at + time_limit, closes_at), fixed at creation.
    ends_at: datetime = Field(nullable=False)

    submitted_at: datetime | None = Field(default=None, nullable=True)
    is_submitted: bool = Field(default=False, nullable=False)

    # Ordered question ids, fixed when the attempt starts.
    question_order: list[int] = Field(sa_column=Column(JSON, nullable=False))

    points_earned: int | None = Field(default=None, nullable=True)
    points_possible: int | None = Field(default=None, nullable=True)

    # Can be overridden by an instructor; `passed` follows it.
    score_percent: int | None = Field(default=None, nullable=True)
    passed: bool | None = Field(default=None, nullable=True)
    score_overridden: bool = Field(default=False, nullable=False)


class AttemptAnswer(SQLModel, table=True):
    __tablename__ = "attempt_answer"
    # One answer row per question per attempt (saving updates it).
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_answer_attempt_question"),
    )

    id: int | None = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempt.id", index=True, nullable=False)
    question_id: int = Field(foreign_key="question.id", nullable=False)

    # A list because a question can have more than one correct answer.
    selected_option_ids: list[int] = Field(sa_column=Column(JSON, nullable=False))

    is_correct: bool | None = Field(default=None, nullable=True)
    points_awarded: int | None = Field(default=None, nullable=True)

