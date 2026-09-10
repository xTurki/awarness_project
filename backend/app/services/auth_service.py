"""Signing in, in two steps, and choosing your own password.

Plain arguments in, plain data out, domain exceptions on failure. No `Request`,
no `Response`, no `HTTPException` (Principle II).
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlmodel import Session as DbSession
from sqlmodel import select

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
    """Unknown address, wrong password."""


class InactiveAccount(Exception):
    """The account exists and is switched off."""


class CodeInvalid(Exception):
    """Wrong code, already used, or replaced by a newer one."""


class CodeExpired(Exception):
    """Right code, too late."""


def find_by_email(db: DbSession, email: str) -> User | None:
    return db.exec(select(User).where(User.email == email.strip().lower())).first()


async def start_login(db: DbSession, email: str, password: str) -> None:
    """Step one. On success a code is emailed and both `login_code_*` columns are
    written together. Any outstanding code for this account is overwritten, which
    is what makes a fresh sign-in invalidate the previous one (FR-018)."""
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

    body = _EMAIL_TEMPLATE.read_text(encoding="utf-8").format(
        full_name=user.full_name,
        code=code,
        minutes=settings.code_ttl_minutes,
    )
    # If this raises, the code is already stored but unusable to anyone who did
    # not receive it, and signing in again replaces it. The caller reports the
    # failure rather than sending the person to wait for nothing (FR-020).
    await email_service.send_email(user.email, "Your sign-in code", body)


def verify_code(
    db: DbSession,
    email: str,
    code: str,
    ip: str | None = None,
    user_agent: str | None = None,
) -> SessionRow:
    """Step two. Clears both code columns and creates the session row."""
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
        ip=(ip or None),
        user_agent=(user_agent or None) and user_agent[:255],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def sign_out(db: DbSession, token: str) -> None:
    row = db.get(SessionRow, token)
    if row is not None:
        db.delete(row)
        db.commit()


def set_own_password(db: DbSession, user: User, password: str) -> None:
    """The eight-character minimum is enforced by `PasswordSet`, in one place
    rather than in each caller (FR-005, FR-012)."""
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


def _sweep_expired_sessions(db: DbSession) -> None:
    """Opportunistic, on each successful sign-in. There is no scheduled cleanup
    in this phase (data-model.md → session rules)."""
    for row in db.exec(select(SessionRow).where(SessionRow.expires_at <= utcnow())).all():
        db.delete(row)
    db.commit()
