"""Admins can't edit their own account (HTTP)."""

from __future__ import annotations

import pytest

from app.models.user import User


@pytest.fixture()
def admin(make_user):
    return make_user(email="admin@example.com", full_name="Only Admin", role="administrator")


def test_your_own_row_is_not_on_the_page(client, sign_in, admin, make_user):
    make_user(email="other@example.com", full_name="Someone Else", role="trainee")
    sign_in(admin)

    page = client.get("/admin/accounts")

    assert page.status_code == 200
    assert "Someone Else" in page.text

    # Their name is in the navbar, so check there are no controls for their account.
    assert f'href="/admin/accounts/{admin.id}"' not in page.text
    assert f'action="/admin/accounts/{admin.id}/active"' not in page.text


def test_the_page_says_why_you_are_not_on_it(client, sign_in, admin):
    """The page explains why the admin's own account isn't listed."""
    sign_in(admin)
    page = client.get("/admin/accounts")

    assert "nobody administers their own" in page.text.lower()


def test_an_administrator_alone_sees_an_empty_list_not_themselves(
    client, sign_in, admin
):
    sign_in(admin)
    page = client.get("/admin/accounts")

    assert "No other accounts yet" in page.text


def test_your_own_edit_form_is_not_found(client, sign_in, admin):
    """Opening your own account's edit page returns 404."""
    sign_in(admin)

    assert client.get(f"/admin/accounts/{admin.id}").status_code == 404


def test_a_crafted_deactivation_of_yourself_is_refused(client, db, sign_in, admin, csrf):
    """Direct POST requests on your own account are rejected."""
    sign_in(admin)

    token = csrf("/admin/accounts")
    response = client.post(
        f"/admin/accounts/{admin.id}/active",
        data={"is_active": "false", "csrf_token": token},
    )

    assert response.status_code == 404
    assert db.get(User, admin.id).is_active is True


def test_a_crafted_demotion_of_yourself_is_refused(client, db, sign_in, admin, csrf):
    sign_in(admin)

    token = csrf("/admin/accounts")
    response = client.post(
        f"/admin/accounts/{admin.id}",
        data={
            "email": admin.email,
            "full_name": admin.full_name,
            "role": "trainee",
            "csrf_token": token,
        },
    )

    assert response.status_code == 404
    assert db.get(User, admin.id).role == "administrator"


def test_a_crafted_password_reset_of_yourself_is_refused(client, sign_in, admin, csrf):
    sign_in(admin)

    token = csrf("/admin/accounts")
    response = client.post(
        f"/admin/accounts/{admin.id}/password",
        data={"password": "a-new-password", "csrf_token": token},
    )

    assert response.status_code == 404


def test_somebody_elses_account_is_still_fully_manageable(
    client, db, sign_in, admin, make_user, csrf
):
    other = make_user(email="other@example.com", full_name="Someone Else", role="trainee")
    sign_in(admin)

    assert client.get(f"/admin/accounts/{other.id}").status_code == 200

    token = csrf("/admin/accounts")
    response = client.post(
        f"/admin/accounts/{other.id}/active",
        data={"is_active": "false", "csrf_token": token},
    )

    assert response.status_code == 303
    assert db.get(User, other.id).is_active is False
