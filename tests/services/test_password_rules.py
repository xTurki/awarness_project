"""The eight-character minimum, in every place a password is set.

Seeding, administrator creation, administrator reset, and the person's own
choice (FR-005, FR-012).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.user import PasswordSet, UserCreate
from app.security import MIN_PASSWORD_LENGTH
from app.services import admin_service, auth_service
from seed import SEED_PASSWORD

SHORT = "sh0rt"


def test_the_minimum_is_eight():
    assert MIN_PASSWORD_LENGTH == 8


def test_seed_password_meets_the_minimum():
    assert len(SEED_PASSWORD) >= MIN_PASSWORD_LENGTH


def test_administrator_creation_refuses_a_short_password():
    with pytest.raises(ValidationError):
        UserCreate(
            email="new@example.com", full_name="New", role="trainee", password=SHORT
        )


def test_administrator_reset_refuses_a_short_password(db, make_user):
    admin = make_user(email="admin@example.com", role="administrator")
    subject = make_user(email="subject@example.com")

    with pytest.raises(ValidationError):
        admin_service.reset_password(db, admin, subject.id, SHORT)


def test_a_person_choosing_their_own_refuses_a_short_password(db, make_user):
    user = make_user(email="person@example.com", must_set_password=True)

    with pytest.raises(ValidationError):
        auth_service.set_own_password(db, user, SHORT)

    db.refresh(user)
    assert user.must_set_password is True, "a refused password must not clear the flag"


def test_a_long_enough_password_is_accepted_and_clears_the_flag(db, make_user):
    user = make_user(email="person@example.com", must_set_password=True)

    auth_service.set_own_password(db, user, "long-enough-password")

    db.refresh(user)
    assert user.must_set_password is False


def test_password_set_accepts_exactly_the_minimum():
    assert PasswordSet(password="a" * MIN_PASSWORD_LENGTH).password
