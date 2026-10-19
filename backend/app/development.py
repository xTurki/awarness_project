"""Development helper: show the login code on the verify page.

Disabled when SHOW_LOGIN_CODE=false. To remove it completely, delete this file
and the places marked `development-only`:
- app/services/auth_service.py (start_login, _clear_code)
- app/routers/auth.py (verify_form)
- app/templates/auth/verify.html

Codes are kept in memory only, since the database stores just a hash.
"""

from __future__ import annotations

from app.config import settings

# email -> latest code issued
_ISSUED: dict[str, str] = {}

_LIMIT = 50


def remember_code(email: str, code: str) -> None:
    """Store the code if showing codes is enabled."""
    if not settings.show_login_code:
        return

    if len(_ISSUED) >= _LIMIT:
        _ISSUED.clear()
    _ISSUED[email.strip().lower()] = code


def code_for(email: str) -> str | None:
    """Return the code to show on the verify page, or None if disabled."""
    if not settings.show_login_code:
        return None
    return _ISSUED.get(email.strip().lower())


def forget(email: str) -> None:
    """Remove a code after it has been used."""
    _ISSUED.pop(email.strip().lower(), None)
