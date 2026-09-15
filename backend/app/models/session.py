"""Evidence that an account signed in successfully.

Held here rather than in the browser, which is the whole reason access can be
withdrawn at any moment: deleting this row ends the session immediately.

An `ip` and a `user_agent` used to be recorded on every sign-in. Nothing ever
read either one, so they are gone.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel

from app.database import utcnow


class Session(SQLModel, table=True):
    __tablename__ = "session"

    # secrets.token_urlsafe(32), stored as issued (research, accepted simplifications).
    id: str = Field(max_length=64, primary_key=True)

    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)

    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    expires_at: datetime = Field(nullable=False)
