"""Read and input models for modules, pages and registrations.

Read models are passed to templates instead of table rows. Input models
validate form data.
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
    # Picked colour, or the default one for the module id.
    art_colour: str = art.COLOURS[0]
    # Uploaded cover file name, or None.
    art_image: str | None = None

    @classmethod
    def of(cls, row) -> "ModuleRead":
        return cls(
            id=row.id,
            title=row.title,
            description=row.description,
            is_published=row.is_published,
            art_colour=art.parse_colour(getattr(row, "art", None), row.id),
            art_image=art.uploaded(getattr(row, "art", None)),
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
    """Page info for navigation (without the body)."""

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
    # None = keep the current cover (so saving doesn't remove an uploaded image).
    art_colour: str | None = None

    @field_validator("title")
    @classmethod
    def _title_present(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A module needs a title.")
        return value

    @field_validator("art_colour")
    @classmethod
    def _known_colour(cls, value: str | None) -> str | None:
        if value is not None and value not in art.COLOURS:
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


class RosterAdd(BaseModel):
    """Register several users at once."""

    user_ids: list[int]
    role_in_module: str = "trainee"

    @field_validator("role_in_module")
    @classmethod
    def _known_role(cls, value: str) -> str:
        if value not in ROLES_IN_MODULE:
            raise ValueError(f"role_in_module must be one of {', '.join(ROLES_IN_MODULE)}")
        return value
