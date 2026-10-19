"""A training module. It is either published or not; deletion is a soft delete."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Column, Field, SQLModel, Text

from app.database import utcnow


class Module(SQLModel, table=True):
    __tablename__ = "module"

    id: int | None = Field(default=None, primary_key=True)

    title: str = Field(max_length=255, nullable=False)

    # TEXT instead of the default VARCHAR(255).
    description: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )

    is_published: bool = Field(default=False, nullable=False)

    # Cover: a colour name or "upload.<file>". Null uses a default colour
    # (see app/art.py).
    art: str | None = Field(default=None, max_length=64, nullable=True)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)

    # Soft delete: set to delete, clear to restore. Related data is kept.
    deleted_at: datetime | None = Field(default=None, nullable=True)
