"""The guarantees this project relies on MySQL to provide.

If any of these fail, every other test in the suite is asserting less than it
appears to (Constitution VI).
"""

from __future__ import annotations

import pytest
from sqlalchemy import inspect, text
from sqlmodel import Session

from app.models.user import User


def test_connection_is_utf8mb4(engine):
    with engine.connect() as connection:
        rows = connection.execute(text("SHOW VARIABLES LIKE 'character_set_%'")).all()
    charsets = {name: value for name, value in rows}

    assert charsets["character_set_client"] == "utf8mb4"
    assert charsets["character_set_connection"] == "utf8mb4"
    assert charsets["character_set_results"] == "utf8mb4"


def test_email_carries_a_unique_index(engine):
    indexes = inspect(engine).get_indexes("user")
    unique_on_email = [
        index for index in indexes if index["unique"] and index["column_names"] == ["email"]
    ]
    assert unique_on_email, "user.email must carry a unique index"


def test_duplicate_email_is_refused_by_the_database(db, make_user):
    """Not merely by a service check somebody could forget."""
    from sqlalchemy.exc import IntegrityError

    make_user(email="taken@example.com")

    db.add(
        User(
            email="taken@example.com",
            full_name="Second",
            role="trainee",
            password_hash="x",
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_session_user_id_is_an_enforced_foreign_key(engine):
    keys = inspect(engine).get_foreign_keys("session")
    assert any(
        key["referred_table"] == "user" and key["constrained_columns"] == ["user_id"]
        for key in keys
    ), "session.user_id must be a foreign key enforced by InnoDB"
