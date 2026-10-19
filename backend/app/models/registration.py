"""A user's registration on a module, as instructor or trainee."""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel, UniqueConstraint

from app.database import utcnow

ROLES_IN_MODULE = ("instructor", "trainee")


class Registration(SQLModel, table=True):
    __tablename__ = "registration"
    __table_args__ = (UniqueConstraint("user_id", "module_id", name="uq_registration_user_module"),)

    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    # Separate from the user's platform role; access checks use this.
    role_in_module: str = Field(max_length=20, nullable=False)

    registered_at: datetime = Field(default_factory=utcnow, nullable=False)
