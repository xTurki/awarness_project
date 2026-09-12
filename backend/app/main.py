"""The application factory and its lifespan.

`SQLModel.metadata.create_all()` is the single schema authority: there is no
migration tool, and a model change is applied by recreating the database
(Constitution IV). The character set is asserted before any table is created,
because fixing it afterwards is painful (research R6).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request, Response
from sqlmodel import SQLModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import assert_utf8mb4, engine, wait_for_database
from app.rendering import render
from app.models.content_image import ContentImage  # noqa: F401 - registers the table
from app.models.module import Module  # noqa: F401 - registers the table
from app.models.attempt import Attempt, AttemptAnswer  # noqa: F401 - registers the tables
from app.models.notification import Notification  # noqa: F401 - registers the table
from app.models.page import Page  # noqa: F401 - registers the table
from app.models.question import AnswerOption, Question  # noqa: F401 - registers the tables
from app.models.registration import Registration  # noqa: F401 - registers the table
from app.models.session import Session  # noqa: F401 - registers the table
from app.models.test import Test, TestQuestion  # noqa: F401 - registers the tables
from app.models.user import User  # noqa: F401 - registers the table
from app.routers import (
    admin,
    attempts,
    auth,
    content,
    modules,
    notifications,
    password,
    questions,
    results,
    registrations,
    tests,
    tutor,
)
from app.services.daily_job import run_now

# This module deliberately names no session type. `Session` here is the session
# *table*, imported above to register it, and a database session built under
# that name would silently construct a row instead. The job builds its own.


@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_database()
    assert_utf8mb4()
    SQLModel.metadata.create_all(engine)

    # In the backend container that already runs, on the loop that already
    # exists. No fourth container, no worker, no broker (FR-026, FR-028). This
    # assumes exactly one backend instance; two would run two schedulers.
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_now,
        CronTrigger(hour=settings.scheduler_hour_utc, minute=0, timezone="UTC"),
        id="daily-due-sweep",
        # Run it however late the wakeup arrives. APScheduler's default grace is
        # one second, which silently *skips* a firing that is even slightly
        # late, and a late wakeup is ordinary here: a container VM whose clock
        # was suspended delivers one minutes after the hour. Skipping would cost
        # a whole day of reminders for no reason, when this job is a full sweep
        # precisely so that running it late is safe (FR-027, research R7).
        misfire_grace_time=None,
        # Several firings missed at once collapse into a single run, because
        # asking who is due now twice in a row has nothing to add.
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    print(
        f"[scheduler] daily sweep at {settings.scheduler_hour_utc:02d}:00 UTC",
        flush=True,
    )

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    application = FastAPI(
        title="SME Cybersecurity Awareness Training Platform",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )

    application.include_router(auth.router)
    application.include_router(password.router)
    application.include_router(admin.router)
    application.include_router(modules.router)
    application.include_router(content.router)
    application.include_router(registrations.router)
    application.include_router(questions.router)
    application.include_router(tests.router)
    application.include_router(attempts.router)
    application.include_router(results.router)
    application.include_router(notifications.router)
    application.include_router(tutor.router)

    # Every refusal reaches a person as a page, not as JSON. Without this a
    # rejected form shows the browser a line of `{"detail": ...}`, which tells
    # somebody using the platform nothing and reads like a crash.
    application.add_exception_handler(StarletteHTTPException, _as_a_page)

    return application


#: What each refusal is called, in the words of somebody who just hit it rather
#: than the words of the protocol.
_HEADINGS = {
    400: "That was not accepted",
    401: "Sign in to continue",
    403: "You do not have access to this",
    404: "Not found",
    409: "That cannot be changed now",
    429: "Too many attempts",
}


async def _as_a_page(request: Request, exc: StarletteHTTPException) -> Response:
    """Render a refusal as a page.

    Redirects pass straight through: the route guards raise them as exceptions
    too, so treating a 303 as a failure would break every sign-in.
    """
    if 300 <= exc.status_code < 400:
        return Response(status_code=exc.status_code, headers=dict(exc.headers or {}))

    return render(
        request,
        "error.html",
        {
            "heading": _HEADINGS.get(exc.status_code, "Something went wrong"),
            "detail": exc.detail or "The page could not be shown.",
        },
        status_code=exc.status_code,
    )


app = create_app()
