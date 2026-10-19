"""A page of module content. `body` is HTML that was sanitised before saving."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Column, Field, SQLModel, Text, UniqueConstraint

from app.database import utcnow


class Page(SQLModel, table=True):
    __tablename__ = "page"
    __table_args__ = (UniqueConstraint("module_id", "position", name="uq_page_module_position"),)

    id: int | None = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    title: str = Field(max_length=255, nullable=False)

    # MEDIUMTEXT (TEXT is limited to 64KB).
    body: str = Field(sa_column=Column(Text(length=4_194_303), nullable=False))

    # Unique within the module.
    position: int = Field(nullable=False)

    # Each page is published separately.
    is_published: bool = Field(default=False, nullable=False)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)
