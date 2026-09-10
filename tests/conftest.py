"""Test harness.

Tests run against **MySQL 8**, never SQLite: this phase relies on a unique index
on `email`, on foreign keys, and on `utf8mb4`, and SQLite enforces none of them
the same way (Constitution VI, research R7).

The database is the disposable one the compose stack already runs. A separate
schema is created for the suite and dropped afterwards, and each test runs inside
a transaction that is rolled back, so tests never see each other's leftovers.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine as sa_create_engine
from sqlalchemy import text
from sqlmodel import Session, SQLModel

from app.config import settings
from app.database import get_session
from app.main import app
from app.models.session import Session as SessionRow  # noqa: F401 - registers the table
from app.models.user import User  # noqa: F401 - registers the table
from app.security import hash_secret, reset_rate_limits

TEST_SCHEMA = f"{settings.mysql_database}_test"

# The application user is scoped to the application database and cannot create or
# drop another one. The suite needs both, so it connects as root, which exists
# only in this disposable local container and never in the application itself.
_ROOT_PASSWORD = os.environ.get("MYSQL_ROOT_PASSWORD", "")


def _server_url() -> str:
    return (
        f"mysql+pymysql://root:{_ROOT_PASSWORD}"
        f"@{settings.mysql_host}:{settings.mysql_port}/?charset=utf8mb4"
    )


def _schema_url() -> str:
    return (
        f"mysql+pymysql://root:{_ROOT_PASSWORD}"
        f"@{settings.mysql_host}:{settings.mysql_port}/{TEST_SCHEMA}?charset=utf8mb4"
    )


@pytest.fixture(scope="session")
def engine():
    server = sa_create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_SCHEMA}"))
        connection.execute(
            text(
                f"CREATE DATABASE {TEST_SCHEMA} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
    server.dispose()

    test_engine = sa_create_engine(_schema_url(), pool_pre_ping=True)
    SQLModel.metadata.create_all(test_engine)

    yield test_engine

    test_engine.dispose()
    server = sa_create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_SCHEMA}"))
    server.dispose()


@pytest.fixture()
def db(engine):
    """One transaction per test, rolled back afterwards.

    `join_transaction_mode="create_savepoint"` is what lets service code call
    `session.commit()` normally while the outer transaction still rolls back.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()
    reset_rate_limits()


@pytest.fixture()
def client(db):
    """A test client whose requests share the test's transaction.

    Instantiated without a context manager on purpose: entering one would run the
    lifespan, which waits for the real database and calls `create_all` against it.
    """
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app, follow_redirects=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def sign_in(db, client):
    """Put a session cookie on the client without walking the two-step flow.

    Tests that are *about* signing in walk it properly; the rest use this.
    """
    from datetime import timedelta

    from app.database import utcnow
    from app.security import new_session_id

    def _sign_in(user: User) -> str:
        now = utcnow()
        row = SessionRow(
            id=new_session_id(),
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(hours=settings.session_hours),
        )
        db.add(row)
        db.commit()
        client.cookies.set("session", row.id)
        return row.id

    return _sign_in


@pytest.fixture()
def csrf(client):
    """Fetch a page so the browser holds a token, and return it for the hidden field."""

    def _csrf(path: str = "/login") -> str:
        client.get(path)
        return client.cookies.get("csrftoken")

    return _csrf


@pytest.fixture()
def make_user(db):
    """Create an account directly, bypassing the administration routes."""

    def _make(
        email: str = "person@example.com",
        password: str = "demo-password",
        role: str = "trainee",
        is_active: bool = True,
        must_set_password: bool = False,
        full_name: str = "Test Person",
    ) -> User:
        user = User(
            email=email.lower(),
            full_name=full_name,
            role=role,
            password_hash=hash_secret(password),
            is_active=is_active,
            must_set_password=must_set_password,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return _make
