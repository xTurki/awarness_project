"""Question bank models. Questions belong to a module and can be reused in tests."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Column, Field, SQLModel, Text

from app.database import utcnow


class Question(SQLModel, table=True):
    __tablename__ = "question"

    id: int | None = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    prompt: str = Field(sa_column=Column(Text, nullable=False))

    # Weight of the question. Scores are shown as percentages.
    points: int = Field(default=1, nullable=False)
    position: int = Field(nullable=False)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)


class AnswerOption(SQLModel, table=True):
    __tablename__ = "answer_option"

    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(
        foreign_key="question.id", index=True, nullable=False, ondelete="CASCADE"
    )

    text: str = Field(max_length=500, nullable=False)

    # One correct option -> radio buttons, several -> checkboxes.
    is_correct: bool = Field(nullable=False)

    position: int = Field(nullable=False)
