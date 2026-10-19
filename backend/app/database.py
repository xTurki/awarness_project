"""Database engine, session dependency and startup checks.

MySQL can report healthy before it is fully ready on first run, so startup
retries the connection a few times.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlmodel import Session, create_engine, text

from app.config import settings

CONNECT_ATTEMPTS = 10
CONNECT_WAIT_SECONDS = 2

# Routers use this alias so they never import `Session` or `select` directly
# (database access stays in services; a test checks this).
Db = Session

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
)


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (how timestamps are stored)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def wait_for_database() -> None:
    """Wait until the database accepts connections, or raise."""
    last_error: Exception | None = None
    for attempt in range(1, CONNECT_ATTEMPTS + 1):
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return
        except Exception as exc:  # noqa: BLE001 - any driver error means "not ready"
            last_error = exc
            print(
                f"database not ready (attempt {attempt}/{CONNECT_ATTEMPTS}): {exc}",
                flush=True,
            )
            time.sleep(CONNECT_WAIT_SECONDS)
    raise RuntimeError(
        f"database unreachable after {CONNECT_ATTEMPTS} attempts"
    ) from last_error


def assert_utf8mb4() -> None:
    """Fail at startup if the connection is not using utf8mb4."""
    with engine.connect() as connection:
        rows = connection.execute(text("SHOW VARIABLES LIKE 'character_set_%'")).all()
    charsets = {name: value for name, value in rows}
    for key in ("character_set_client", "character_set_connection", "character_set_results"):
        value = charsets.get(key)
        if value != "utf8mb4":
            raise RuntimeError(
                f"{key} is {value!r}, expected 'utf8mb4'. "
                "Fix the connection URL and the server before any table is created."
            )


def get_session() -> Iterator[Session]:
    with Session(engine) as session:
        yield session
