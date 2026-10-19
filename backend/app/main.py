"""Application setup and startup.

Tables are created with `create_all()`. There are no migrations, so a model
change means recreating the database.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI, Request, Response
from sqlmodel import SQLModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import content_seed
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

# Note: `Session` here is the session table model, not a database session.


@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_database()
    assert_utf8mb4()
    SQLModel.metadata.create_all(engine)
    content_seed.run()

    # Runs inside the backend process. Assumes a single backend instance.
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_now,
        CronTrigger(hour=settings.scheduler_hour_utc, minute=0, timezone="UTC"),
        id="daily-due-sweep",
        # Always run, even if late. The default 1s grace would skip the run
        # after a sleep/suspend, and the job is safe to run late.
        misfire_grace_time=None,
        # Missed runs collapse into one.
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

    # Show HTTP errors as HTML pages instead of JSON.
    application.add_exception_handler(StarletteHTTPException, _as_a_page)

    return application


# Error page headings by status code.
_HEADINGS = {
    400: "That was not accepted",
    401: "Sign in to continue",
    403: "You do not have access to this",
    404: "Not found",
    409: "That cannot be changed now",
    429: "Too many attempts",
}


async def _as_a_page(request: Request, exc: StarletteHTTPException) -> Response:
    """Render an HTTP error as a page. Redirects (3xx) are passed through."""
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
