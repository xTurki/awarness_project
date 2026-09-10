"""Template rendering, with the CSRF token attached on the way out.

Every GET that renders a form gets the token as a cookie and the same value in
the template, so the double-submit check on the matching POST has something to
compare (research R3). Doing it here means no route has to remember.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.security import CSRF_FIELD, is_secure_request, issue_csrf_token, set_csrf_cookie

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def render(
    request: Request,
    template: str,
    context: dict[str, Any] | None = None,
    status_code: int = 200,
):
    token = issue_csrf_token(request)
    payload: dict[str, Any] = {"csrf_token": token, "csrf_field": CSRF_FIELD}
    payload.update(context or {})

    response = templates.TemplateResponse(
        request=request, name=template, context=payload, status_code=status_code
    )
    set_csrf_cookie(response, token, secure=is_secure_request(request))
    return response
