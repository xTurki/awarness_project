"""Account administration.

Every route sits behind `require_role("administrator")`, applied to the router
so refusal happens before any handler runs (FR-027). There is no delete route:
accounts are deactivated, never removed.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.database import Db, get_session
from app.dependencies import require_role
from app.rendering import render
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.security import MIN_PASSWORD_LENGTH, csrf_protect
from app.services import admin_service

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_role("administrator"))],
)

ROLE_CHOICES = ("administrator", "instructor", "trainee")


@router.get("/accounts")
def list_accounts(
    request: Request,
    db: Db = Depends(get_session),
    actor=Depends(require_role("administrator")),
):
    rows = admin_service.list_accounts(db, actor)
    return render(
        request,
        "admin/list.html",
        {"account": UserRead.of(actor), "accounts": rows},
    )


@router.get("/accounts/new")
def new_form(request: Request, actor=Depends(require_role("administrator"))):
    return render(
        request,
        "admin/form.html",
        {"account": UserRead.of(actor), "roles": ROLE_CHOICES, "minimum": MIN_PASSWORD_LENGTH},
    )


@router.post("/accounts", dependencies=[Depends(csrf_protect)])
def create(
    request: Request,
    email: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    password: str = Form(...),
    db: Db = Depends(get_session),
    actor=Depends(require_role("administrator")),
):
    base = {"account": UserRead.of(actor), "roles": ROLE_CHOICES, "minimum": MIN_PASSWORD_LENGTH}
    values = {"email": email, "full_name": full_name, "role": role}

    try:
        data = UserCreate(email=email, full_name=full_name, role=role, password=password)
    except ValidationError as exc:
        return render(
            request,
            "admin/form.html",
            {**base, **values, "message": _first_message(exc)},
            status.HTTP_400_BAD_REQUEST,
        )

    try:
        admin_service.create_account(db, actor, data)
    except admin_service.EmailAlreadyUsed:
        return render(
            request,
            "admin/form.html",
            {**base, **values, "message": "An account with that email address already exists."},
            status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse("/admin/accounts", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/accounts/{user_id}")
def edit_form(
    request: Request,
    user_id: int,
    db: Db = Depends(get_session),
    actor=Depends(require_role("administrator")),
):
    try:
        subject = admin_service.get_account(db, actor, user_id)
    except admin_service.AccountNotFound:
        raise _not_found()

    return render(
        request,
        "admin/form.html",
        {
            "account": UserRead.of(actor),
            "roles": ROLE_CHOICES,
            "minimum": MIN_PASSWORD_LENGTH,
            "subject": subject,
            "email": subject.email,
            "full_name": subject.full_name,
            "role": subject.role,
        },
    )


@router.post("/accounts/{user_id}", dependencies=[Depends(csrf_protect)])
def update(
    request: Request,
    user_id: int,
    email: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    db: Db = Depends(get_session),
    actor=Depends(require_role("administrator")),
):
    try:
        data = UserUpdate(email=email, full_name=full_name, role=role)
        admin_service.update_account(db, actor, user_id, data)
    except ValidationError as exc:
        return _edit_error(request, actor, user_id, email, full_name, role, _first_message(exc))
    except admin_service.EmailAlreadyUsed:
        return _edit_error(
            request, actor, user_id, email, full_name, role,
            "Another account already uses that email address.",
        )
    except admin_service.AccountNotFound:
        raise _not_found()

    return RedirectResponse("/admin/accounts", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/accounts/{user_id}/password", dependencies=[Depends(csrf_protect)])
def reset_password(
    request: Request,
    user_id: int,
    password: str = Form(...),
    db: Db = Depends(get_session),
    actor=Depends(require_role("administrator")),
):
    try:
        admin_service.reset_password(db, actor, user_id, password)
    except ValidationError:
        return _edit_error(
            request, actor, user_id, None, None, None,
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )
    except admin_service.AccountNotFound:
        raise _not_found()

    return RedirectResponse("/admin/accounts", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/accounts/{user_id}/active", dependencies=[Depends(csrf_protect)])
def set_active(
    request: Request,
    user_id: int,
    is_active: str = Form(...),
    db: Db = Depends(get_session),
    actor=Depends(require_role("administrator")),
):
    try:
        admin_service.set_active(db, actor, user_id, is_active == "true")
    except admin_service.AccountNotFound:
        raise _not_found()

    return RedirectResponse("/admin/accounts", status_code=status.HTTP_303_SEE_OTHER)


# ----------------------------------------------------------------- small helpers


def _not_found():
    from fastapi import HTTPException

    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such account.")


def _first_message(exc: ValidationError) -> str:
    first = exc.errors()[0]
    return str(first.get("msg", "That is not valid.")).removeprefix("Value error, ")


def _edit_error(request, actor, user_id, email, full_name, role, message):
    return render(
        request,
        "admin/form.html",
        {
            "account": UserRead.of(actor),
            "roles": ROLE_CHOICES,
            "minimum": MIN_PASSWORD_LENGTH,
            "subject": UserRead(
                id=user_id,
                email=email or "",
                full_name=full_name or "",
                role=role or "trainee",
                is_active=True,
                must_set_password=False,
            ),
            "email": email or "",
            "full_name": full_name or "",
            "role": role or "trainee",
            "message": message,
        },
        status.HTTP_400_BAD_REQUEST,
    )
