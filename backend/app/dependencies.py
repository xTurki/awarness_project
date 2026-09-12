"""Route guards.

These touch `Request`, which is why they live here and not under `services/`
(Principle II). `require_password_set` is applied at the router level so that
FR-011 is structural rather than something each route has to remember, and so
there is no allow-list to get subtly wrong (research R4).
"""

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
    """Who is signed in, or None. Never redirects, and never raises.

    Shared by the two dependencies below, which differ only in what they do
    with None. Keeping the resolution in one place is what stops a second copy
    of the session rules drifting: an expired row is deleted here, on sight, for
    both of them (FR-024).
    """
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None

    row = db.get(SessionRow, token)
    if row is None:
        return None

    if row.expires_at <= utcnow():
        db.delete(row)  # refused and deleted on sight (FR-024)
        db.commit()
        return None

    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        return None

    request.state.session_token = token
    # Attached here rather than in each route, so the shell indicator cannot be
    # missing from a page somebody forgot about (Phase 4 FR-030).
    request.state.unread_notifications = notification_service.unread_count(db, user)
    return user


def current_account(request: Request, db: DbSession = Depends(get_session)) -> User:
    """The signed-in account, or a redirect to sign-in.

    Every request re-reads the session row and re-checks `is_active`, which is
    what makes deactivation take effect on the very next request rather than at
    expiry (FR-003, FR-022).
    """
    user = _resolve_account(request, db)
    if user is None:
        raise _redirect("/login")
    return user


def optional_account(
    request: Request, db: DbSession = Depends(get_session)
) -> User | None:
    """The signed-in account, or None, for the one page a visitor may see.

    Only the landing page uses this. Everything else in the platform sits
    behind `require_password_set`, and a page that renders differently for a
    visitor is exactly the thing worth keeping to one.
    """
    return _resolve_account(request, db)


def require_password_set(user: User = Depends(current_account)) -> User:
    """Nothing else is reachable while the flag is raised (FR-011)."""
    if user.must_set_password:
        raise _redirect("/password/new")
    return user


def require_role(*roles: str) -> Callable[..., User]:
    """Refusal happens before any handler runs, so a hidden control is never the
    enforcement (FR-027)."""

    def guard(user: User = Depends(require_password_set)) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this area.",
            )
        return user

    return guard


def find_by_email(db: DbSession, email: str) -> User | None:
    """Shared lookup: email is stored and compared lowercased."""
    return db.exec(select(User).where(User.email == email.strip().lower())).first()
