"""Non-table models at every boundary for the assessment phase.

`QuestionRead` deliberately carries no `is_correct`. A trainee taking a test
receives options through it, and the answer must not travel with them.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator


# ------------------------------------------------------------------ read models


class OptionRead(BaseModel):
    """What a trainee sees while taking a test. No `is_correct` anywhere."""

    id: int
    text: str
    position: int


class OptionReview(BaseModel):
    """What a trainee sees afterwards, and what an instructor always sees."""

    id: int
    text: str
    position: int
    is_correct: bool


class QuestionRead(BaseModel):
    id: int
    prompt: str
    points: int
    position: int
    options: list[OptionRead]
    # Counted from the options, never chosen by the instructor: one correct
    # option renders radio buttons, several renders checkboxes (FR-005).
    multiple: bool


class QuestionReview(BaseModel):
    id: int
    prompt: str
    points: int
    position: int
    options: list[OptionReview]
    multiple: bool


class TestRead(BaseModel):
    __test__ = False

    id: int
    module_id: int
    title: str
    instructions: str | None
    is_published: bool
    opens_at: datetime | None
    closes_at: datetime | None
    time_limit_minutes: int | None
    allowed_attempts: int
    shuffle_questions: bool
    passing_score: int | None
    # Phase 4. Null on both means this test never falls due for anyone.
    retake_interval_days: int | None = None
    completion_deadline_days: int | None = None
    question_count: int = 0
    is_frozen: bool = False


class AttemptRead(BaseModel):
    id: int
    test_id: int
    user_id: int
    attempt_number: int
    started_at: datetime
    ends_at: datetime
    submitted_at: datetime | None
    is_submitted: bool
    score_percent: int | None
    passed: bool | None
    score_overridden: bool


class AttemptAnswerRead(BaseModel):
    question_id: int
    selected_option_ids: list[int]
    is_correct: bool | None
    points_awarded: int | None


class CohortRow(BaseModel):
    """One person's attempts on a test, for the instructor's list."""

    user_id: int
    full_name: str
    email: str
    attempts: list[AttemptRead]


# ----------------------------------------------------------------- input models


class QuestionWrite(BaseModel):
    prompt: str
    points: int = 1
    options: list[str]
    correct: list[int]  # indexes into `options`

    @field_validator("prompt")
    @classmethod
    def _prompt_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A question needs a prompt.")
        return value

    @field_validator("points")
    @classmethod
    def _points_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("A question must be worth at least one point.")
        return value

    @field_validator("options")
    @classmethod
    def _at_least_two_options(cls, value: list[str]) -> list[str]:
        filled = [option for option in value if option.strip()]
        if len(filled) < 2:
            raise ValueError("A question needs at least two answer options.")
        return filled

    @field_validator("correct")
    @classmethod
    def _at_least_one_correct(cls, value: list[int]) -> list[int]:
        if not value:
            raise ValueError("Mark at least one option as correct.")
        return value


class TestWrite(BaseModel):
    # pytest collects classes beginning with Test unless told otherwise.
    __test__ = False

    title: str
    instructions: str | None = None
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    time_limit_minutes: int | None = None
    allowed_attempts: int = 1
    shuffle_questions: bool = False
    passing_score: int | None = None
    # Phase 4's only input. Both optional, and the form offers one or the other:
    # if both arrive, the interval wins. The rules that need a pass mark or the
    # warning period to compare against live in `test_service`, because they are
    # cross-field and one of them reads a setting.
    retake_interval_days: int | None = None
    completion_deadline_days: int | None = None
    question_ids: list[int] = []

    @field_validator("retake_interval_days", "completion_deadline_days")
    @classmethod
    def _a_period_is_at_least_a_day(cls, value: int | None) -> int | None:
        if value is not None and value < 1:
            raise ValueError("A period is counted in whole days, so it is at least one.")
        return value

    @field_validator("title")
    @classmethod
    def _title_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A test needs a title.")
        return value

    @field_validator("allowed_attempts")
    @classmethod
    def _attempts_positive(cls, value: int) -> int:
        if value < 1:
            raise ValueError("A test must allow at least one attempt.")
        return value

    @field_validator("passing_score")
    @classmethod
    def _mark_is_a_percentage(cls, value: int | None) -> int | None:
        if value is not None and not 0 <= value <= 100:
            raise ValueError("A pass mark is a percentage between 0 and 100.")
        return value


class AnswerSubmit(BaseModel):
    question_id: int
    option_ids: list[int] = []


class ScoreOverride(BaseModel):
    score_percent: int

    @field_validator("score_percent")
    @classmethod
    def _is_a_percentage(cls, value: int) -> int:
        if not 0 <= value <= 100:
            raise ValueError("A score is a percentage between 0 and 100.")
        return value
