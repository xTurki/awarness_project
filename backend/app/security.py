"""Security helpers: hashing, CSRF protection and rate limiting."""

from __future__ import annotations

import secrets
import time
from collections import defaultdict

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from fastapi import HTTPException, Request, status

from app.config import settings

# Argon2 hasher used for both passwords and login codes.
_hasher = PasswordHasher()

MIN_PASSWORD_LENGTH = 8
CSRF_COOKIE = "csrftoken"
CSRF_FIELD = "csrf_token"


# --------------------------------------------------------------------- hashing


def hash_secret(raw: str) -> str:
    return _hasher.hash(raw)


def verify_secret(hashed: str | None, raw: str) -> bool:
    if not hashed:
        return False
    try:
        return _hasher.verify(hashed, raw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_code() -> str:
    """Random 6-digit code (uses `secrets`, not `random`)."""
    return f"{secrets.randbelow(1_000_000):06d}"


def new_session_id() -> str:
    return secrets.token_urlsafe(32)


# ------------------------------------------------------------------------ CSRF


def issue_csrf_token(request: Request) -> str:
    """Return the browser's existing CSRF token or create a new one.

    Double-submit pattern: the same value goes in a cookie and a hidden field.
    """
    existing = request.cookies.get(CSRF_COOKIE)
    if existing:
        return existing
    return secrets.token_urlsafe(32)


async def csrf_protect(request: Request) -> None:
    """Dependency for POST routes: the form token must match the cookie."""
    cookie_token = request.cookies.get(CSRF_COOKIE)
    form = await request.form()
    form_token = form.get(CSRF_FIELD)
    if not cookie_token or not form_token or not secrets.compare_digest(
        str(cookie_token), str(form_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This form has expired. Reload the page and try again.",
        )


def set_csrf_cookie(response, token: str, secure: bool) -> None:
    response.set_cookie(
        CSRF_COOKIE,
        token,
        httponly=False,  # the template reads it into a hidden field
        secure=secure,
        samesite="lax",
        path="/",
    )


# ---------------------------------------------------------------- rate limiting

# In-memory counters (single instance). They reset on restart.
_attempts: dict[str, list[float]] = defaultdict(list)


def _window_seconds() -> int:
    return settings.login_rate_window_minutes * 60


def rate_limit_exceeded(key: str, limit: int | None = None) -> bool:
    """Record an attempt and return True if the key is over the limit.

    Defaults to the login limit; `limit` overrides it (e.g. for the tutor).
    """
    now = time.monotonic()
    cutoff = now - _window_seconds()

    recent = [stamp for stamp in _attempts[key] if stamp > cutoff]
    _attempts[key] = recent

    if len(recent) >= (settings.login_rate_limit if limit is None else limit):
        return True

    recent.append(now)
    _prune(cutoff)
    return False


def _prune(cutoff: float) -> None:
    """Remove keys with no recent attempts."""
    for key in [k for k, stamps in _attempts.items() if not any(s > cutoff for s in stamps)]:
        del _attempts[key]


def reset_rate_limits() -> None:
    """Clear all counters (used by tests)."""
    _attempts.clear()


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def is_secure_request(request: Request) -> bool:
    """True if the original request was HTTPS (from nginx's header)."""
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
