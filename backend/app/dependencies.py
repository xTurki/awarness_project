"""FastAPI dependencies for authentication and role checks."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request, status
from sqlmodel import Session as DbSession
from sqlmodel import select

from app.database import get_session, utcnow
from app.models.session import Session as SessionRow
from app.models.user import User
from app.services import notification_service

SESSION_COOKIE = "session"


def _redirect(location: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_303_SEE_OTHER, headers={"Location": location}
    )


def _resolve_account(request: Request, db: DbSession) -> User | None:
    """Return the signed-in user from the session cookie, or None.

    Expired sessions are deleted here.
    """
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None

    row = db.get(SessionRow, token)
    if row is None:
        return None

    if row.expires_at <= utcnow():
        db.delete(row)
        db.commit()
        return None

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        return None

    request.state.session_token = token
    # Used by the navbar on every page.
    request.state.unread_notifications = notification_service.unread_count(db, user)
    return user


def current_account(request: Request, db: DbSession = Depends(get_session)) -> User:
    """Return the signed-in user, or redirect to /login.

    The session and `is_active` are checked on every request, so deactivation
    takes effect immediately.
    """
    user = _resolve_account(request, db)
    if user is None:
        raise _redirect("/login")
    return user


def optional_account(
    request: Request, db: DbSession = Depends(get_session)
) -> User | None:
    """Return the signed-in user or None. Used only by the landing page."""
    return _resolve_account(request, db)


def require_password_set(user: User = Depends(current_account)) -> User:
    """Redirect to the set-password page until the user sets a password."""
    if user.must_set_password:
        raise _redirect("/password/new")
    return user


def require_role(*roles: str) -> Callable[..., User]:
    """Dependency that allows only the given roles (403 otherwise)."""

    def guard(user: User = Depends(require_password_set)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this area.",
            )
        return user

    return guard


def find_by_email(db: DbSession, email: str) -> User | None:
    """Find a user by email (case-insensitive)."""
    return db.exec(select(User).where(User.email == email.strip().lower())).first()
