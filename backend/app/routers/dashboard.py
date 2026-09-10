"""The workspace each role lands on.

A trainee's dashboard lists the modules they are registered on. **Phase 3
extends this same page with a state against each module; it does not add a
second list** (FR-031, Phase 1 Clarifications).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.database import Db, get_session
from app.dependencies import require_password_set
from app.rendering import render
from app.schemas.user import UserRead
from app.services import module_service

router = APIRouter(tags=["dashboard"])


@router.get("/")
def dashboard(
    request: Request, db: Db = Depends(get_session), account=Depends(require_password_set)
):
    return render(
        request,
        "dashboard.html",
        {
            "account": UserRead.of(account),
            "modules": module_service.list_for(db, account),
        },
    )
