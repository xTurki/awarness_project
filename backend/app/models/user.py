"""User accounts.

Contains password and code hashes, so templates get a `UserRead` instead.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.database import utcnow

ROLES = ("administrator", "instructor", "trainee")


class User(SQLModel, table=True):
    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)

    # Stored in lowercase.
    email: str = Field(max_length=255, unique=True, index=True, nullable=False)
    full_name: str = Field(max_length=255, nullable=False)
    password_hash: str = Field(max_length=255, nullable=False)
    role: str = Field(max_length=20, nullable=False)

    is_active: bool = Field(default=True, nullable=False)
    must_set_password: bool = Field(default=False, nullable=False)

    # Pending login code (both null when no login is in progress).
    login_code_hash: str | None = Field(default=None, max_length=255, nullable=True)
    login_code_expires_at: datetime | None = Field(default=None, nullable=True)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
