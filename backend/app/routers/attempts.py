"""Taking a test, reviewing it, and the instructor's view of both.

`POST /attempts/{id}/answer` is the only high-traffic route in the platform. It
does one upsert and returns a fragment; anything more belongs elsewhere.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from app.database import Db, get_session
from app.dependencies import require_password_set
from app.rendering import render
from app.schemas.module import ModuleRead
from app.schemas.quiz import ScoreOverride
from app.schemas.user import UserRead
from app.security import csrf_protect
from app.services import attempt_service, module_service, test_service

router = APIRouter(tags=["attempts"])


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


@router.post("/tests/{test_id}/attempts", dependencies=[Depends(csrf_protect)])
def start(
    test_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    """Starts an attempt, or resumes the one in progress."""
    try:
        row = attempt_service.start(db, account, test_id)
    except attempt_service.AttemptNotFound:
        raise _not_found() from None
    except (attempt_service.OutsideWindow, attempt_service.NoAttemptsLeft) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None

    if row.is_submitted:
        # It expired while they were away, so there is nothing to return to.
        return RedirectResponse(
            f"/attempts/{row.id}/review", status_code=status.HTTP_303_SEE_OTHER
        )
    return RedirectResponse(f"/attempts/{row.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/attempts/{attempt_id}")
def take(
    request: Request,
    attempt_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    """One scrolling page: every question at once, submit at the end."""
    try:
        row = attempt_service.get_own(db, account, attempt_id)
    except attempt_service.AttemptNotFound:
        raise _not_found() from None

    if row.is_submitted:
        return RedirectResponse(
            f"/attempts/{attempt_id}/review", status_code=status.HTTP_303_SEE_OTHER
        )

    test = test_service.get_test(db, account, row.test_id)
    module = module_service.get_for(db, test.module_id, account)

    return render(
        request,
        "attempts/take.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "test": test,
            "attempt": attempt_service.read(row),
            "questions": attempt_service.questions_for(db, row),
            "answers": attempt_service.answers_for(db, attempt_id),
            "remaining": attempt_service.remaining_seconds(row),
        },
    )


@router.post("/attempts/{attempt_id}/answer", dependencies=[Depends(csrf_protect)])
def answer(
    attempt_id: int,
    question_id: int = Form(...),
    option_ids: list[int] = Form(default=[]),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    """One upsert, one small fragment back. Hit on every click."""
    try:
        attempt_service.save_answer(db, account, attempt_id, question_id, option_ids)
    except attempt_service.AttemptNotFound:
        raise _not_found() from None
    except attempt_service.AttemptClosed as exc:
        return HTMLResponse(
            f'<span class="text-danger small">{exc}</span>',
            status_code=status.HTTP_409_CONFLICT,
        )

    return HTMLResponse('<span class="text-success small">Saved</span>')


@router.post("/attempts/{attempt_id}/submit", dependencies=[Depends(csrf_protect)])
def submit(
    attempt_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    """A second submission returns the same result rather than a second one."""
    try:
        attempt_service.submit_own(db, account, attempt_id)
    except attempt_service.AttemptNotFound:
        raise _not_found() from None

    return RedirectResponse(
        f"/attempts/{attempt_id}/review", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/attempts/{attempt_id}/review")
def review(
    request: Request,
    attempt_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    try:
        row = attempt_service.get_viewable(db, account, attempt_id)
    except attempt_service.AttemptNotFound:
        raise _not_found() from None

    if not row.is_submitted:
        # Back into the attempt rather than a partial result.
        return RedirectResponse(f"/attempts/{row.id}", status_code=status.HTTP_303_SEE_OTHER)

    test = test_service.get_test(db, account, row.test_id)
    module = module_service.get_for(db, test.module_id, account)

    return render(
        request,
        "attempts/review.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "test": test,
            "attempt": attempt_service.read(row),
            "review": attempt_service.review(db, row),
        },
    )


@router.get("/tests/{test_id}/attempts")
def cohort(
    request: Request,
    test_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    """Every attempt on the test, for the instructor who runs the module."""
    try:
        rows = attempt_service.list_attempts_for_test(db, account, test_id)
        test = test_service.get_test(db, account, test_id)
        module = module_service.get_for(db, test.module_id, account)
    except (attempt_service.AttemptNotFound, test_service.TestNotFound, module_service.NotFound):
        raise _not_found() from None
    except module_service.NotPermitted:
        raise HTTPException(status_code=403, detail="You do not run this module.") from None

    return render(
        request,
        "attempts/cohort.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "test": test,
            "people": rows,
        },
    )


@router.post("/attempts/{attempt_id}/score", dependencies=[Depends(csrf_protect)])
def override(
    attempt_id: int,
    score_percent: int = Form(...),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    try:
        corrected = attempt_service.override_score(
            db, account, attempt_id, ScoreOverride(score_percent=score_percent)
        )
    except attempt_service.AttemptNotFound:
        raise _not_found() from None
    except module_service.NotPermitted:
        raise HTTPException(status_code=403, detail="You do not run this module.") from None
    except attempt_service.NotSubmitted as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except ValidationError:
        raise HTTPException(status_code=400, detail="A score is a percentage.") from None

    return RedirectResponse(
        f"/tests/{corrected.test_id}/attempts", status_code=status.HTTP_303_SEE_OTHER
    )
