"""Refusal at the point of request, not a hidden button (FR-027).

quickstart Scenario 2: a trainee requesting /admin/accounts gets 403, not a page
with the controls removed.
"""

from __future__ import annotations

import pytest

ADMIN_PATHS = ["/admin/accounts", "/admin/accounts/new"]


@pytest.mark.parametrize("role", ["trainee", "instructor"])
@pytest.mark.parametrize("path", ADMIN_PATHS)
def test_non_administrators_are_refused(client, make_user, sign_in, role, path):
    sign_in(make_user(email=f"{role}@example.com", role=role))
    assert client.get(path).status_code == 403


@pytest.mark.parametrize("path", ADMIN_PATHS)
def test_an_administrator_is_admitted(client, make_user, sign_in, path):
    sign_in(make_user(email="admin@example.com", role="administrator"))
    assert client.get(path).status_code == 200


def test_administrative_navigation_is_absent_for_a_trainee(client, make_user, sign_in):
    sign_in(make_user(email="t@example.com", role="trainee"))
    page = client.get("/")
    assert page.status_code == 200
    assert "/admin/accounts" not in page.text


def test_administrative_navigation_is_present_for_an_administrator(client, make_user, sign_in):
    sign_in(make_user(email="a@example.com", role="administrator"))
    page = client.get("/")
    assert page.status_code == 200
    assert "/admin/accounts" in page.text


def test_each_role_sees_its_own_heading(client, make_user, sign_in):
    """Phase 1 replaced the placeholder panels with the module list, so the
    role-specific wording moved with it."""
    headings = {
        "instructor": "Modules you run",
        "trainee": "Your training",
        "administrator": "Modules",
    }
    for role, heading in headings.items():
        sign_in(make_user(email=f"{role}@example.com", role=role))
        assert heading in client.get("/").text
        client.cookies.clear()
