"""The three cross-cutting primitives: hashing, CSRF, and rate limiting.

Kept together so they are not scattered, and kept out of `services/` because
the CSRF dependency touches `Request` and Principle II forbids that there.
"""

from __future__ import annotations

import secrets
import time
from collections import defaultdict

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from fastapi import HTTPException, Request, status

from app.config import settings

# One hasher for passwords and for codes: one configuration, one thing to get right.
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
    """Six digits, zero-padded. `secrets` rather than `random`: the latter is
    predictable from observed output, which for a login code matters."""
    return f"{secrets.randbelow(1_000_000):06d}"


def new_session_id() -> str:
    return secrets.token_urlsafe(32)


# ------------------------------------------------------------------------ CSRF


def issue_csrf_token(request: Request) -> str:
    """Reuse the token already on this browser, or mint one.

    The caller is responsible for setting it as a cookie on the response; the
    template puts the same value in a hidden field (double submit, research R3).
    """
    existing = request.cookies.get(CSRF_COOKIE)
    if existing:
        return existing
    return secrets.token_urlsafe(32)


async def csrf_protect(request: Request) -> None:
    """A FastAPI dependency for every state-changing post.

    Works identically before and after sign-in, which matters because the login
    form is the one form with no session behind it.
    """
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

# Process-local. The platform is single-instance by design, so this is not a
# correctness problem; counters reset on restart, which is accepted (research R2).
_attempts: dict[str, list[float]] = defaultdict(list)


def _window_seconds() -> int:
    return settings.login_rate_window_minutes * 60


def rate_limit_exceeded(key: str, limit: int | None = None) -> bool:
    """Fixed window, five attempts per key per five minutes by default.

    `limit` overrides that for callers whose sensible ceiling is not a sign-in
    ceiling: asking a tutor twenty questions while reading is ordinary, while
    twenty sign-in attempts is not.
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
    """Drop keys whose attempts have all aged out, so the dict cannot grow forever."""
    for key in [k for k, stamps in _attempts.items() if not any(s > cutoff for s in stamps)]:
        del _attempts[key]


def reset_rate_limits() -> None:
    """Used by tests. Nothing in the application calls this."""
    _attempts.clear()


def client_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def is_secure_request(request: Request) -> bool:
    """Nginx tells us the scheme; cookies follow it."""
    return request.headers.get("x-forwarded-proto", request.url.scheme) == "https"
