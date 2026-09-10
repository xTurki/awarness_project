"""The fact that a person is on a module, and in what capacity.

**No status column.** A registration exists, or the person is not on the module.
There is nothing invited and awaiting acceptance, because people are registered
directly, and nothing concluded, because modules do not end (FR-030).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from app.database import utcnow

ROLES_IN_MODULE = ("instructor", "trainee")


class Registration(SQLModel, table=True):
    __tablename__ = "registration"
    # This constraint is what makes "no duplicates" a database guarantee rather
    # than a check somebody could forget (FR-027).
    __table_args__ = (UniqueConstraint("user_id", "module_id", name="uq_registration_user_module"),)

    id: int | None = Field(default=None, primary_key=True)

    user_id: int = Field(foreign_key="user.id", index=True, nullable=False)
    module_id: int = Field(foreign_key="module.id", index=True, nullable=False)

    # Independent of the platform-wide role: the same person may instruct one
    # module and be a trainee on another. Authorisation asks this column
    # rather than `user.role` (FR-026).
    role_in_module: str = Field(max_length=20, nullable=False)

    registered_at: datetime = Field(default_factory=utcnow, nullable=False)
