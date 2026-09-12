"""Building and publishing a test.

A trainee sees the time limit, the attempts allowed, and the pass mark before
they start (FR-009).
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.database import Db, get_session
from app.dependencies import require_password_set
from app.rendering import render
from app.schemas.module import ModuleRead
from app.schemas.quiz import TestWrite
from app.schemas.user import UserRead
from app.security import csrf_protect
from app.services import (
    attempt_service,
    content_service,
    module_service,
    question_service,
    results_service,
    test_service,
)

router = APIRouter(tags=["tests"])


def _module_for_write(db, module_id: int, account):
    try:
        return module_service.get_for_write(db, module_id, account)
    except module_service.NotFound:
        raise HTTPException(status_code=404, detail="No such module.") from None
    except module_service.NotPermitted:
        raise HTTPException(status_code=403, detail="You do not run this module.") from None


def _when(value: str) -> datetime | None:
    """An empty datetime-local field means "no bound", not an error."""
    return datetime.fromisoformat(value) if value else None


def _optional_int(value: str) -> int | None:
    return int(value) if value not in ("", None) else None


def _message_of(exc: Exception) -> str:
    """The sentence to show above the form.

    A pydantic error arrives wrapped in its own prefix and buried in a list, so
    it is unwrapped here; every other refusal already carries the sentence the
    form should show.
    """
    if isinstance(exc, ValidationError):
        return str(exc.errors()[0].get("msg", "")).removeprefix("Value error, ")
    return str(exc)


@router.get("/modules/{module_id}/tests")
def listing(
    request: Request,
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    try:
        module = module_service.get_for(db, module_id, account)
        rows = test_service.list_for_module(db, account, module_id)
    except module_service.NotFound:
        raise HTTPException(status_code=404, detail="No such module.") from None

    can_write = _can_write(db, module_id, account)
    return render(
        request,
        "tests/list.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "tests": rows,
            "can_write": can_write,
        },
    )


@router.get("/modules/{module_id}/tests/new")
def new_form(
    request: Request,
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    return render(
        request,
        "tests/form.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "bank": question_service.list_bank(db, account, module_id),
        },
    )


@router.post("/modules/{module_id}/tests", dependencies=[Depends(csrf_protect)])
def create(
    request: Request,
    module_id: int,
    title: str = Form(...),
    instructions: str = Form(""),
    opens_at: str = Form(""),
    closes_at: str = Form(""),
    time_limit_minutes: str = Form(""),
    allowed_attempts: int = Form(1),
    shuffle_questions: str = Form(""),
    passing_score: str = Form(""),
    retake_interval_days: str = Form(""),
    completion_deadline_days: str = Form(""),
    question_ids: list[int] = Form(default=[]),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    try:
        data = TestWrite(
            title=title,
            instructions=instructions or None,
            opens_at=_when(opens_at),
            closes_at=_when(closes_at),
            time_limit_minutes=_optional_int(time_limit_minutes),
            allowed_attempts=allowed_attempts,
            shuffle_questions=shuffle_questions == "true",
            passing_score=_optional_int(passing_score),
            retake_interval_days=_optional_int(retake_interval_days),
            completion_deadline_days=_optional_int(completion_deadline_days),
            question_ids=question_ids,
        )
        created = test_service.create(db, account, module_id, data)
    except (
        ValidationError,
        test_service.CannotPublish,
        test_service.InvalidSchedule,
    ) as exc:
        message = _message_of(exc)
        return render(
            request,
            "tests/form.html",
            {
                "account": UserRead.of(account),
                "module": ModuleRead.of(module),
                "bank": question_service.list_bank(db, account, module_id),
                "title": title,
                "message": message,
            },
            status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        f"/modules/{module_id}/tests/{created.id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/modules/{module_id}/tests/{test_id}/edit")
def edit_form(
    request: Request,
    module_id: int,
    test_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    try:
        row = test_service.get_test(db, account, test_id)
    except test_service.TestNotFound:
        raise HTTPException(status_code=404, detail="No such test.") from None

    # A frozen test renders read-only, and says why (FR-014).
    return render(
        request,
        "tests/form.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "test": row,
            "bank": question_service.list_bank(db, account, module_id),
            "title": row.title,
            "chosen": [q.id for q in test_service.questions_of(db, test_id)],
            "message": test_service.FROZEN_MESSAGE if row.is_frozen else None,
            "message_kind": "warning" if row.is_frozen else None,
        },
    )


@router.post("/modules/{module_id}/tests/{test_id}", dependencies=[Depends(csrf_protect)])
def update(
    request: Request,
    module_id: int,
    test_id: int,
    title: str = Form(...),
    instructions: str = Form(""),
    opens_at: str = Form(""),
    closes_at: str = Form(""),
    time_limit_minutes: str = Form(""),
    allowed_attempts: int = Form(1),
    shuffle_questions: str = Form(""),
    passing_score: str = Form(""),
    retake_interval_days: str = Form(""),
    completion_deadline_days: str = Form(""),
    question_ids: list[int] = Form(default=[]),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    try:
        test_service.update(
            db,
            account,
            test_id,
            TestWrite(
                title=title,
                instructions=instructions or None,
                opens_at=_when(opens_at),
                closes_at=_when(closes_at),
                time_limit_minutes=_optional_int(time_limit_minutes),
                allowed_attempts=allowed_attempts,
                shuffle_questions=shuffle_questions == "true",
                passing_score=_optional_int(passing_score),
                retake_interval_days=_optional_int(retake_interval_days),
                completion_deadline_days=_optional_int(completion_deadline_days),
                question_ids=question_ids,
            ),
        )
    except test_service.TestNotFound:
        raise HTTPException(status_code=404, detail="No such test.") from None
    except test_service.TestFrozen as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    except (
        ValidationError,
        test_service.CannotPublish,
        test_service.InvalidSchedule,
    ) as exc:
        # Back to the form with the reason above it, the way the sign-in page
        # reports a wrong password. Somebody who has just filled in eight fields
        # should not have to fill them in again to read why one was refused.
        return render(
            request,
            "tests/form.html",
            {
                "account": UserRead.of(account),
                "module": ModuleRead.of(module),
                "test": test_service.get_test(db, account, test_id),
                "bank": question_service.list_bank(db, account, module_id),
                "title": title,
                "chosen": question_ids,
                "message": _message_of(exc),
            },
            status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        f"/modules/{module_id}/tests/{test_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post(
    "/modules/{module_id}/tests/{test_id}/publish", dependencies=[Depends(csrf_protect)]
)
def publish(
    request: Request,
    module_id: int,
    test_id: int,
    is_published: str = Form(...),
    confirmed: str = Form(""),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)

    # Publishing a replacement resets everyone who had passed, because state
    # follows the module's currently published test. The instructor is told how
    # many people that is, before it happens (Phase 3 FR-027).
    if is_published == "true" and confirmed != "true":
        current = results_service.current_test_row(db, module_id)
        if current is not None and current.id != test_id:
            affected = results_service.count_affected_by_replacement(db, module_id)
            if affected:
                return render(
                    request,
                    "tests/confirm_publish.html",
                    {
                        "account": UserRead.of(account),
                        "module": ModuleRead.of(module),
                        "current": current,
                        "replacement": test_service.get_test(db, account, test_id),
                        "affected": affected,
                    },
                )

    try:
        test_service.set_published(db, account, test_id, is_published == "true")
    except test_service.TestNotFound:
        raise HTTPException(status_code=404, detail="No such test.") from None
    except test_service.CannotPublish as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None

    return RedirectResponse(
        f"/modules/{module_id}/tests/{test_id}", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/modules/{module_id}/tests/{test_id}")
def detail(
    request: Request,
    module_id: int,
    test_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    try:
        module = module_service.get_for(db, module_id, account)
        row = test_service.get_test(db, account, test_id)
    except (module_service.NotFound, test_service.TestNotFound):
        raise HTTPException(status_code=404, detail="No such test.") from None

    return render(
        request,
        "tests/detail.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "test": row,
            "can_write": _can_write(db, module_id, account),
            "attempts": attempt_service.history_for(db, account, test_id),
            # The sidebar, because this page is the last page of the module.
            "pages": content_service.list_readable(db, account, module_id),
            "final_test": results_service.current_test_row(db, module_id),
            # None when they may sit it, otherwise the reason, so the page can
            # offer the button only to somebody who can use it.
            "cannot_start": attempt_service.why_not_startable(
                db, account, test_service.row_of(db, test_id)
            ),
        },
    )


def _can_write(db, module_id: int, account) -> bool:
    try:
        module_service.get_for_write(db, module_id, account)
        return True
    except (module_service.NotFound, module_service.NotPermitted):
        return False
