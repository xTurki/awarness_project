"""Template rendering. Adds the CSRF token and shared values to every page."""

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
    """Short hash of the static assets, added to asset URLs for cache busting."""
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
        # Set in dependencies.py when the session is resolved.
        "unread_notifications": getattr(request.state, "unread_notifications", 0),
        "asset_version": ASSET_VERSION,
        "art_colours": art.COLOURS,
        "upload_max_mb": settings.upload_max_mb,
        "upload_extensions": settings.allowed_image_extensions,
        "assistant_available": tutor_service.is_available(),
    }
    payload.update(context or {})

    response = templates.TemplateResponse(
        request=request, name=template, context=payload, status_code=status_code
    )
    set_csrf_cookie(response, token, secure=is_secure_request(request))
    return response
