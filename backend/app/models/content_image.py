"""A picture an instructor uploaded.

The file itself lives on a volume under `stored_name`; this row is what the
platform knows about it. `original_name` is kept for display and is **never**
used to build a path, which is what stops a filename deciding where a file lands.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.database import utcnow


class ContentImage(SQLModel, table=True):
    __tablename__ = "content_image"

    id: int | None = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    # uuid4().hex plus the normalised extension. Generated, never derived from
    # what arrived (research R3).
    stored_name: str = Field(max_length=64, nullable=False)

    # For display only.
    original_name: str = Field(max_length=255, nullable=False)

    # Recorded as declared, not trusted.
    content_type: str = Field(max_length=100, nullable=False)

    size_bytes: int = Field(nullable=False)

    uploaded_by: int = Field(foreign_key="user.id", nullable=False)
    uploaded_at: datetime = Field(default_factory=utcnow, nullable=False)
