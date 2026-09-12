"""A question in a module's bank, and the options it offers.

The bank belongs to the **module**, not to a test. A question may be used in
more than one test, and a test is an ordered selection from the bank rather
than everything in it.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from app.database import utcnow


class Question(SQLModel, table=True):
    __tablename__ = "question"

    id: int | None = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    # Text, not VARCHAR(255): a prompt is prose, not a name.
    prompt: str = Field(sa_column=Column(Text, nullable=False))

    # Points exist so an instructor can weight a hard question, not so trainees
    # are shown raw totals: a score is a percentage of what was available.
    points: int = Field(default=1, nullable=False)
    position: int = Field(nullable=False)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    # There is no `type` column. Multiple choice is the only kind, and a
    # true/false question is a multiple-choice question with two options.


class AnswerOption(SQLModel, table=True):
    __tablename__ = "answer_option"

    id: int | None = Field(default=None, primary_key=True)
    question_id: int = Field(
        foreign_key="question.id", index=True, nullable=False, ondelete="CASCADE"
    )

    text: str = Field(max_length=500, nullable=False)

    # How many of these are true decides how the question is presented: one
    # means radio buttons, several means checkboxes. The instructor never picks
    # a mode, so a question cannot be configured as single-answer while holding
    # two correct options.
    is_correct: bool = Field(nullable=False)

    position: int = Field(nullable=False)
