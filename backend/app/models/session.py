"""Server-side login sessions. Deleting a row logs the user out."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.database import utcnow


class Session(SQLModel, table=True):
    __tablename__ = "session"

    # secrets.token_urlsafe(32)
    id: str = Field(max_length=64, primary_key=True)

    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    expires_at: datetime = Field(nullable=False)
