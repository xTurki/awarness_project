"""Pytest fixtures.

Tests run against MySQL (not SQLite) in a separate test schema that is created
for the run and dropped afterwards. Each test runs in a transaction that is
rolled back.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, text

from app.config import settings
from app.database import get_session
from app.main import app
from app.models.session import Session as SessionRow  # noqa: F401 - registers the table
from app.models.user import User  # noqa: F401 - registers the table
from app.security import hash_secret, reset_rate_limits

TEST_SCHEMA = f"{settings.mysql_database}_test"

# Connect as root so the test schema can be created and dropped.
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
    server = create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_SCHEMA}"))
        connection.execute(
            text(
                f"CREATE DATABASE {TEST_SCHEMA} "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        )
    server.dispose()

    test_engine = create_engine(_schema_url(), pool_pre_ping=True)
    SQLModel.metadata.create_all(test_engine)

    yield test_engine

    test_engine.dispose()
    server = create_engine(_server_url(), isolation_level="AUTOCOMMIT")
    with server.connect() as connection:
        connection.execute(text(f"DROP DATABASE IF EXISTS {TEST_SCHEMA}"))
    server.dispose()


@pytest.fixture()
def db(engine):
    """One transaction per test, rolled back afterwards.

    `create_savepoint` lets service code call `commit()` normally.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()
    reset_rate_limits()


@pytest.fixture(autouse=True)
def mail(monkeypatch):
    """Replace email sending with a list, so no test opens an SMTP connection."""
    sent: list[tuple[str, str, str]] = []

    def fake_send(to: str, subject: str, body: str) -> None:
        sent.append((to, subject, body))

    monkeypatch.setattr("app.services.email_service.send_email_now", fake_send)
    # Send immediately instead of in the background thread.
    monkeypatch.setattr("app.services.notification_service.SEND_IN_BACKGROUND", False)
    return sent


@pytest.fixture()
def failing_mail(monkeypatch):
    """Make every email send fail."""
    from app.services.email_service import EmailDeliveryFailed

    def refuse(to: str, subject: str, body: str) -> None:
        raise EmailDeliveryFailed("no route to host")

    monkeypatch.setattr("app.services.email_service.send_email_now", refuse)


@pytest.fixture()
def client(db):
    """Test client that uses the test's database session.

    Not used as a context manager, so the app startup (lifespan) doesn't run.
    """
    app.dependency_overrides[get_session] = lambda: db
    yield TestClient(app, follow_redirects=False)
    app.dependency_overrides.clear()


@pytest.fixture()
def sign_in(db, client):
    """Log a user in by creating a session directly (skips the login flow)."""
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
    """Load a page to get a CSRF token and return it."""

    def _csrf(path: str = "/login") -> str:
        client.get(path)
        return client.cookies.get("csrftoken")

    return _csrf


@pytest.fixture()
def make_user(db):
    """Create a user directly in the database."""

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
