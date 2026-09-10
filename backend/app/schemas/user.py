"""Non-table models at every boundary.

Read models exist because `User` carries `password_hash` and `login_code_hash`
and must never reach a template or a response (done-gate 5).

Input models exist because SQLModel does not validate table classes: every form
post is parsed into one of these first, so validation happens in one place
rather than in each router.
"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, field_validator

from app.models.user import ROLES
from app.security import MIN_PASSWORD_LENGTH


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    must_set_password: bool

    @classmethod
    def of(cls, user) -> "UserRead":
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            must_set_password=user.must_set_password,
        )


def _check_role(value: str) -> str:
    if value not in ROLES:
        raise ValueError(f"role must be one of {', '.join(ROLES)}")
    return value


def _check_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return value


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    role: str
    password: str

    _role = field_validator("role")(_check_role)
    _password = field_validator("password")(_check_password)


class UserUpdate(BaseModel):
    email: EmailStr
    full_name: str
    role: str

    _role = field_validator("role")(_check_role)


class PasswordSet(BaseModel):
    """Used both by an administrator resetting a password and by a person choosing
    their own. The rule is the same in both places (FR-005)."""

    password: str

    _password = field_validator("password")(_check_password)
