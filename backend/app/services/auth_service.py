"""Two-step login (password, then emailed code) and password changes."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlmodel import Session as DbSession
from sqlmodel import select

from app import development
from app.config import settings
from app.database import utcnow
from app.models.session import Session as SessionRow
from app.models.user import User
from app.schemas.user import PasswordSet
from app.security import (
    generate_code,
    hash_secret,
    new_session_id,
    verify_secret,
)
from app.services import email_service

_EMAIL_TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "emails" / "login_code.txt"


class InvalidCredentials(Exception):
    """Unknown email or wrong password."""


class InactiveAccount(Exception):
    """The account is deactivated."""


class CodeInvalid(Exception):
    """Wrong, used or replaced code."""


class CodeExpired(Exception):
    """The code has expired."""


def find_by_email(db: DbSession, email: str) -> User | None:
    return db.exec(select(User).where(User.email == email.strip().lower())).first()


async def start_login(db: DbSession, email: str, password: str) -> None:
    """Step 1: check the password and email a login code.

    A new code replaces any previous one.
    """
    user = find_by_email(db, email)
    if user is None or not verify_secret(user.password_hash, password):
        raise InvalidCredentials()
    if not user.is_active:
        raise InactiveAccount()

    code = generate_code()
    user.login_code_hash = hash_secret(code)
    user.login_code_expires_at = utcnow() + timedelta(minutes=settings.code_ttl_minutes)
    db.add(user)
    db.commit()

    # Print the code to the server log so login still works if email fails.
    print(f"[login code] {user.email}: {code}", flush=True)

    # development-only: keep the code so the verify page can show it.
    development.remember_code(user.email, code)

    body = _EMAIL_TEMPLATE.read_text(encoding="utf-8").format(
        full_name=user.full_name,
        code=code,
        minutes=settings.code_ttl_minutes,
    )
    # If sending fails the caller shows an error; logging in again makes a new code.
    await email_service.send_email(user.email, "Your sign-in code", body)


def verify_code(db: DbSession, email: str, code: str) -> SessionRow:
    """Step 2: check the code, clear it and create a session."""
    user = find_by_email(db, email)
    if user is None or user.login_code_hash is None or user.login_code_expires_at is None:
        raise CodeInvalid()
    if not user.is_active:
        raise InactiveAccount()

    if user.login_code_expires_at <= utcnow():
        _clear_code(db, user)
        raise CodeExpired()

    if not verify_secret(user.login_code_hash, code):
        raise CodeInvalid()

    _clear_code(db, user)
    _sweep_expired_sessions(db)

    now = utcnow()
    row = SessionRow(
        id=new_session_id(),
        user_id=user.id,
        created_at=now,
        expires_at=now + timedelta(hours=settings.session_hours),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def session_is_valid(db: DbSession, token: str | None) -> bool:
    """True if the session token is still valid."""
    if not token:
        return False

    row = db.get(SessionRow, token)
    if row is None or row.expires_at <= utcnow():
        return False

    user = db.get(User, row.user_id)
    return user is not None and user.is_active


def sign_out(db: DbSession, token: str) -> None:
    row = db.get(SessionRow, token)
    if row is not None:
        db.delete(row)
        db.commit()


def set_own_password(db: DbSession, user: User, password: str) -> None:
    """Set the user's own password (length is validated by `PasswordSet`)."""
    checked = PasswordSet(password=password)
    user.password_hash = hash_secret(checked.password)
    user.must_set_password = False
    db.add(user)
    db.commit()


def _clear_code(db: DbSession, user: User) -> None:
    user.login_code_hash = None
    user.login_code_expires_at = None
    db.add(user)
    db.commit()

    # development-only: stop showing a used code.
    development.forget(user.email)


def _sweep_expired_sessions(db: DbSession) -> None:
    """Delete expired sessions (runs on each successful login)."""
    for row in db.exec(select(SessionRow).where(SessionRow.expires_at <= utcnow())).all():
        db.delete(row)
    db.commit()
