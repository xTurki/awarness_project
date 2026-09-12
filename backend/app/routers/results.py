"""Where everyone stands.

`GET /` lives here now. It was moved out of `dashboard.py`, which is gone: the
application must register `GET /` exactly once, and a second registration is
shadowed silently with no error to find.

A trainee's dashboard **is** their results page. One route, one template, one
list. Instructors and administrators keep the dashboard Phase 0 gave them.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse

from app.database import Db, get_session
from app.dependencies import optional_account, require_password_set
from app.rendering import render
from app.schemas.module import ModuleRead
from app.schemas.user import UserRead
from app.services import module_service, results_service

router = APIRouter(tags=["results"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


@router.get("/")
def dashboard(
    request: Request, db: Db = Depends(get_session), account=Depends(optional_account)
):
    """The landing page to a visitor, the dashboard to anyone signed in.

    One route, branching on the session, rather than two. Registering `GET /`
    twice is shadowed silently with no error to find, which is the thing Phase 3
    moved this route to prevent.
    """
    if account is None:
        # A visitor gets a page that says what this is and offers a way in,
        # rather than being dropped into a form with no context.
        return render(request, "welcome.html", {})

    # `optional_account` does not enforce this the way `require_password_set`
    # does, so the one route that uses it checks for itself. Without this, the
    # dashboard would be the single page reachable before choosing a password
    # (Phase 0 FR-011).
    if account.must_set_password:
        return RedirectResponse("/password/new", status_code=status.HTTP_303_SEE_OTHER)

    if account.role == "trainee":
        return render(
            request,
            "results/dashboard.html",
            {
                "account": UserRead.of(account),
                "rows": results_service.for_person(db, account),
            },
        )

    # Unchanged for the other two roles: they see modules, not training they owe.
    return render(
        request,
        "dashboard.html",
        {
            "account": UserRead.of(account),
            "modules": module_service.list_for(db, account),
        },
    )


@router.get("/results/modules/{module_id}")
def module_history(
    request: Request,
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    """The caller's own attempts on one module, at every test it has had."""
    try:
        module = module_service.get_for(db, module_id, account)
        rows = results_service.history_for(db, account, module_id, account)
    except module_service.NotFound:
        raise _not_found() from None

    return render(
        request,
        "results/module.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "subject": UserRead.of(account),
            "rows": rows,
            "current": results_service.current_test_row(db, module_id),
        },
    )


@router.get("/modules/{module_id}/results")
def cohort(
    request: Request,
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    try:
        module = module_service.get_for_write(db, module_id, account)
        rows = results_service.for_module(db, module_id, account)
    except module_service.NotFound:
        raise _not_found() from None
    except module_service.NotPermitted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You do not run this module."
        ) from None

    return render(
        request,
        "results/cohort.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "rows": rows,
        },
    )


@router.get("/modules/{module_id}/results/{user_id}")
def person_history(
    request: Request,
    module_id: int,
    user_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    """One person's attempt history for one module.

    This is what every cohort row links to, and the only route by which FR-018
    is reachable at all.
    """
    try:
        module = module_service.get_for_write(db, module_id, account)
    except module_service.NotFound:
        raise _not_found() from None
    except module_service.NotPermitted:
        raise HTTPException(status_code=403, detail="You do not run this module.") from None

    subject = results_service.subject_on_module(db, module_id, user_id)
    if subject is None:
        raise _not_found()

    return render(
        request,
        "results/module.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "subject": UserRead.of(subject),
            "rows": results_service.history_for(db, subject, module_id, account),
            "current": results_service.current_test_row(db, module_id),
        },
    )
