"""Choosing your own password.

These two are the only authenticated routes not behind `require_password_set`.
Everything else redirects here while the flag is raised (FR-011).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.database import Db, get_session
from app.dependencies import current_account
from app.rendering import render
from app.security import MIN_PASSWORD_LENGTH, csrf_protect
from app.services import auth_service

router = APIRouter(tags=["password"])


@router.get("/password/new")
def form(request: Request, account=Depends(current_account)):
    if not account.must_set_password:
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    return render(request, "auth/set_password.html", {"minimum": MIN_PASSWORD_LENGTH})


@router.post("/password/new", dependencies=[Depends(csrf_protect)])
def submit(
    request: Request,
    password: str = Form(...),
    confirm: str = Form(...),
    account=Depends(current_account),
    db: Db = Depends(get_session),
):
    context = {"minimum": MIN_PASSWORD_LENGTH}

    if password != confirm:
        context["message"] = "The two passwords do not match."
        return render(request, "auth/set_password.html", context, status.HTTP_400_BAD_REQUEST)

    try:
        auth_service.set_own_password(db, account, password)
    except ValidationError:
        context["message"] = f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
        return render(request, "auth/set_password.html", context, status.HTTP_400_BAD_REQUEST)

    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
