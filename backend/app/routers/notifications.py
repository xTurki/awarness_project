"""In-app notifications for the current user.

Opening the list marks all notifications as read.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import RedirectResponse

from app.database import Db, get_session
from app.dependencies import require_password_set
from app.rendering import render
from app.schemas.user import UserRead
from app.security import csrf_protect
from app.services import notification_service

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
def listing(
    request: Request,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    rows = notification_service.list_for(db, account)
    # Load before marking as read, so new items are still highlighted on this page.
    notification_service.mark_seen(db, account)

    return render(
        request,
        "notifications/list.html",
        {"account": UserRead.of(account), "rows": rows},
    )


@router.post("/notifications/read", dependencies=[Depends(csrf_protect)])
def mark_read(
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    """Mark all as read without opening the list."""
    notification_service.mark_seen(db, account)
    return RedirectResponse("/notifications", status_code=status.HTTP_303_SEE_OTHER)
