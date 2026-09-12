"""Publishing a module, from the page it now lives on.

The control sits on the module page beside the badge that says whether anybody
can see the module, rather than behind Settings. Publishing is restricted to
administrators (FR-005), so the page offers it to nobody else and the service
refuses it regardless of what the page offered.
"""

from __future__ import annotations

import pytest

from app.models.module import Module
from app.models.registration import Registration


@pytest.fixture()
def module(db):
    row = Module(title="Phishing Awareness", is_published=False)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@pytest.fixture()
def admin(make_user):
    return make_user(email="admin@example.com", role="administrator")


@pytest.fixture()
def owner(db, make_user, module):
    person = make_user(email="owner@example.com", role="instructor")
    db.add(Registration(user_id=person.id, module_id=module.id,
                        role_in_module="instructor"))
    db.commit()
    return person


# ------------------------------------------------------------ where it sits


def test_the_control_is_on_the_module_page(client, sign_in, admin, module):
    sign_in(admin)
    page = client.get(f"/modules/{module.id}")

    assert page.status_code == 200
    assert f'action="/modules/{module.id}/publish"' in page.text
    assert "Publish" in page.text


def test_it_comes_after_the_roster_button(client, sign_in, admin, module):
    """Where it was asked for, and where the order reads: build it, staff it,
    then let people see it."""
    sign_in(admin)
    text = client.get(f"/modules/{module.id}").text

    assert text.index("/roster") < text.index("/publish")


def test_it_is_no_longer_on_the_settings_page(client, sign_in, admin, module):
    sign_in(admin)
    page = client.get(f"/modules/{module.id}/edit")

    assert page.status_code == 200
    assert f'action="/modules/{module.id}/publish"' not in page.text
    # Remove stays there, which is where a destructive action belongs.
    assert f'action="/modules/{module.id}/delete"' in page.text


def test_the_settings_page_says_where_publishing_went(client, sign_in, admin, module):
    sign_in(admin)
    page = client.get(f"/modules/{module.id}/edit")

    assert "unpublish it from" in page.text.lower()


# ---------------------------------------------------------------- what it says


def test_it_offers_publish_while_the_module_is_hidden(client, sign_in, admin, module):
    sign_in(admin)
    page = client.get(f"/modules/{module.id}")

    assert ">\n                Publish\n              </button>" in page.text.replace(
        "\r\n", "\n"
    ) or "Publish" in page.text
    assert "btn-primary" in page.text


def test_it_offers_unpublish_once_the_module_is_live(client, db, sign_in, admin, module):
    module.is_published = True
    db.add(module)
    db.commit()
    sign_in(admin)

    page = client.get(f"/modules/{module.id}")

    assert "Unpublish" in page.text


# --------------------------------------------------------------- who may use it


def test_an_instructor_is_not_offered_it(client, sign_in, owner, module):
    """Publishing is an administrator's act. The control is absent rather than
    shown and refused (FR-005)."""
    sign_in(owner)
    page = client.get(f"/modules/{module.id}")

    assert page.status_code == 200
    assert f'action="/modules/{module.id}/publish"' not in page.text
    # They still run the module, so the rest of the toolbar is theirs.
    assert f'/modules/{module.id}/roster' in page.text


def test_an_instructor_posting_it_by_hand_is_refused(client, db, sign_in, owner, module, csrf):
    """The page not offering the control is never the enforcement."""
    sign_in(owner)

    token = csrf(f"/modules/{module.id}")
    response = client.post(
        f"/modules/{module.id}/publish",
        data={"is_published": "true", "csrf_token": token},
    )

    assert response.status_code == 403
    assert db.get(Module, module.id).is_published is False


# ------------------------------------------------------------------ it works


def test_publishing_returns_to_the_module_page(client, db, sign_in, admin, module, csrf):
    sign_in(admin)

    token = csrf(f"/modules/{module.id}")
    response = client.post(
        f"/modules/{module.id}/publish",
        data={"is_published": "true", "csrf_token": token},
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/modules/{module.id}"
    assert db.get(Module, module.id).is_published is True


def test_and_unpublishing_puts_it_back(client, db, sign_in, admin, module, csrf):
    module.is_published = True
    db.add(module)
    db.commit()
    sign_in(admin)

    token = csrf(f"/modules/{module.id}")
    client.post(
        f"/modules/{module.id}/publish",
        data={"is_published": "false", "csrf_token": token},
    )

    assert db.get(Module, module.id).is_published is False
