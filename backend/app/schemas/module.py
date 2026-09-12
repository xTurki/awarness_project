"""Non-table models at every boundary for this phase.

Read models keep the four new `table=True` classes out of templates and
responses (done-gate 5). Input models are where every form post is validated,
because SQLModel does not validate table classes.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

from app import art
from app.models.registration import ROLES_IN_MODULE


# ------------------------------------------------------------------ read models


class ModuleRead(BaseModel):
    id: int
    title: str
    description: str | None
    is_published: bool
    #: Resolved, never raw: a module with nothing chosen still arrives with a
    #: pattern and a colour, so no template has to decide what to do about null.
    art_pattern: str = art.PATTERNS[0]
    art_colour: str = art.COLOURS[0]

    @classmethod
    def of(cls, row) -> "ModuleRead":
        pattern, colour = art.parse(getattr(row, "art", None), row.id)
        return cls(
            id=row.id,
            title=row.title,
            description=row.description,
            is_published=row.is_published,
            art_pattern=pattern,
            art_colour=colour,
        )


class PageRead(BaseModel):
    id: int
    module_id: int
    title: str
    body: str
    position: int
    is_published: bool

    @classmethod
    def of(cls, row) -> "PageRead":
        return cls(
            id=row.id,
            module_id=row.module_id,
            title=row.title,
            body=row.body,
            position=row.position,
            is_published=row.is_published,
        )


class PageSummary(BaseModel):
    """Everything the navigation needs and nothing else: bodies are large."""

    id: int
    title: str
    position: int
    is_published: bool

    @classmethod
    def of(cls, row) -> "PageSummary":
        return cls(
            id=row.id, title=row.title, position=row.position, is_published=row.is_published
        )


class RegistrationRead(BaseModel):
    id: int
    user_id: int
    module_id: int
    role_in_module: str
    registered_at: datetime
    full_name: str
    email: str


class ImageRead(BaseModel):
    id: int
    url: str
    original_name: str


# ----------------------------------------------------------------- input models


class ModuleWrite(BaseModel):
    title: str
    description: str | None = None
    art_pattern: str = art.PATTERNS[0]
    art_colour: str = art.COLOURS[0]

    @field_validator("title")
    @classmethod
    def _title_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A module needs a title.")
        return value

    @field_validator("art_pattern")
    @classmethod
    def _known_pattern(cls, value: str) -> str:
        if value not in art.PATTERNS:
            raise ValueError(f"Choose one of: {', '.join(art.PATTERNS)}.")
        return value

    @field_validator("art_colour")
    @classmethod
    def _known_colour(cls, value: str) -> str:
        if value not in art.COLOURS:
            raise ValueError(f"Choose one of: {', '.join(art.COLOURS)}.")
        return value


class PageWrite(BaseModel):
    title: str
    body: str = ""

    @field_validator("title")
    @classmethod
    def _title_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A page needs a title.")
        return value


class PageReorder(BaseModel):
    """The page ids in their new order."""

    order: list[int]


class RosterAdd(BaseModel):
    """Several people registered in one action (FR-025)."""

    user_ids: list[int]
    role_in_module: str = "trainee"

    @field_validator("role_in_module")
    @classmethod
    def _known_role(cls, value: str) -> str:
        if value not in ROLES_IN_MODULE:
            raise ValueError(f"role_in_module must be one of {', '.join(ROLES_IN_MODULE)}")
        return value
