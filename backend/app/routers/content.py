"""Content pages and image uploads.

The upload route reads the file off the request here and hands **bytes** to the
service. No file handling lives in this module (Principle I, Principle II).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import ValidationError

from app.config import settings
from app.database import Db, get_session
from app.dependencies import require_password_set
from app.rendering import render
from app.schemas.module import ModuleRead, PageWrite
from app.schemas.user import UserRead
from app.security import csrf_protect
from app.services import content_service, module_service, results_service

router = APIRouter(tags=["content"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


def _forbidden() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="You do not run this module."
    )


def _module_for_write(db, module_id: int, account):
    try:
        return module_service.get_for_write(db, module_id, account)
    except module_service.NotFound:
        raise _not_found() from None
    except module_service.NotPermitted:
        raise _forbidden() from None


# ------------------------------------------------------------- authoring pages


@router.get("/modules/{module_id}/pages")
def page_list(
    request: Request,
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    return render(
        request,
        "modules/page_list.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "pages": content_service.list_pages(db, account, module_id),
        },
    )


@router.get("/modules/{module_id}/pages/new")
def new_page_form(
    request: Request,
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    return render(
        request,
        "modules/page_form.html",
        {"account": UserRead.of(account), "module": ModuleRead.of(module)},
    )


@router.post("/modules/{module_id}/pages", dependencies=[Depends(csrf_protect)])
def create_page(
    request: Request,
    module_id: int,
    title: str = Form(...),
    body: str = Form(""),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    try:
        data = PageWrite(title=title, body=body)
    except ValidationError:
        return render(
            request,
            "modules/page_form.html",
            {
                "account": UserRead.of(account),
                "module": ModuleRead.of(module),
                "title": title,
                "body": body,
                "message": "A page needs a title.",
            },
            status.HTTP_400_BAD_REQUEST,
        )

    content_service.create_page(db, account, module_id, data)
    return RedirectResponse(
        f"/modules/{module_id}/pages", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/modules/{module_id}/pages/{page_id}/edit")
def edit_page_form(
    request: Request,
    module_id: int,
    page_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    try:
        page = content_service.get_page(db, account, module_id, page_id)
    except content_service.PageNotFound:
        raise _not_found() from None

    return render(
        request,
        "modules/page_form.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "page": page,
            "title": page.title,
            "body": page.body,
        },
    )


@router.post("/modules/{module_id}/pages/{page_id}", dependencies=[Depends(csrf_protect)])
def update_page(
    module_id: int,
    page_id: int,
    title: str = Form(...),
    body: str = Form(""),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    _module_for_write(db, module_id, account)
    try:
        content_service.update_page(db, account, module_id, page_id, PageWrite(title=title, body=body))
    except content_service.PageNotFound:
        raise _not_found() from None
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="A page needs a title."
        ) from None

    return RedirectResponse(
        f"/modules/{module_id}/pages", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post(
    "/modules/{module_id}/pages/{page_id}/publish", dependencies=[Depends(csrf_protect)]
)
def publish_page(
    module_id: int,
    page_id: int,
    is_published: str = Form(...),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    _module_for_write(db, module_id, account)
    try:
        content_service.set_page_published(
            db, account, module_id, page_id, is_published == "true"
        )
    except content_service.PageNotFound:
        raise _not_found() from None
    return RedirectResponse(
        f"/modules/{module_id}/pages", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post(
    "/modules/{module_id}/pages/{page_id}/delete", dependencies=[Depends(csrf_protect)]
)
def delete_page(
    module_id: int,
    page_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    _module_for_write(db, module_id, account)
    try:
        content_service.delete_page(db, account, module_id, page_id)
    except content_service.PageNotFound:
        raise _not_found() from None
    return RedirectResponse(
        f"/modules/{module_id}/pages", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post("/modules/{module_id}/pages/reorder", dependencies=[Depends(csrf_protect)])
def reorder_pages(
    module_id: int,
    order: list[int] = Form(...),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    _module_for_write(db, module_id, account)
    content_service.reorder(db, account, module_id, order)
    return RedirectResponse(
        f"/modules/{module_id}/pages", status_code=status.HTTP_303_SEE_OTHER
    )


# --------------------------------------------------------------- reading a page


@router.get("/modules/{module_id}/pages/{page_id}")
def read_page(
    request: Request,
    module_id: int,
    page_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    try:
        module = module_service.get_for(db, module_id, account)
        page = content_service.get_page(db, account, module_id, page_id)
        pages = content_service.list_readable(db, account, module_id)
    except (module_service.NotFound, content_service.PageNotFound):
        raise _not_found() from None

    return render(
        request,
        "modules/page.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "page": page,
            "pages": pages,
            # The test closes the module, so it sits at the end of the same
            # list of pages rather than somewhere else entirely.
            "final_test": results_service.current_test_row(db, module_id),
        },
    )


# ---------------------------------------------------------------------- images


@router.post("/modules/{module_id}/images", dependencies=[Depends(csrf_protect)])
async def upload_image(
    module_id: int,
    file: UploadFile = File(...),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    """Reads the upload here, hands bytes to the service, returns the URL the
    editor inserts. A rejection says why, naming the limit or the accepted
    types, rather than failing blankly (FR-021)."""
    _module_for_write(db, module_id, account)

    content = await file.read()
    try:
        image = content_service.save_image(
            db, account, module_id, content, file.filename or "", file.content_type or ""
        )
    except content_service.UploadRejected as exc:
        return JSONResponse(
            {"error": str(exc), "limit_mb": settings.upload_max_mb},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    return JSONResponse({"url": image.url, "name": image.original_name})
