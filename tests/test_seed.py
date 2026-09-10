"""The starting set of accounts (FR-004).

One administrator, one instructor, five trainees, all exempt from the
first-sign-in password change, and running it twice creates nothing.
"""

from __future__ import annotations

from sqlmodel import select

from app.models.user import User
from seed import ACCOUNTS, SEED_PASSWORD, seed
from app.security import MIN_PASSWORD_LENGTH, verify_secret


def _roles(db):
    rows = db.exec(select(User)).all()
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.role] = counts.get(row.role, 0) + 1
    return counts


def test_seeding_creates_seven_accounts_in_the_right_roles(db):
    seed(db)
    assert _roles(db) == {"administrator": 1, "instructor": 1, "trainee": 5}


def test_seeded_accounts_are_exempt_from_the_password_change(db):
    seed(db)
    for row in db.exec(select(User)).all():
        assert row.must_set_password is False
        assert row.is_active is True


def test_seeding_twice_creates_no_duplicates(db):
    first = seed(db)
    second = seed(db)

    assert len(first) == len(ACCOUNTS)
    assert second == []
    assert len(db.exec(select(User)).all()) == len(ACCOUNTS)


def test_the_seed_password_is_usable_and_long_enough(db):
    seed(db)
    assert len(SEED_PASSWORD) >= MIN_PASSWORD_LENGTH

    admin = db.exec(select(User).where(User.role == "administrator")).first()
    assert verify_secret(admin.password_hash, SEED_PASSWORD)
