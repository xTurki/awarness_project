"""Modules: the list, the administrator's forms, and the module home page.

There is **no permanent-delete route**. Removal here is reversible; permanent
removal is a database operation, documented in the README (FR-010).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.database import Db, get_session
from app.dependencies import require_password_set, require_role
from app.rendering import render
from app.schemas.module import ModuleRead, ModuleWrite
from app.schemas.user import UserRead
from app.security import csrf_protect
from app.services import content_service, module_service

router = APIRouter(tags=["modules"])


def _not_found() -> HTTPException:
    """A module the caller may not see does not exist, as far as they are told."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such module.")


def _forbidden() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your module.")


@router.get("/modules")
def list_modules(
    request: Request, db: Db = Depends(get_session), account=Depends(require_password_set)
):
    return render(
        request,
        "modules/list.html",
        {"account": UserRead.of(account), "modules": module_service.list_for(db, account)},
    )


@router.get("/modules/new")
def new_form(request: Request, account=Depends(require_role("administrator"))):
    return render(request, "modules/form.html", {"account": UserRead.of(account)})


@router.post("/modules", dependencies=[Depends(csrf_protect)])
def create(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    db: Db = Depends(get_session),
    account=Depends(require_role("administrator")),
):
    try:
        data = ModuleWrite(title=title, description=description or None)
    except ValidationError:
        return render(
            request,
            "modules/form.html",
            {
                "account": UserRead.of(account),
                "title": title,
                "description": description,
                "message": "A module needs a title.",
            },
            status.HTTP_400_BAD_REQUEST,
        )

    created = module_service.create(db, account, data)
    return RedirectResponse(f"/modules/{created.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/modules/{module_id}")
def home(
    request: Request,
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    """Module home: description, readable pages in order, module navigation."""
    try:
        module = module_service.get_for(db, module_id, account)
        pages = content_service.list_readable(db, account, module_id)
    except module_service.NotFound:
        raise _not_found() from None

    can_write = _can_write(db, module_id, account)
    return render(
        request,
        "modules/home.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "pages": pages,
            "can_write": can_write,
        },
    )


@router.get("/modules/{module_id}/edit")
def edit_form(
    request: Request,
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_role("administrator")),
):
    try:
        module = module_service.get_for(db, module_id, account)
    except module_service.NotFound:
        raise _not_found() from None

    return render(
        request,
        "modules/form.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "title": module.title,
            "description": module.description,
        },
    )


@router.post("/modules/{module_id}", dependencies=[Depends(csrf_protect)])
def update(
    request: Request,
    module_id: int,
    title: str = Form(...),
    description: str = Form(""),
    db: Db = Depends(get_session),
    account=Depends(require_role("administrator")),
):
    try:
        module_service.update(
            db, account, module_id, ModuleWrite(title=title, description=description or None)
        )
    except ValidationError:
        return render(
            request,
            "modules/form.html",
            {
                "account": UserRead.of(account),
                "title": title,
                "description": description,
                "message": "A module needs a title.",
            },
            status.HTTP_400_BAD_REQUEST,
        )
    except module_service.NotFound:
        raise _not_found() from None

    return RedirectResponse(f"/modules/{module_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/modules/{module_id}/publish", dependencies=[Depends(csrf_protect)])
def publish(
    module_id: int,
    is_published: str = Form(...),
    db: Db = Depends(get_session),
    account=Depends(require_role("administrator")),
):
    try:
        module_service.set_published(db, account, module_id, is_published == "true")
    except module_service.NotFound:
        raise _not_found() from None
    return RedirectResponse(f"/modules/{module_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/modules/{module_id}/delete", dependencies=[Depends(csrf_protect)])
def delete(
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_role("administrator")),
):
    try:
        module_service.soft_delete(db, account, module_id)
    except module_service.NotFound:
        raise _not_found() from None
    return RedirectResponse("/modules", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/modules/{module_id}/restore", dependencies=[Depends(csrf_protect)])
def restore(
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_role("administrator")),
):
    try:
        module_service.restore(db, account, module_id)
    except module_service.NotFound:
        raise _not_found() from None
    return RedirectResponse(f"/modules/{module_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/modules/{module_id}/instructors", dependencies=[Depends(csrf_protect)])
def add_instructor(
    module_id: int,
    user_id: int = Form(...),
    db: Db = Depends(get_session),
    account=Depends(require_role("administrator")),
):
    try:
        module_service.assign_instructor(db, account, module_id, user_id)
    except module_service.NotFound:
        raise _not_found() from None
    return RedirectResponse(
        f"/modules/{module_id}/roster", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post(
    "/modules/{module_id}/instructors/{user_id}/remove", dependencies=[Depends(csrf_protect)]
)
def drop_instructor(
    module_id: int,
    user_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_role("administrator")),
):
    try:
        module_service.remove_instructor(db, account, module_id, user_id)
    except module_service.NotFound:
        raise _not_found() from None
    return RedirectResponse(
        f"/modules/{module_id}/roster", status_code=status.HTTP_303_SEE_OTHER
    )


def _can_write(db, module_id: int, account) -> bool:
    try:
        module_service.get_for_write(db, module_id, account)
        return True
    except (module_service.NotPermitted, module_service.NotFound):
        return False
