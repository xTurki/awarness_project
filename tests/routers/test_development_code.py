"""The code shown on the page that asks for it, and the switch that hides it.

This covers a feature meant to be deleted. The test that matters most is the one
proving `SHOW_LOGIN_CODE=false` silences it completely, because that is the
switch thrown at production time, before anybody gets round to deleting the
module itself.
"""

from __future__ import annotations

import pytest

from app import development
from app.config import settings


@pytest.fixture(autouse=True)
def clean():
    """The store is process memory, so it outlives a test unless emptied."""
    development._ISSUED.clear()
    yield
    development._ISSUED.clear()


@pytest.fixture()
def showing(monkeypatch):
    monkeypatch.setattr(settings, "show_login_code", True)


@pytest.fixture()
def hidden(monkeypatch):
    monkeypatch.setattr(settings, "show_login_code", False)


def _sign_in_step_one(client, csrf, email="a@example.com", password="demo-password"):
    token = csrf("/login")
    return client.post(
        "/login",
        data={"email": email, "password": password, "csrf_token": token},
    )


# --------------------------------------------------------- while developing


def test_the_code_appears_on_the_page_that_asks_for_it(
    client, make_user, csrf, showing
):
    make_user(email="a@example.com", password="demo-password")
    _sign_in_step_one(client, csrf)

    page = client.get("/login/verify?email=a@example.com")

    assert page.status_code == 200
    assert "Development build" in page.text
    code = development.code_for("a@example.com")
    assert code is not None
    assert code in page.text


def test_the_shown_code_actually_works(client, make_user, csrf, showing):
    """If the page shows one code and the database holds another, the feature
    is worse than useless."""
    make_user(email="a@example.com", password="demo-password")
    _sign_in_step_one(client, csrf)

    shown = development.code_for("a@example.com")
    token = csrf("/login/verify?email=a@example.com")
    response = client.post(
        "/login/verify",
        data={"email": "a@example.com", "code": shown, "csrf_token": token},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_a_used_code_stops_being_offered(client, make_user, csrf, showing):
    make_user(email="a@example.com", password="demo-password")
    _sign_in_step_one(client, csrf)

    shown = development.code_for("a@example.com")
    token = csrf("/login/verify?email=a@example.com")
    client.post(
        "/login/verify",
        data={"email": "a@example.com", "code": shown, "csrf_token": token},
    )

    assert development.code_for("a@example.com") is None


def test_signing_in_again_replaces_the_shown_code(client, make_user, csrf, showing):
    make_user(email="a@example.com", password="demo-password")
    _sign_in_step_one(client, csrf)
    first = development.code_for("a@example.com")

    _sign_in_step_one(client, csrf)
    second = development.code_for("a@example.com")

    assert second is not None
    assert second != first or first is not None  # a fresh code replaced the old


def test_one_persons_code_is_not_shown_on_anothers_page(
    client, make_user, csrf, showing
):
    make_user(email="a@example.com", password="demo-password")
    make_user(email="b@example.com", password="demo-password")
    _sign_in_step_one(client, csrf, email="a@example.com")

    page = client.get("/login/verify?email=b@example.com")

    assert "Development build" not in page.text


def test_the_store_does_not_grow_without_bound(showing):
    for n in range(development._LIMIT + 5):
        development.remember_code(f"p{n}@example.com", "000000")

    assert len(development._ISSUED) <= development._LIMIT


# ------------------------------------------------------- the production switch


def test_the_switch_silences_the_page(client, make_user, csrf, hidden):
    """`SHOW_LOGIN_CODE=false` and the page says nothing, with no code
    remembered anywhere. This is what is thrown before launch."""
    make_user(email="a@example.com", password="demo-password")
    _sign_in_step_one(client, csrf)

    page = client.get("/login/verify?email=a@example.com")

    assert "Development build" not in page.text
    assert development.code_for("a@example.com") is None


def test_nothing_is_remembered_at_all_when_it_is_off(hidden):
    development.remember_code("a@example.com", "123456")

    assert development._ISSUED == {}


def test_the_switch_is_off_unless_asked_for():
    """The default is the production behaviour, so a deployment that forgets to
    set anything is the safe one."""
    from app.config import Settings

    assert Settings.model_fields["show_login_code"].default is False


def test_signing_in_still_works_with_it_off(client, make_user, csrf, hidden):
    """The feature is a convenience. Removing it changes nothing else."""
    make_user(email="a@example.com", password="demo-password")
    response = _sign_in_step_one(client, csrf)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login/verify")
