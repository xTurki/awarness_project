"""What a person has been told, inside the platform.

Two routes, and **neither takes a person**. There is no path parameter for
somebody else, so there is no route to guard and nothing to get wrong: the
service scopes every read to the caller (FR-033).

Opening the list marks everything in it seen, so the shell indicator clears by
reading rather than by a dismiss control nobody asked for (FR-031).
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
    # Read before marking, so this page still shows what was new when it was
    # opened. The indicator is gone from the next page onwards.
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
    """For clearing the indicator without opening the list."""
    notification_service.mark_seen(db, account)
    return RedirectResponse("/notifications", status_code=status.HTTP_303_SEE_OTHER)
