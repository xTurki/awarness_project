"""An image uploaded for module content.

The file is saved under `stored_name`. `original_name` is for display only and
is never used to build a file path.
"""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class ContentImage(SQLModel, table=True):
    __tablename__ = "content_image"

    id: int | None = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    # uuid4 hex + extension, generated on upload.
    stored_name: str = Field(max_length=64, nullable=False)

    # Display only.
    original_name: str = Field(max_length=255, nullable=False)
