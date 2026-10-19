"""Module roster: registering users as instructors or trainees.

Users can't register themselves; training is assigned.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.database import Db, get_session
from app.dependencies import require_password_set
from app.rendering import render
from app.schemas.module import ModuleRead, RosterAdd
from app.schemas.user import UserRead
from app.security import csrf_protect
from app.services import module_service, registration_service

router = APIRouter(tags=["registrations"])


def _module_for_write(db, module_id: int, account):
    try:
        return module_service.get_for_write(db, module_id, account)
    except module_service.NotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No such module."
        ) from None
    except module_service.NotPermitted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You do not run this module."
        ) from None


@router.get("/modules/{module_id}/roster")
def roster(
    request: Request,
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    return render(
        request,
        "modules/roster.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "roster": registration_service.roster(db, account, module_id),
            "candidates": [
                UserRead.of(person)
                for person in registration_service.candidates(db, account, module_id)
            ],
        },
    )


@router.post("/modules/{module_id}/roster", dependencies=[Depends(csrf_protect)])
def register_people(
    module_id: int,
    user_ids: list[int] = Form(default=[]),
    # Only admins see the role field; instructors always add trainees.
    role_in_module: str = Form("trainee"),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    """Register several users. Already registered users are skipped."""
    _module_for_write(db, module_id, account)

    if user_ids:
        try:
            registration_service.register_many(
                db,
                account,
                module_id,
                RosterAdd(user_ids=user_ids, role_in_module=role_in_module),
            )
        except ValidationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown role."
            ) from None
        except module_service.NotPermitted as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)
            ) from None

    return RedirectResponse(
        f"/modules/{module_id}/roster", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post(
    "/modules/{module_id}/roster/{user_id}/remove", dependencies=[Depends(csrf_protect)]
)
def remove_person(
    module_id: int,
    user_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    _module_for_write(db, module_id, account)
    registration_service.remove(db, account, module_id, user_id)
    return RedirectResponse(
        f"/modules/{module_id}/roster", status_code=status.HTTP_303_SEE_OTHER
    )
