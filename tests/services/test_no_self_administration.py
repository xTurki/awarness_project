"""Administrators can't change their own account.

This guarantees there is always at least one active administrator.
"""

from __future__ import annotations

import pytest

from app.models.user import User
from app.schemas.user import UserUpdate
from app.services import admin_service


@pytest.fixture()
def admin(make_user):
    return make_user(email="admin@example.com", full_name="Only Admin", role="administrator")


def _reload(db, person):
    return db.get(User, person.id)


def _edit(person, role=None):
    return UserUpdate(
        email=person.email, full_name=person.full_name, role=role or person.role
    )


# ------------------------------------------------------ acting on yourself


def test_you_cannot_deactivate_yourself(db, admin):
    """An admin can't deactivate themselves."""
    with pytest.raises(admin_service.CannotAdministerSelf):
        admin_service.set_active(db, admin, admin.id, False)

    assert _reload(db, admin).is_active is True


def test_you_cannot_demote_yourself(db, admin):
    with pytest.raises(admin_service.CannotAdministerSelf):
        admin_service.update_account(db, admin, admin.id, _edit(admin, role="trainee"))

    assert _reload(db, admin).role == "administrator"


def test_you_cannot_rename_yourself_either(db, admin):
    """An admin can't edit any field of their own account."""
    with pytest.raises(admin_service.CannotAdministerSelf):
        admin_service.update_account(
            db, admin, admin.id,
            UserUpdate(email="new@example.com", full_name="New Name", role="administrator"),
        )

    assert _reload(db, admin).email == "admin@example.com"


def test_you_cannot_reset_your_own_password(db, admin):
    """An admin can't reset their own password here."""
    with pytest.raises(admin_service.CannotAdministerSelf):
        admin_service.reset_password(db, admin, admin.id, "a-new-password")


def test_you_cannot_even_read_your_own_row(db, admin):
    """Getting your own account for editing is refused."""
    with pytest.raises(admin_service.CannotAdministerSelf):
        admin_service.get_account(db, admin, admin.id)


def test_the_refusal_says_who_can(db, admin):
    with pytest.raises(admin_service.CannotAdministerSelf) as refused:
        admin_service.set_active(db, admin, admin.id, False)

    # The error message explains what to do.
    assert "another administrator" in str(refused.value).lower()


# --------------------------------------------------------------- the list


def test_your_own_account_is_absent_from_the_list(db, admin, make_user):
    make_user(email="other@example.com", role="trainee")

    listed = {row.email for row in admin_service.list_accounts(db, admin)}

    assert "admin@example.com" not in listed
    assert "other@example.com" in listed


def test_another_administrator_still_sees_you(db, admin, make_user):
    """Other admins still see the account."""
    second = make_user(email="second@example.com", role="administrator")

    listed = {row.email for row in admin_service.list_accounts(db, second)}

    assert "admin@example.com" in listed
    assert "second@example.com" not in listed


# --------------------------------------------------- acting on other people


def test_you_may_deactivate_another_administrator(db, admin, make_user):
    other = make_user(email="second@example.com", role="administrator")

    admin_service.set_active(db, admin, other.id, False)

    assert _reload(db, other).is_active is False


def test_you_may_demote_another_administrator(db, admin, make_user):
    other = make_user(email="second@example.com", role="administrator")

    admin_service.update_account(db, admin, other.id, _edit(other, role="instructor"))

    assert _reload(db, other).role == "instructor"


def test_you_may_reset_somebody_elses_password(db, admin, make_user):
    other = make_user(email="t@example.com", role="trainee")

    result = admin_service.reset_password(db, admin, other.id, "a-new-password")

    assert result.must_set_password is True


def test_creating_an_account_is_untouched(db, admin):
    from app.schemas.user import UserCreate

    created = admin_service.create_account(
        db, admin,
        UserCreate(email="fresh@example.com", full_name="Fresh Person",
                   role="trainee", password="a-good-password"),
    )

    assert created.email == "fresh@example.com"


# ------------------------------------------- the property the rule exists for


def test_one_administrator_cannot_reach_zero(db, admin):
    """A single admin can't remove their own admin access in any way."""
    for attempt in (
        lambda: admin_service.set_active(db, admin, admin.id, False),
        lambda: admin_service.update_account(db, admin, admin.id, _edit(admin, role="trainee")),
        lambda: admin_service.update_account(db, admin, admin.id, _edit(admin, role="instructor")),
    ):
        with pytest.raises(admin_service.CannotAdministerSelf):
            attempt()

    assert _reload(db, admin).role == "administrator"
    assert _reload(db, admin).is_active is True


def test_two_administrators_floor_at_one(db, admin, make_user):
    """With two admins, one can remove the other but not themselves."""
    other = make_user(email="second@example.com", role="administrator")

    admin_service.update_account(db, admin, other.id, _edit(other, role="trainee"))

    with pytest.raises(admin_service.CannotAdministerSelf):
        admin_service.update_account(db, admin, admin.id, _edit(admin, role="trainee"))

    remaining = [
        person
        for person in (_reload(db, admin), _reload(db, other))
        if person.role == "administrator" and person.is_active
    ]
    assert len(remaining) == 1


def test_the_retired_guard_is_gone(db):
    """The old "last administrator" check no longer exists."""
    assert not hasattr(admin_service, "LastAdministrator")
    assert not hasattr(admin_service, "sole_administrator_id")
