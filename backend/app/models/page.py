"""One section of a module's material.

`body` holds HTML that has **already been sanitised**. Nothing unsafe can be in
this column, because the sanitiser runs before the write, which is why templates
render it directly (FR-016).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.mysql import MEDIUMTEXT
from sqlmodel import Field, SQLModel

from app.database import utcnow


class Page(SQLModel, table=True):
    __tablename__ = "page"
    __table_args__ = (UniqueConstraint("module_id", "position", name="uq_page_module_position"),)

    id: int | None = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    title: str = Field(max_length=255, nullable=False)

    # MEDIUMTEXT, not TEXT: MySQL cuts a TEXT column at 64KB silently, and
    # formatted HTML reaches that sooner than prose does (research R6, FR-017).
    body: str = Field(sa_column=Column(MEDIUMTEXT, nullable=False))

    # Unique within the module. New pages go last; reordering rewrites the
    # affected rows in one transaction (research R5).
    position: int = Field(nullable=False)

    # A page starts as a draft, and each one is published on its own, so an
    # instructor can work on section four while the first three are live.
    is_published: bool = Field(default=False, nullable=False)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=utcnow, nullable=False)
