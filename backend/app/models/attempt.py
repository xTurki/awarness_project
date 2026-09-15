"""One person's sitting of one test, and the answers in it.

`ends_at` and `question_order` are written once when the attempt begins and are
never recomputed. They are what make an interrupted attempt resumable and an
instructor's later edit harmless to an attempt already running. Nothing in this
codebase should recalculate either.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Index, UniqueConstraint
from sqlalchemy.dialects.mysql import JSON
from sqlmodel import Field, SQLModel

from app.database import utcnow


class Attempt(SQLModel, table=True):
    __tablename__ = "attempt"
    # Every attempt-count and most-recent-attempt query uses this.
    __table_args__ = (Index("ix_attempt_test_user", "test_id", "user_id"),)

    id: int | None = Field(default=None, primary_key=True)
    test_id: int = Field(foreign_key="test.id", index=True, nullable=False)
    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)

    # Derived by counting this person's existing attempts. Never supplied by
    # the request.
    attempt_number: int = Field(nullable=False)

    started_at: datetime = Field(default_factory=utcnow, nullable=False)

    # min(started_at + time_limit, closes_at), fixed at creation.
    ends_at: datetime = Field(nullable=False)

    submitted_at: datetime | None = Field(default=None, nullable=True)
    is_submitted: bool = Field(default=False, nullable=False)

    # The ordered question ids, fixed at creation. Read whole, never searched
    # into, which is the one use the project permits a JSON column.
    question_order: list[int] = Field(sa_column=Column(JSON, nullable=False))

    points_earned: int | None = Field(default=None, nullable=True)
    points_possible: int | None = Field(default=None, nullable=True)

    # Replaced by an instructor's override; `passed` follows whatever it holds.
    score_percent: int | None = Field(default=None, nullable=True)
    passed: bool | None = Field(default=None, nullable=True)
    score_overridden: bool = Field(default=False, nullable=False)


class AttemptAnswer(SQLModel, table=True):
    __tablename__ = "attempt_answer"
    # One row per question per attempt, however many times they change their
    # mind. This is what makes each save an upsert.
    __table_args__ = (
        UniqueConstraint("attempt_id", "question_id", name="uq_answer_attempt_question"),
    )

    id: int | None = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="attempt.id", index=True, nullable=False)
    question_id: int = Field(foreign_key="question.id", nullable=False)

    # A list, because a question may have several correct answers.
    selected_option_ids: list[int] = Field(sa_column=Column(JSON, nullable=False))

    is_correct: bool | None = Field(default=None, nullable=True)
    points_awarded: int | None = Field(default=None, nullable=True)

