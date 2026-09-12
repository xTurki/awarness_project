"""The question bank. Every route is behind `module:write`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from app.database import Db, get_session
from app.dependencies import require_password_set
from app.rendering import render
from app.schemas.module import ModuleRead
from app.schemas.quiz import QuestionWrite
from app.schemas.user import UserRead
from app.security import csrf_protect
from app.services import module_service, question_service

router = APIRouter(tags=["questions"])


def _module_for_write(db, module_id: int, account):
    try:
        return module_service.get_for_write(db, module_id, account)
    except module_service.NotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such module.") from None
    except module_service.NotPermitted:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="You do not run this module."
        ) from None


def _first_message(exc: ValidationError) -> str:
    return str(exc.errors()[0].get("msg", "That is not valid.")).removeprefix("Value error, ")


def _parse(prompt: str, points: int, options: list[str], correct: list[int]) -> QuestionWrite:
    return QuestionWrite(prompt=prompt, points=points, options=options, correct=correct)


@router.get("/modules/{module_id}/questions")
def bank(
    request: Request,
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    return render(
        request,
        "questions/list.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "questions": question_service.list_bank(db, account, module_id),
        },
    )


@router.get("/modules/{module_id}/questions/new")
def new_form(
    request: Request,
    module_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    return render(
        request,
        "questions/form.html",
        {"account": UserRead.of(account), "module": ModuleRead.of(module)},
    )


@router.post("/modules/{module_id}/questions", dependencies=[Depends(csrf_protect)])
def create(
    request: Request,
    module_id: int,
    prompt: str = Form(...),
    points: int = Form(1),
    options: list[str] = Form(default=[]),
    correct: list[int] = Form(default=[]),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    try:
        data = _parse(prompt, points, options, correct)
        question_service.create_question(db, account, module_id, data)
    except ValidationError as exc:
        return render(
            request,
            "questions/form.html",
            {
                "account": UserRead.of(account),
                "module": ModuleRead.of(module),
                "prompt": prompt,
                "points": points,
                "options": options,
                "correct": correct,
                "message": _first_message(exc),
            },
            status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        f"/modules/{module_id}/questions", status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/modules/{module_id}/questions/{question_id}/edit")
def edit_form(
    request: Request,
    module_id: int,
    question_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    try:
        question = question_service.get_question(db, account, module_id, question_id)
    except question_service.QuestionNotFound:
        raise HTTPException(status_code=404, detail="No such question.") from None

    return render(
        request,
        "questions/form.html",
        {
            "account": UserRead.of(account),
            "module": ModuleRead.of(module),
            "question": question,
            "prompt": question.prompt,
            "points": question.points,
        },
    )


@router.post("/modules/{module_id}/questions/{question_id}", dependencies=[Depends(csrf_protect)])
def update(
    request: Request,
    module_id: int,
    question_id: int,
    prompt: str = Form(...),
    points: int = Form(1),
    options: list[str] = Form(default=[]),
    correct: list[int] = Form(default=[]),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    module = _module_for_write(db, module_id, account)
    try:
        question_service.update_question(
            db, account, module_id, question_id, _parse(prompt, points, options, correct)
        )
    except question_service.QuestionNotFound:
        raise HTTPException(status_code=404, detail="No such question.") from None
    except (ValidationError, question_service.QuestionFrozen) as exc:
        message = _first_message(exc) if isinstance(exc, ValidationError) else str(exc)
        return render(
            request,
            "questions/form.html",
            {
                "account": UserRead.of(account),
                "module": ModuleRead.of(module),
                "question": question_service.get_question(db, account, module_id, question_id),
                "prompt": prompt,
                "points": points,
                "message": message,
            },
            status.HTTP_400_BAD_REQUEST,
        )

    return RedirectResponse(
        f"/modules/{module_id}/questions", status_code=status.HTTP_303_SEE_OTHER
    )


@router.post(
    "/modules/{module_id}/questions/{question_id}/delete", dependencies=[Depends(csrf_protect)]
)
def delete(
    module_id: int,
    question_id: int,
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    _module_for_write(db, module_id, account)
    try:
        question_service.delete_question(db, account, module_id, question_id)
    except question_service.QuestionNotFound:
        raise HTTPException(status_code=404, detail="No such question.") from None
    except question_service.QuestionFrozen as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None

    return RedirectResponse(
        f"/modules/{module_id}/questions", status_code=status.HTTP_303_SEE_OTHER
    )
