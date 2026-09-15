"""Template rendering, with the CSRF token attached on the way out.

Every GET that renders a form gets the token as a cookie and the same value in
the template, so the double-submit check on the matching POST has something to
compare (research R3). Doing it here means no route has to remember.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app import art
from app.config import settings
from app.services import tutor_service
from app.security import CSRF_FIELD, is_secure_request, issue_csrf_token, set_csrf_cookie

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

_STATIC = Path(__file__).parent / "static"


def _asset_version() -> str:
    """A short digest of the project's own assets, computed once at import.

    Every asset URL carries it, so changing a stylesheet changes its address and
    the new file is fetched immediately. Without it a cache in front of the
    platform serves the previous one until its TTL expires, which on the live
    deployment is four hours: long enough that a change looks like it failed.

    Computed at import rather than per request, because the files cannot change
    while the process runs: they are baked into the image.
    """
    digest = hashlib.sha256()
    for name in ("css/bootstrap.min.css", "css/app.css", "js/localtime.js"):
        path = _STATIC / name
        if path.exists():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:10]


ASSET_VERSION = _asset_version()


def render(
    request: Request,
    template: str,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
):
    token = issue_csrf_token(request)
    payload: dict[str, Any] = {
        "csrf_token": token,
        "csrf_field": CSRF_FIELD,
        # Counted while the session was resolved, so the shell indicator appears
        # on every authenticated page without a single route asking for it
        # (Phase 4 FR-030).
        "unread_notifications": getattr(request.state, "unread_notifications", 0),
        # Stamped onto every asset URL, so a stylesheet change is never served
        # stale by a cache in front of the platform.
        "asset_version": ASSET_VERSION,
        # The colours a module cover may wear. Constant, so the picker
        # offers exactly what the service validates against.
        "art_colours": art.COLOURS,
        # What an upload form may promise. Taken from the one setting nginx
        # derives its own limit from, so the page cannot name a size the proxy
        # would refuse.
        "upload_max_mb": settings.upload_max_mb,
        "upload_extensions": settings.allowed_image_extensions,
        # With no API key the panel is never rendered and the route never
        # answers, so the platform runs exactly as it did before the assistant
        # existed.
        "assistant_available": tutor_service.is_available(),
    }
    payload.update(context or {})

    response = templates.TemplateResponse(
        request=request, name=template, context=payload, status_code=status_code
    )
    set_csrf_cookie(response, token, secure=is_secure_request(request))
    return response
