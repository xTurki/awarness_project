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

    # The cover: either a pattern and a colour as "shield.teal", or an uploaded
    # picture as "upload.9f2c....png". Nullable, and a null draws one derived
    # from the id, so this column was added to a live database without
    # backfilling a row (app/art.py).
    #
    # 64 rather than 32: a stored image name is a 32-character uuid plus its
    # extension, which does not fit the width a pattern name needed.
    # `create_all()` never alters an existing column, so widening a database
    # that already has this table is one statement by hand (see README).
    art: str | None = Field(default=None, max_length=64, nullable=True)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    # NULL means live. Set to soft-delete, cleared to restore (FR-010).
    # A soft-deleted module disappears from every list for everyone, while its
    # pages, images, and registrations stay exactly where they are.
    deleted_at: datetime | None = Field(default=None, nullable=True)
