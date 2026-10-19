"""Account administration.

Each function checks the acting user's role itself (not only the router).
"""

from __future__ import annotations

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models.user import User
from app.schemas.user import PasswordSet, UserCreate, UserRead, UserUpdate
from app.security import hash_secret


class NotPermitted(Exception):
    """The acting user is not an administrator."""


class EmailAlreadyUsed(Exception):
    """The email is already used by another account."""


class AccountNotFound(Exception):
    pass


class CannotAdministerSelf(Exception):
    """An administrator tried to change their own account.

    Blocking this means there is always at least one administrator left.
    """


def _require_administrator(actor: User) -> None:
    if actor.role != "administrator":
        raise NotPermitted()


def _normalise(email: str) -> str:
    return email.strip().lower()


def _refuse_self(actor: User, user_id: int) -> None:
    """Raise if the admin is acting on their own account."""
    if actor.id == user_id:
        raise CannotAdministerSelf(
            "You cannot change your own account here. Another administrator can "
            "do it for you."
        )


def _email_taken(db: DbSession, email: str, *, excluding: int | None = None) -> bool:
    found = db.exec(select(User).where(User.email == email)).first()
    return found is not None and found.id != excluding


def list_accounts(db: DbSession, actor: User) -> list[UserRead]:
    """All accounts except the caller's own."""
    _require_administrator(actor)
    rows = db.exec(select(User).order_by(User.full_name)).all()
    return [UserRead.of(row) for row in rows if row.id != actor.id]


def get_account(db: DbSession, actor: User, user_id: int) -> UserRead:
    _require_administrator(actor)
    _refuse_self(actor, user_id)
    row = db.get(User, user_id)
    if row is None:
        raise AccountNotFound()
    return UserRead.of(row)


def create_account(db: DbSession, actor: User, data: UserCreate) -> UserRead:
    """Create an account. The user must set a new password on first login."""
    _require_administrator(actor)

    email = _normalise(str(data.email))
    if _email_taken(db, email):
        raise EmailAlreadyUsed()

    row = User(
        email=email,
        full_name=data.full_name.strip(),
        role=data.role,
        password_hash=hash_secret(data.password),
        is_active=True,
        must_set_password=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return UserRead.of(row)


def update_account(db: DbSession, actor: User, user_id: int, data: UserUpdate) -> UserRead:
    _require_administrator(actor)
    _refuse_self(actor, user_id)

    row = db.get(User, user_id)
    if row is None:
        raise AccountNotFound()

    email = _normalise(str(data.email))
    if _email_taken(db, email, excluding=user_id):
        raise EmailAlreadyUsed()

    row.email = email
    row.full_name = data.full_name.strip()
    row.role = data.role
    db.add(row)
    db.commit()
    db.refresh(row)
    return UserRead.of(row)


def reset_password(db: DbSession, actor: User, user_id: int, password: str) -> UserRead:
    """Reset a password. The user must choose a new one at next login."""
    _require_administrator(actor)
    _refuse_self(actor, user_id)

    row = db.get(User, user_id)
    if row is None:
        raise AccountNotFound()

    checked = PasswordSet(password=password)
    row.password_hash = hash_secret(checked.password)
    row.must_set_password = True
    db.add(row)
    db.commit()
    db.refresh(row)
    return UserRead.of(row)


def set_active(db: DbSession, actor: User, user_id: int, is_active: bool) -> UserRead:
    """Activate or deactivate an account (takes effect on the next request)."""
    _require_administrator(actor)
    _refuse_self(actor, user_id)

    row = db.get(User, user_id)
    if row is None:
        raise AccountNotFound()

    row.is_active = is_active
    db.add(row)
    db.commit()
    db.refresh(row)
    return UserRead.of(row)
