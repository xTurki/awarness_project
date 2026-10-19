"""Study assistant: ask a question about the current page.

Returns an HTML fragment for htmx. The conversation is kept in hidden form
fields, not on the server.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status

from app.database import Db, get_session
from app.dependencies import require_password_set
from app.rendering import render
from app.security import csrf_protect, rate_limit_exceeded
from app.services import content_service, module_service, tutor_service
from app.config import settings

router = APIRouter(tags=["tutor"])

TOO_MANY = (
    "That is a lot of questions in a short time. Give it a few minutes, then ask again."
)


@router.post(
    "/modules/{module_id}/pages/{page_id}/ask", dependencies=[Depends(csrf_protect)]
)
def ask(
    request: Request,
    module_id: int,
    page_id: int,
    question: str = Form(""),
    # Previous questions and answers (matched by position).
    asked: list[str] = Form(default=[]),
    answered: list[str] = Form(default=[]),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    # Uses the normal page access check.
    try:
        module = module_service.get_for(db, module_id, account)
        page = content_service.get_page(db, account, module_id, page_id)
    except (module_service.NotFound, content_service.PageNotFound):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found."
        ) from None

    history = list(zip(asked, answered))
    asking = (question or "").strip()

    if not asking:
        return _panel(request, module, page, history, error="Ask a question first.")

    if rate_limit_exceeded(f"ask:{account.id}", limit=settings.ask_rate_limit):
        return _panel(request, module, page, history, error=TOO_MANY, keep=asking)

    try:
        answer = tutor_service.ask(
            asking,
            module_title=module.title,
            page_title=page.title,
            body_html=page.body,
            history=history,
        )
    except tutor_service.AssistantUnavailable as exc:
        # Keep the question in the box so the user can retry.
        return _panel(request, module, page, history, error=str(exc), keep=asking)

    return _panel(request, module, page, history + [(asking, answer)])


def _panel(request, module, page, history, *, error=None, keep=""):
    """Render the assistant panel (conversation and form)."""
    return render(
        request,
        "components/ask_panel.html",
        {
            "module": module,
            "page": page,
            "thread": history,
            "ask_error": error,
            "ask_keep": keep,
            "ask_fragment": True,
        },
    )
