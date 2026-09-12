"""Everything that exists only while the platform is being built.

**This whole module is meant to be deleted.** It holds one convenience, showing
the sign-in code on the page that asks for it, so that development does not stop
every time the mail provider refuses to send. It is not part of the platform and
nothing in the platform depends on it.

## Removing it at production time

Setting `SHOW_LOGIN_CODE=false` in `.env` is enough: every function here returns
nothing and the page shows nothing. That is the switch to throw first, because
it takes effect on a restart and touches no code.

To take it out for good, delete this file and the three places that mention it.
They are the only three, and each is marked with the comment `development-only`:

1. `app/services/auth_service.py`, one call in `start_login`
2. `app/routers/auth.py`, one call in `verify_form`
3. `app/templates/auth/verify.html`, one block

The setting in `config.py` and `.env.example` can go with them.

## Why the code is held here and not read back from the database

`login_code_hash` is a hash, so the code cannot be recovered from it. Keeping the
plain code for display means keeping it somewhere, and this module is that
somewhere: a dictionary in the process, never written to disk, never a column,
emptied by a restart. That is deliberate. A database column would outlive this
phase of the project and would have to be migrated away; a dictionary that dies
with the process cannot.
"""

from __future__ import annotations

from app.config import settings

#: email -> the code most recently issued to it. Process memory only.
_ISSUED: dict[str, str] = {}

#: Kept small, so a long development session cannot grow it without bound.
_LIMIT = 50


def remember_code(email: str, code: str) -> None:
    """Hold the code just issued, if this build is allowed to show it."""
    if not settings.show_login_code:
        return

    if len(_ISSUED) >= _LIMIT:
        _ISSUED.clear()
    _ISSUED[email.strip().lower()] = code


def code_for(email: str) -> str | None:
    """The code to display on the verification page, or None.

    None whenever the setting is off, which is what makes the page fall silent
    in production without any page needing to know this module exists.
    """
    if not settings.show_login_code:
        return None
    return _ISSUED.get(email.strip().lower())


def forget(email: str) -> None:
    """Drop a code once it has been used, so the page stops offering a code
    that no longer works."""
    _ISSUED.pop(email.strip().lower(), None)
