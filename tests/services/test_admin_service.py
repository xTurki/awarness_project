"""Account administration, and the role check on every function.

Done-gate 6: every one of these verifies the acting account itself, so the router
guard is a second line rather than the enforcement.
"""

from __future__ import annotations

import pytest

from app.schemas.user import UserCreate, UserUpdate
from app.services import admin_service


@pytest.fixture()
def admin(make_user):
    return make_user(email="admin@example.com", role="administrator")


@pytest.fixture()
def trainee(make_user):
    return make_user(email="trainee@example.com", role="trainee")


def _new(email="new@example.com", role="trainee"):
    return UserCreate(email=email, full_name="New Person", role=role, password="demo-password")


# --------------------------------------------------------------- the role check


def test_every_function_refuses_a_non_administrator(db, trainee, admin):
    subject = admin  # any existing id will do; the check happens first

    with pytest.raises(admin_service.NotPermitted):
        admin_service.list_accounts(db, trainee)
    with pytest.raises(admin_service.NotPermitted):
        admin_service.create_account(db, trainee, _new())
    with pytest.raises(admin_service.NotPermitted):
        admin_service.update_account(
            db, trainee, subject.id, UserUpdate(email="x@example.com", full_name="X", role="trainee")
        )
    with pytest.raises(admin_service.NotPermitted):
        admin_service.reset_password(db, trainee, subject.id, "demo-password")
    with pytest.raises(admin_service.NotPermitted):
        admin_service.set_active(db, trainee, subject.id, False)
    with pytest.raises(admin_service.NotPermitted):
        admin_service.get_account(db, trainee, subject.id)


# ------------------------------------------------------------------- creating


def test_creating_an_account_raises_must_set_password(db, admin):
    created = admin_service.create_account(db, admin, _new())
    assert created.must_set_password is True
    assert created.is_active is True


def test_a_duplicate_email_is_refused_on_create(db, admin, trainee):
    with pytest.raises(admin_service.EmailAlreadyUsed):
        admin_service.create_account(db, admin, _new(email=trainee.email))


def test_email_comparison_is_lowercase(db, admin, trainee):
    """Ahmad@x.com and ahmad@x.com are one account."""
    with pytest.raises(admin_service.EmailAlreadyUsed):
        admin_service.create_account(db, admin, _new(email=trainee.email.upper()))


def test_a_created_account_is_stored_lowercased(db, admin):
    created = admin_service.create_account(db, admin, _new(email="Mixed@Example.com"))
    assert created.email == "mixed@example.com"


# -------------------------------------------------------------------- editing


def test_editing_changes_name_email_and_role(db, admin, trainee):
    updated = admin_service.update_account(
        db,
        admin,
        trainee.id,
        UserUpdate(email="moved@example.com", full_name="Moved", role="instructor"),
    )
    assert (updated.email, updated.full_name, updated.role) == (
        "moved@example.com",
        "Moved",
        "instructor",
    )


def test_a_duplicate_email_is_refused_on_edit(db, admin, trainee):
    with pytest.raises(admin_service.EmailAlreadyUsed):
        admin_service.update_account(
            db,
            admin,
            trainee.id,
            UserUpdate(email=admin.email, full_name="Clash", role="trainee"),
        )


def test_keeping_your_own_email_on_edit_is_not_a_duplicate(db, admin, trainee):
    updated = admin_service.update_account(
        db,
        admin,
        trainee.id,
        UserUpdate(email=trainee.email, full_name="Renamed", role="trainee"),
    )
    assert updated.full_name == "Renamed"


# ------------------------------------------------------- resetting and switching


def test_resetting_a_password_raises_must_set_password(db, admin, trainee):
    updated = admin_service.reset_password(db, admin, trainee.id, "another-password")
    assert updated.must_set_password is True


def test_deactivating_and_reactivating(db, admin, trainee):
    assert admin_service.set_active(db, admin, trainee.id, False).is_active is False
    assert admin_service.set_active(db, admin, trainee.id, True).is_active is True


def test_an_unknown_account_is_reported(db, admin):
    with pytest.raises(admin_service.AccountNotFound):
        admin_service.get_account(db, admin, 999_999)


def test_listing_returns_read_models_without_secrets(db, admin, trainee):
    rows = admin_service.list_accounts(db, admin)
    assert rows
    for row in rows:
        assert not hasattr(row, "password_hash")
        assert not hasattr(row, "login_code_hash")
