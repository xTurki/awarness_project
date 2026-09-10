"""The workspace each role lands on.

Largely empty in this phase — modules arrive in Phase 1. What matters here is
that the three roles see materially different navigation, and that the template
receives a `UserRead` rather than the table model (done-gate 5).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from app.dependencies import require_password_set
from app.rendering import render
from app.schemas.user import UserRead

router = APIRouter(tags=["dashboard"])


@router.get("/")
def dashboard(request: Request, account=Depends(require_password_set)):
    view = UserRead.of(account)
    return render(request, "dashboard.html", {"account": view})
