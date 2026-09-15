"""Modules: the list, the administrator's forms, and the module home page.

There is **no permanent-delete route**. Removal here is reversible; permanent
removal is a database operation, documented in the README (FR-010).
"""

from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.database import Db, get_session
from app.dependencies import require_password_set, require_role
from app.rendering import render
from app.schemas.module import ModuleRead, ModuleWrite
from app.schemas.user import UserRead
from app.security import csrf_protect
from app.services import content_service, module_service, results_service

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


async def _picture(file: UploadFile | str | None) -> bytes | None:
    """The bytes of a chosen file, or `None` when the field was left empty.

    A file input nobody touched still posts a part, and what that part looks
    like depends on the client. A browser sends it with an empty filename,
    which arrives here as an `UploadFile` with nothing in it. Other clients
    leave the filename out altogether, and then the part is not a file at all
    but an empty string.

    Both mean the same thing, and both have to mean it, or every save that did
    not attach a picture is refused as malformed.
    """
    if file is None or isinstance(file, str):
        return None
    if not (file.filename or "").strip():
        return None
    content = await file.read()
    return content or None


@router.post("/modules", dependencies=[Depends(csrf_protect)])
async def create(
    request: Request,
    title: str = Form(...),
    description: str = Form(""),
    art_colour: str | None = Form(None),
    cover: UploadFile | str | None = File(None),
    db: Db = Depends(get_session),
    account=Depends(require_role("administrator")),
):
    def refused(message: str):
        return render(
            request,
            "modules/form.html",
            {
                "account": UserRead.of(account),
                "title": title,
                "description": description,
                # Carried back, so a missing title does not also discard the
                # colour they picked.
                "art_colour": art_colour,
                "message": message,
            },
            status.HTTP_400_BAD_REQUEST,
        )

    try:
        data = ModuleWrite(
            title=title,
            description=description or None,
            art_colour=art_colour,
        )
    except ValidationError:
        return refused("A module needs a title.")

    # Checked before the module is made, so a refused picture does not leave a
    # module behind that nobody asked for.
    picture = await _picture(cover)
    if picture is not None:
        try:
            content_service.validate_upload(picture, cover.filename or "")
        except content_service.UploadRejected as exc:
            return refused(str(exc))

    created = module_service.create(db, account, data)

    if picture is not None:
        content_service.set_cover(
            db,
            account,
            created.id,
            picture,
            cover.filename or "",
        )

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
            "my_state": results_service.state_for_module(db, module_id, account),
            "final_test": results_service.current_test_row(db, module_id),
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
            "art_colour": ModuleRead.of(module).art_colour,
            "art_image": ModuleRead.of(module).art_image,
        },
    )


@router.post("/modules/{module_id}", dependencies=[Depends(csrf_protect)])
async def update(
    request: Request,
    module_id: int,
    title: str = Form(...),
    description: str = Form(""),
    art_colour: str | None = Form(None),
    cover: UploadFile | str | None = File(None),
    remove_cover: str | None = Form(None),
    db: Db = Depends(get_session),
    account=Depends(require_role("administrator")),
):
    """One form and one Save. The picture is part of the module, so it is saved
    with the rest of it rather than by a button of its own."""
    try:
        current = ModuleRead.of(module_service.get_for(db, module_id, account))
    except module_service.NotFound:
        raise _not_found() from None

    def refused(message: str):
        return render(
            request,
            "modules/form.html",
            {
                "account": UserRead.of(account),
                "module": current,
                "title": title,
                "description": description,
                # Carried back, so a missing title does not also discard the
                # cover they picked.
                "art_image": current.art_image,
                "message": message,
            },
            status.HTTP_400_BAD_REQUEST,
        )

    picture = await _picture(cover)
    if picture is not None:
        try:
            content_service.validate_upload(picture, cover.filename or "")
        except content_service.UploadRejected as exc:
            return refused(str(exc))

    try:
        module_service.update(
            db,
            account,
            module_id,
            ModuleWrite(
                title=title,
                description=description or None,
                art_colour=art_colour,
            ),
        )
    except ValidationError:
        return refused("A module needs a title.")
    except module_service.NotFound:
        raise _not_found() from None

    # After the rest of the save, so a rejected title does not take the
    # picture with it. A new file replaces whatever was there; ticking remove
    # takes the picture off and lets the patterns come back.
    if picture is not None:
        content_service.set_cover(
            db,
            account,
            module_id,
            picture,
            cover.filename or "",
        )
    elif remove_cover:
        content_service.clear_cover(db, account, module_id)

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
