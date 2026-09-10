"""The application factory and its lifespan.

`SQLModel.metadata.create_all()` is the single schema authority: there is no
migration tool, and a model change is applied by recreating the database
(Constitution IV). The character set is asserted before any table is created,
because fixing it afterwards is painful (research R6).
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel

from app.database import assert_utf8mb4, engine, wait_for_database
from app.models.session import Session  # noqa: F401 - registers the table
from app.models.user import User  # noqa: F401 - registers the table
from app.routers import admin, auth, dashboard, password


@asynccontextmanager
async def lifespan(app: FastAPI):
    wait_for_database()
    assert_utf8mb4()
    SQLModel.metadata.create_all(engine)
    yield


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
    application.include_router(dashboard.router)
    application.include_router(admin.router)

    return application


app = create_app()
