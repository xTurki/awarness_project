"""A subject the organisation wants covered.

Two states, not three. There is no `archived`: a module is published or it is
not, and retiring one means unpublishing it. Deletion is separate, reversible,
and marked here rather than performed.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel

from app.database import utcnow


class Module(SQLModel, table=True):
    __tablename__ = "module"

    id: int | None = Field(default=None, primary_key=True)

    # No code and no reference number: the title identifies it (FR-001).
    title: str = Field(max_length=255, nullable=False)

    # Text, not VARCHAR(255): SQLModel maps a bare str to 255 characters, which
    # is fine for a name and wrong for a description.
    description: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )

    is_published: bool = Field(default=False, nullable=False)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    # NULL means live. Set to soft-delete, cleared to restore (FR-010).
    # A soft-deleted module disappears from every list for everyone, while its
    # pages, images, and registrations stay exactly where they are.
    deleted_at: datetime | None = Field(default=None, nullable=True)
