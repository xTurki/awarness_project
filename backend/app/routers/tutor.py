"""Asking about the page you are reading.

One route. It answers with a fragment of a page rather than a page, because
htmx swaps it into the panel in place: the trainee keeps their scroll position
and the page they were reading stays where it was.

The thread is carried in the fragment as hidden fields and posted back with the
next question. That is the whole of "it remembers": nothing is stored on the
server, and closing the page ends it.
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
    # The thread so far, as it was rendered into the last fragment. Paired by
    # position: the nth question goes with the nth answer.
    asked: list[str] = Form(default=[]),
    answered: list[str] = Form(default=[]),
    db: Db = Depends(get_session),
    account=Depends(require_password_set),
):
    # The page is fetched through the same service every other reader uses, so
    # somebody cannot ask about a page they could not open (FR-018, Phase 1).
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
        # The question stays in the box, so a failure costs them nothing but the
        # wait. Nothing here reaches the error page: this is a fragment.
        return _panel(request, module, page, history, error=str(exc), keep=asking)

    return _panel(request, module, page, history + [(asking, answer)])


def _panel(request, module, page, history, *, error=None, keep=""):
    """The panel, rendered whole, thread and form together.

    One template for every outcome, so an answer, a refusal and a failure cannot
    drift into looking like three different features.
    """
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
