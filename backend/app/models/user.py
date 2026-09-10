"""A person who can sign in.

This is a `table=True` model carrying two secrets. It is never returned from an
endpoint and never passed into a template (done-gate 5); templates receive a
`UserRead` built in the service layer.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.database import utcnow

ROLES = ("administrator", "instructor", "trainee")


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)

    # Stored lowercased, so Ahmad@x.com and ahmad@x.com are one account.
    email: str = Field(max_length=255, unique=True, index=True, nullable=False)
    full_name: str = Field(max_length=255, nullable=False)
    password_hash: str = Field(max_length=255, nullable=False)
    role: str = Field(max_length=20, nullable=False)

    is_active: bool = Field(default=True, nullable=False)
    must_set_password: bool = Field(default=False, nullable=False)

    # Written together and cleared together. Both null means no sign-in is in progress.
    login_code_hash: str | None = Field(default=None, max_length=255, nullable=True)
    login_code_expires_at: datetime | None = Field(default=None, nullable=True)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
