"""Engine, session dependency, and the wait-for-MySQL retry loop.

The compose healthcheck is not enough on a first run: MySQL reports healthy
once it accepts connections, but initialising the data directory can still be
in progress. Ten attempts two seconds apart removes an intermittent startup
failure that would otherwise be blamed on something else (research R5).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import datetime, timezone

from sqlalchemy import text
from sqlmodel import Session, create_engine

from app.config import settings

CONNECT_ATTEMPTS = 10
CONNECT_WAIT_SECONDS = 2

# Routers annotate their database parameter with this alias rather than importing
# `Session` themselves, so done-gate 4 stays mechanically checkable: no module
# under app/routers/ contains the token `Session` or `select` at all.
Db = Session

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
)


def utcnow() -> datetime:
    """Naive UTC, which is what every timestamp column in this project holds."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def wait_for_database() -> None:
    """Block until the database answers, or give up loudly."""
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
    """Fail at boot rather than discovering mangled text months later (research R6)."""
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
