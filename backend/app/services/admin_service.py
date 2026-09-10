"""Account administration, the only way an account comes into existence.

Every function takes the acting account and verifies its role itself. The router
guard is a second line, not the enforcement (Principle III, done-gate 6).
"""

from __future__ import annotations

from sqlmodel import Session as DbSession
from sqlmodel import select

from app.models.user import User
from app.schemas.user import PasswordSet, UserCreate, UserRead, UserUpdate
from app.security import hash_secret


class NotPermitted(Exception):
    """The acting account is not an administrator."""


class EmailAlreadyUsed(Exception):
    """Another account already holds that address."""


class AccountNotFound(Exception):
    pass


def _require_administrator(actor: User) -> None:
    if actor.role != "administrator":
        raise NotPermitted()


def _normalise(email: str) -> str:
    return email.strip().lower()


def _email_taken(db: DbSession, email: str, *, excluding: int | None = None) -> bool:
    found = db.exec(select(User).where(User.email == email)).first()
    return found is not None and found.id != excluding


def list_accounts(db: DbSession, actor: User) -> list[UserRead]:
    _require_administrator(actor)
    rows = db.exec(select(User).order_by(User.full_name)).all()
    return [UserRead.of(row) for row in rows]


def get_account(db: DbSession, actor: User, user_id: int) -> UserRead:
    _require_administrator(actor)
    row = db.get(User, user_id)
    if row is None:
        raise AccountNotFound()
    return UserRead.of(row)


def create_account(db: DbSession, actor: User, data: UserCreate) -> UserRead:
    """`must_set_password` is raised here, always: the administrator knows the
    password they issued, and this is how the person takes sole possession of
    the account (FR-010)."""
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
    """Raises `must_set_password` exactly as creation does, so the person chooses
    their own at the next sign-in (FR-010)."""
    _require_administrator(actor)

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
    """Deactivation takes effect on that account's very next request, because
    `current_account` re-checks this column every time (FR-003)."""
    _require_administrator(actor)

    row = db.get(User, user_id)
    if row is None:
        raise AccountNotFound()

    row.is_active = is_active
    db.add(row)
    db.commit()
    db.refresh(row)
    return UserRead.of(row)
