"""What a module's address tells you about whether it exists.

404 rather than 403 is deliberate: a trainee should not learn that a module
exists by being refused it (FR-007, quickstart Scenario 1).
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


def _enrol(db, user, module, role):
    db.add(Registration(user_id=user.id, module_id=module.id, role_in_module=role))
    db.commit()


def test_an_unpublished_module_is_404_for_a_trainee(client, db, make_user, sign_in, module):
    trainee = make_user(email="t@example.com", role="trainee")
    _enrol(db, trainee, module, "trainee")
    sign_in(trainee)

    assert client.get(f"/modules/{module.id}").status_code == 404


def test_an_unpublished_module_is_visible_to_its_instructor(
    client, db, make_user, sign_in, module
):
    instructor = make_user(email="i@example.com", role="instructor")
    _enrol(db, instructor, module, "instructor")
    sign_in(instructor)

    response = client.get(f"/modules/{module.id}")
    assert response.status_code == 200
    assert "Phishing Awareness" in response.text


def test_publishing_makes_it_reachable_by_a_registered_trainee(
    client, db, make_user, sign_in, module
):
    trainee = make_user(email="t@example.com", role="trainee")
    _enrol(db, trainee, module, "trainee")
    module.is_published = True
    db.add(module)
    db.commit()
    sign_in(trainee)

    assert client.get(f"/modules/{module.id}").status_code == 200


def test_an_unregistered_trainee_gets_404_even_when_published(
    client, db, make_user, sign_in, module
):
    module.is_published = True
    db.add(module)
    db.commit()

    sign_in(make_user(email="stranger@example.com", role="trainee"))
    assert client.get(f"/modules/{module.id}").status_code == 404


def test_only_an_administrator_may_create_a_module(client, make_user, sign_in, csrf):
    for role in ("instructor", "trainee"):
        sign_in(make_user(email=f"{role}@example.com", role=role))
        assert client.get("/modules/new").status_code == 403

        response = client.post(
            "/modules", data={"title": "Sneaky", "csrf_token": csrf("/modules")}
        )
        assert response.status_code == 403
        client.cookies.clear()


def test_an_administrator_creates_and_lands_on_the_module(client, make_user, sign_in, csrf):
    sign_in(make_user(email="a@example.com", role="administrator"))

    response = client.post(
        "/modules",
        data={
            "title": "Passwords",
            "description": "Choosing them",
            "csrf_token": csrf("/modules/new"),
        },
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/modules/")


def test_a_module_needs_a_title(client, make_user, sign_in, csrf):
    sign_in(make_user(email="a@example.com", role="administrator"))

    response = client.post(
        "/modules", data={"title": "   ", "csrf_token": csrf("/modules/new")}
    )

    assert response.status_code == 400
    assert "needs a title" in response.text
