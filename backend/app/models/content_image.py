"""A picture an instructor uploaded.

The file itself lives on a volume under `stored_name`; this row is what the
platform knows about it. `original_name` is kept for display and is **never**
used to build a path, which is what stops a filename deciding where a file lands.

Deliberately thin. There was a `content_type`, a `size_bytes`, an `uploaded_by`
and an `uploaded_at` here, all written on every upload and read by nothing: no
page showed them and no query asked for them. A row that records what nobody
reads makes the table look like it tracks something it does not.
"""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class ContentImage(SQLModel, table=True):
    __tablename__ = "content_image"

    id: int | None = Field(default=None, primary_key=True)
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    # uuid4().hex plus the normalised extension. Generated, never derived from
    # what arrived (research R3).
    stored_name: str = Field(max_length=64, nullable=False)

    # For display only: returned to the editor after an upload so it can name
    # the file somebody just chose.
    original_name: str = Field(max_length=255, nullable=False)
